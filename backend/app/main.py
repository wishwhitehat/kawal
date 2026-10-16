"""Kawal API - FastAPI app served on Cloud Run."""

from __future__ import annotations

import collections
import datetime as dt
import io
import json
import logging
import wave

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from google.genai import types
from pydantic import BaseModel, Field

from . import genai_client, live, pipeline, store
from .agents import analyst, bulletin
from .auth import User, current_user, limited
from .config import get_settings
from .taxonomy import HOTLINES, KILL_CHAIN, LANGS, SCAM_TYPES, TACTICS, clamp_enum

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
log = logging.getLogger("kawal")

settings = get_settings()
app = FastAPI(title="Kawal API", version="1.0.0", docs_url="/api/docs", openapi_url="/api/openapi.json",
              redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type"], max_age=3600)

ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/webp", "image/heic", "image/heif", "application/pdf",
    "audio/mpeg", "audio/mp3", "audio/mp4", "audio/m4a", "audio/x-m4a", "audio/aac", "audio/wav",
    "audio/x-wav", "audio/ogg", "audio/webm", "audio/flac",
}


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


# ------------------------------------------------------------------ scam check
@app.post("/api/check")
async def check(
    text: str = Form(default="", max_length=8000),
    lang: str = Form(default="en"),
    country: str = Form(default="MY"),
    share: bool = Form(default=True),
    files: list[UploadFile] = File(default=[]),
    user: User = Depends(limited("check")),
):
    media: list[tuple[bytes, str]] = []
    for f in files[:3]:
        mime = (f.content_type or "").split(";")[0].lower()
        if mime not in ALLOWED_MIME:
            raise HTTPException(415, f"Unsupported file type: {mime or 'unknown'}")
        data = await f.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"File too large (max {settings.max_upload_mb} MB)")
        media.append((data, "audio/mp4" if mime in ("audio/m4a", "audio/x-m4a") else mime))
    if not text.strip() and not media:
        raise HTTPException(400, "Paste a message or attach a screenshot / audio")

    lang = clamp_enum(lang, LANGS, "en")
    country = (country or "MY").upper()[:2]

    async def stream():
        try:
            async for event, payload in pipeline.check(text=text, media=media, lang=lang, country=country,
                                                       share=share):
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


@app.post("/api/tts")
async def tts(body: TtsIn, user: User = Depends(limited("tts", 10))):
    resp = await genai_client.client().aio.models.generate_content(
        model=settings.model_tts,
        contents=body.text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")))),
    )
    blob = resp.candidates[0].content.parts[0].inline_data
    if blob.mime_type == "audio/wav":
        return Response(blob.data, media_type="audio/wav")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(blob.data)
    return Response(buf.getvalue(), media_type="audio/wav")


# ------------------------------------------------------------------ intel console
@app.get("/api/intel/overview")
async def overview(user: User = Depends(current_user)):
    stats = await store.get_stats()
    reports = await store.recent_reports(days=21)
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
    return {
        "stats": stats,
        "series": [{"day": d, **v} for d, v in series.items()],
        "tactics": [{"id": t, "label": TACTICS.get(t, t), "count": n} for t, n in tactic_counts.most_common(8)],
        "campaigns": campaigns,
        "feed": feed,
        "indicators": [{k: i.get(k) for k in ("kind", "masked", "count", "countries")} for i in indicators],
        "bulletin": await store.latest_bulletin(),
    }


@app.post("/api/intel/bulletin")
async def make_bulletin(user: User = Depends(limited("bulletin", 3))):
    return await bulletin.generate()


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


@app.post("/api/intel/ask")
async def ask(body: AskIn, user: User = Depends(limited("ask", 10))):
    return await analyst.ask(body.question)


# ------------------------------------------------------------------ live guardian
@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    await live.handle(ws)
