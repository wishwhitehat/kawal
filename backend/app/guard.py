"""Cost & abuse guard.

Kawal is open source and publicly reachable, so every AI feature sits behind
layered controls that keep the bill near zero no matter who calls it:

1. Kill switch   - `config/runtime.paused` (set by the budget circuit breaker or
                   by hand) turns every AI endpoint into a friendly 503.
2. Daily quotas  - global, per-user and per-IP counters in Firestore, so caps
                   hold across Cloud Run instances. They are the real ceiling:
                   worst-case spend per day is bounded by `GLOBAL_DAILY`.
3. App Check     - only the genuine web app (reCAPTCHA Enterprise attested) can
                   call the API; scripted clients are rejected.
4. Result cache  - identical checks are answered from Firestore for 24 h at zero
                   model cost (judges tend to click the same examples).

Per-minute bursts are handled separately by `auth.RateLimiter`.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from fastapi import HTTPException, Request, status
from firebase_admin import app_check
from google.cloud import firestore

from . import store
from .auth import _app
from .config import get_settings

log = logging.getLogger(__name__)

KINDS = ("check", "grounding", "live", "tts", "ask", "bulletin")


# ------------------------------------------------------------------ kill switch
_runtime: dict[str, Any] = {"at": 0.0, "doc": {}}


async def runtime() -> dict:
    """`config/runtime`, cached for 30 s per instance."""
    if time.monotonic() - _runtime["at"] > 30:
        try:
            snap = await store.db().collection("config").document("runtime").get()
            _runtime["doc"] = snap.to_dict() or {}
        except Exception:
            log.exception("could not read runtime config")
        _runtime["at"] = time.monotonic()
    return _runtime["doc"]


async def ensure_open() -> None:
    rt = await runtime()
    if rt.get("paused"):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {"code": "paused", "message": "Kawal's AI features are paused to stay within the project's budget. "
                                          "Please try again later."},
        )


async def set_paused(paused: bool, reason: str, by: str) -> None:
    await store.db().collection("config").document("runtime").set(
        {"paused": paused, "reason": reason, "by": by, "updatedAt": store.now()}, merge=True)
    _runtime["at"] = 0.0
    log.warning("kill switch %s by %s: %s", "ENGAGED" if paused else "released", by, reason)


# ------------------------------------------------------------------ identity
def client_ip(headers) -> str:
    """Caller IP as seen by Cloud Run's front end (first X-Forwarded-For hop)."""
    fwd = headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or "unknown"


def ip_key(ip: str) -> str:
    """Keyed hash - raw IP addresses are never stored."""
    pepper = get_settings().indicator_pepper.encode()
    return hmac.new(pepper, f"ip:{ip}".encode(), hashlib.sha256).hexdigest()[:24]


def verify_app_check(token: str | None) -> None:
    s = get_settings()
    if not s.appcheck_required:
        return
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing App Check token")
    try:
        app_check.verify_token(token, app=_app())
    except Exception as exc:  # invalid, expired, wrong app...
        log.info("app check rejected: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid App Check token") from exc


async def app_check_dep(request: Request) -> None:
    verify_app_check(request.headers.get("x-firebase-appcheck"))


# ------------------------------------------------------------------ quotas
def _limits() -> dict[str, dict[str, int]]:
    s = get_settings()
    return {"global": s.global_daily, "user": s.user_daily, "ip": s.ip_daily}


def _today() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%d")


class QuotaExceeded(HTTPException):
    def __init__(self, scope: str, kind: str):
        msg = {
            "global": "Kawal has reached today's demo limit for this feature. It resets at 08:00 MYT (00:00 UTC).",
            "user": "You've reached today's fair-use limit for this feature. Please try again tomorrow.",
            "ip": "Too many requests from your network today. Please try again tomorrow.",
        }[scope]
        super().__init__(status.HTTP_429_TOO_MANY_REQUESTS, {"code": f"quota_{scope}", "kind": kind, "message": msg})


async def consume(kind: str, uid: str | None, ip: str | None, n: int = 1) -> None:
    """Atomically check and increment global / user / IP counters for `kind`."""
    limits = _limits()
    day = _today()
    expire = dt.datetime.now(dt.UTC) + dt.timedelta(days=3)
    db = store.db()
    gref = db.collection("usage").document(day)
    refs = {"global": gref}
    if uid and limits["user"].get(kind):
        refs["user"] = gref.collection("users").document(uid)
    if ip and limits["ip"].get(kind):
        refs["ip"] = gref.collection("ips").document(ip_key(ip))

    @firestore.async_transactional
    async def txn(tx):
        snaps = {scope: await ref.get(transaction=tx) for scope, ref in refs.items()}
        for scope, snap in snaps.items():
            cap = limits[scope].get(kind)
            used = (snap.to_dict() or {}).get(kind, 0) if snap.exists else 0
            if cap is not None and used + n > cap:
                log.warning("quota_exceeded scope=%s kind=%s used=%s cap=%s", scope, kind, used, cap)
                raise QuotaExceeded(scope, kind)
        for ref in refs.values():
            tx.set(ref, {kind: firestore.Increment(n), "expireAt": expire}, merge=True)

    await txn(db.transaction())


async def try_consume_global(kind: str, n: int = 1) -> bool:
    """Like `consume` for optional enrichments: returns False instead of raising."""
    try:
        await consume(kind, None, None, n)
        return True
    except QuotaExceeded:
        return False


async def usage_today() -> dict:
    snap = await store.db().collection("usage").document(_today()).get()
    used = {k: v for k, v in (snap.to_dict() or {}).items() if k in KINDS}
    return {"date": _today(), "used": used, "limits": _limits()["global"]}


# ------------------------------------------------------------------ result cache
def cache_key(*parts: str) -> str:
    norm = "\x1f".join(" ".join(p.split()).lower() for p in parts)
    return hashlib.sha256(norm.encode()).hexdigest()


async def cache_get(key: str) -> dict | None:
    snap = await store.db().collection("cache").document(key).get()
    if not snap.exists:
        return None
    doc = snap.to_dict()
    if doc.get("expireAt") and doc["expireAt"] < dt.datetime.now(dt.UTC):
        return None
    try:
        return json.loads(doc["value"])
    except (KeyError, json.JSONDecodeError):
        return None


async def cache_put(key: str, value: dict, hours: int = 24) -> None:
    blob = json.dumps(value, ensure_ascii=False, default=str)
    if len(blob) > 900_000:
        return
    await store.db().collection("cache").document(key).set(
        {"value": blob, "expireAt": dt.datetime.now(dt.UTC) + dt.timedelta(hours=hours)})
