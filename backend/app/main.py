"""Kawal API - FastAPI app served on Cloud Run."""

from __future__ import annotations

import base64
import collections
import datetime as dt
import hashlib
import io
import json
import logging
import time
import wave

import google.auth.transport.requests
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from google.genai import types
from google.oauth2 import id_token
from pydantic import BaseModel, Field

from . import genai_client, guard, live, pipeline, store
from .agents import analyst, bulletin
from .auth import User, limited
from .config import get_settings
from .taxonomy import HOTLINES, KILL_CHAIN, LANGS, SCAM_TYPES, TACTICS, clamp_enum

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("kawal")

settings = get_settings()
app = FastAPI(title="Kawal API", version="1.1.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type", "X-Firebase-AppCheck"], max_age=3600)

# Declared type -> (category, size cap). Content is sniffed too, see `_sniff`.
ALLOWED_MIME = {
    "image/png": "image", "image/jpeg": "image", "image/webp": "image", "image/heic": "image",
    "image/heif": "image", "application/pdf": "pdf",
    "audio/mpeg": "audio", "audio/mp3": "audio", "audio/mp4": "audio", "audio/m4a": "audio",
    "audio/x-m4a": "audio", "audio/aac": "audio", "audio/wav": "audio", "audio/x-wav": "audio",
    "audio/ogg": "audio", "audio/webm": "audio", "audio/flac": "audio",
}


def _sniff(data: bytes) -> str | None:
    """Identify a file by its magic bytes - the declared MIME type is not trusted."""
    head = data[:16]
    if head.startswith(b"\x89PNG") or head.startswith(b"\xff\xd8\xff"):
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio"
    if head.startswith(b"%PDF"):
        return "pdf"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        return "image" if brand in (b"heic", b"heix", b"mif1", b"msf1") else "audio"
    if head.startswith((b"ID3", b"OggS", b"fLaC", b"\x1a\x45\xdf\xa3")) or head[:2] in (b"\xff\xfb", b"\xff\xf3",
                                                                                          b"\xff\xf1", b"\xff\xf9"):
        return "audio"
    return None


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Cache-Control"] = resp.headers.get("Cache-Control", "no-store")
    return resp


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse({"detail": "Internal error"}, status_code=500)


# Every AI endpoint: kill switch -> App Check -> per-minute limit (-> daily quota inside).
ai_guard = [Depends(guard.ensure_open), Depends(guard.app_check_dep)]


# ------------------------------------------------------------------ public
@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "kawal-api"}


@app.get("/api/meta")
async def meta():
    return {
        "languages": LANGS,
        "countries": {k: {"name": v["name"], "primary": v["primary"]} for k, v in HOTLINES.items()},
        "scamTypes": SCAM_TYPES, "tactics": TACTICS, "killChain": KILL_CHAIN,
        "models": {"flash": settings.model_flash, "lite": settings.model_lite, "live": settings.model_live,
                   "embed": settings.model_embed, "tts": settings.model_tts},
    }


@app.get("/api/usage")
async def usage():
    """Public transparency: today's usage against the daily ceilings, and kill-switch state."""
    rt = await guard.runtime()
    return {**await guard.usage_today(), "paused": bool(rt.get("paused")), "reason": rt.get("reason", "")}


# ------------------------------------------------------------------ scam check
@app.post("/api/check", dependencies=ai_guard)
async def check(
    request: Request,
    text: str = Form(default="", max_length=8000),
    lang: str = Form(default="en"),
    country: str = Form(default="MY"),
    share: bool = Form(default=True),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(limited("check")),
):
    text = text[: settings.max_text_chars]
    if len(files) > settings.max_files:
        raise HTTPException(400, f"At most {settings.max_files} files per check")
    caps = {"image": settings.max_image_mb, "audio": settings.max_audio_mb, "pdf": settings.max_pdf_mb}
    media: list[tuple[bytes, str]] = []
    for f in files:
        mime = (f.content_type or "").split(";")[0].lower()
        declared = ALLOWED_MIME.get(mime)
        if not declared:
            raise HTTPException(415, f"Unsupported file type: {mime or 'unknown'}")
        limit = int(caps[declared] * 1024 * 1024)
        data = await f.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"{declared.title()} files are limited to {caps[declared]:g} MB")
        if _sniff(data) != declared:
            raise HTTPException(415, "File content does not match its type")
        media.append((data, "audio/mp4" if mime in ("audio/m4a", "audio/x-m4a") else mime))
    if not text.strip() and not media:
        raise HTTPException(400, "Paste a message or attach a screenshot / audio")

    lang = clamp_enum(lang, LANGS, "en")
    country = (country or "MY").upper()[:2]
    ip = guard.client_ip(request.headers)

    # Identical text-only checks are served from cache at zero model cost.
    key = guard.cache_key("check-v1", text, lang, country) if not media else None
    cached = await guard.cache_get(key) if key else None
    if not cached:
        await guard.consume("check", user.uid, ip)
    verify = bool(cached) or await guard.try_consume_global("grounding")

    async def stream():
        if cached:
            for sid in ("triage", "evidence", "intel", "advice"):
                yield f"event: stage\ndata: {json.dumps({'id': sid, 'status': 'done', 'ms': 0})}\n\n"
            payload = {**cached, "cached": True, "shared": False, "timingMs": 0}
            yield f"event: result\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
            return
        try:
            async for event, payload in pipeline.check(text=text, media=media, lang=lang, country=country,
                                                       share=share, verify=verify):
                if event == "result":
                    if not verify:
                        payload["evidence"]["findings"] = "Web verification is paused for today (daily limit)."
                    if key:
                        await guard.cache_put(key, payload, settings.check_cache_hours)
                yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        except Exception:
            log.exception("check failed")
            yield 'event: error\ndata: {"message": "Analysis failed, please try again."}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ------------------------------------------------------------------ read aloud
class TtsIn(BaseModel):
    text: str = Field(max_length=900)
    lang: str = "en"


_tts_cache: collections.OrderedDict[str, bytes] = collections.OrderedDict()


@app.post("/api/tts", dependencies=ai_guard)
async def tts(body: TtsIn, request: Request, user: User = Depends(limited("tts", 6))):
    text = body.text[:600]
    key = hashlib.sha256(text.encode()).hexdigest()
    if key in _tts_cache:
        _tts_cache.move_to_end(key)
        return Response(_tts_cache[key], media_type="audio/wav")
    await guard.consume("tts", user.uid, guard.client_ip(request.headers))
    resp = await genai_client.client().aio.models.generate_content(
        model=settings.model_tts,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")))),
    )
    blob = resp.candidates[0].content.parts[0].inline_data
    if blob.mime_type == "audio/wav":
        audio = blob.data
    else:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(blob.data)
        audio = buf.getvalue()
    _tts_cache[key] = audio
    while len(_tts_cache) > 50:
        _tts_cache.popitem(last=False)
    return Response(audio, media_type="audio/wav")


# ------------------------------------------------------------------ intel console
_overview_cache: dict = {"at": 0.0, "data": None}


@app.get("/api/intel/overview", dependencies=[Depends(guard.app_check_dep)])
async def overview(user: User = Depends(limited("overview", 30))):
    # Aggregate, non-personal data: share one snapshot across callers for 30 s
    # to keep Firestore reads (and cost) flat under load.
    if _overview_cache["data"] and time.monotonic() - _overview_cache["at"] < 30:
        return _overview_cache["data"]
    stats = await store.get_stats()
    reports = await store.recent_reports(days=21, limit=600)
    campaigns = await store.list_campaigns(limit=8)
    feed = await store.recent_feed(limit=10)
    indicators = await store.top_indicators(limit=6)

    today = store.now().date()
    days = [(today - dt.timedelta(days=i)).isoformat() for i in range(20, -1, -1)]
    series = {d: {"scam": 0, "suspicious": 0} for d in days}
    tactic_counts: collections.Counter[str] = collections.Counter()
    per_campaign: dict[str, list[int]] = collections.defaultdict(lambda: [0] * 21)
    for r in reports:
        day = (r.get("createdAt") or "")[:10]
        if day in series and r.get("verdict") in ("scam", "suspicious"):
            series[day][r["verdict"]] += 1
        if day in series and r.get("campaignId"):
            per_campaign[r["campaignId"]][days.index(day)] += 1
        tactic_counts.update(r.get("tactics") or [])
    for c in campaigns:
        spark = per_campaign.get(c["id"], [0] * 21)
        c["spark"] = spark
        c["last7"], c["prev7"] = sum(spark[-7:]), sum(spark[-14:-7])
    data = {
        "stats": stats,
        "series": [{"day": d, **v} for d, v in series.items()],
        "tactics": [{"id": t, "label": TACTICS.get(t, t), "count": n} for t, n in tactic_counts.most_common(8)],
        "campaigns": campaigns,
        "feed": feed,
        "indicators": [{k: i.get(k) for k in ("kind", "masked", "count", "countries")} for i in indicators],
        "bulletin": await store.latest_bulletin(),
    }
    _overview_cache.update(at=time.monotonic(), data=data)
    return data


@app.post("/api/intel/bulletin", dependencies=ai_guard)
async def make_bulletin(request: Request, user: User = Depends(limited("bulletin", 2))):
    # Bulletins summarise slow-moving aggregates; reuse a recent one instead of paying again.
    latest = await store.latest_bulletin()
    if latest and latest.get("createdAt"):
        age = store.now() - dt.datetime.fromisoformat(latest["createdAt"])
        if age < dt.timedelta(minutes=settings.bulletin_cache_minutes):
            return {**latest, "cached": True}
    await guard.consume("bulletin", user.uid, guard.client_ip(request.headers))
    return await bulletin.generate()


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=300)


@app.post("/api/intel/ask", dependencies=ai_guard)
async def ask(body: AskIn, request: Request, user: User = Depends(limited("ask", 6))):
    await guard.consume("ask", user.uid, guard.client_ip(request.headers))
    return await analyst.ask(body.question)


# ------------------------------------------------------------------ budget circuit breaker
_google_request = google.auth.transport.requests.Request()


@app.post("/internal/budget", include_in_schema=False)
async def budget_breaker(request: Request):
    """Pub/Sub push target for Cloud Billing budget notifications.

    Engages the kill switch once actual spend reaches `breaker_ratio` x budget and
    releases it automatically when a new budget period starts (cost resets).
    Only accepts OIDC tokens minted for our dedicated push service account.
    """
    if not settings.budget_push_audience or not settings.budget_push_sa:
        raise HTTPException(404)
    auth = request.headers.get("authorization", "")
    try:
        claims = id_token.verify_oauth2_token(auth.removeprefix("Bearer "), _google_request,
                                              audience=settings.budget_push_audience)
    except Exception as exc:
        raise HTTPException(401, "bad token") from exc
    if claims.get("email") != settings.budget_push_sa or not claims.get("email_verified"):
        raise HTTPException(403, "unexpected caller")

    envelope = await request.json()
    data = json.loads(base64.b64decode(envelope["message"]["data"]))
    cost, budget = float(data.get("costAmount", 0)), float(data.get("budgetAmount", 0) or 0)
    log.info("budget notification cost=%s budget=%s %s", cost, budget, data.get("currencyCode"))
    rt = await guard.runtime()
    if budget and cost >= budget * settings.breaker_ratio and not rt.get("paused"):
        await guard.set_paused(True, f"Budget reached: {cost:.2f}/{budget:.2f} {data.get('currencyCode', '')}",
                               "budget")
        log.warning("kawal_paused budget breaker engaged")
    elif budget and cost < budget * settings.breaker_ratio and rt.get("paused") and rt.get("by") == "budget":
        await guard.set_paused(False, "New budget period", "budget")
    return {"ok": True}


# ------------------------------------------------------------------ live guardian
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await live.handle(ws)
