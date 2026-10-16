"""Firebase Authentication: every API call carries a Firebase ID token.

Citizens are signed in anonymously by the web app (zero friction), which still
gives each browser a stable uid for rate limiting and abuse control.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass

import firebase_admin
from fastapi import Depends, Header, HTTPException, status
from firebase_admin import auth as fb_auth

from .config import get_settings

log = logging.getLogger(__name__)


@dataclass
class User:
    uid: str
    anonymous: bool


def _app() -> firebase_admin.App:
    try:
        return firebase_admin.get_app()
    except ValueError:
        pid = get_settings().project_id
        return firebase_admin.initialize_app(options={"projectId": pid} if pid else None)


def verify_token(token: str | None) -> User:
    s = get_settings()
    if not token:
        if not s.auth_required:
            return User(uid="dev-local", anonymous=True)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Firebase ID token")
    try:
        claims = fb_auth.verify_id_token(token, app=_app(), clock_skew_seconds=10)
    except Exception as exc:  # invalid, expired, wrong project...
        log.info("token rejected: %s", type(exc).__name__)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid Firebase ID token") from exc
    provider = claims.get("firebase", {}).get("sign_in_provider")
    return User(uid=claims["uid"], anonymous=provider == "anonymous")


async def current_user(authorization: str | None = Header(default=None)) -> User:
    token = authorization.split(" ", 1)[1] if authorization and authorization.lower().startswith("bearer ") else None
    return verify_token(token)


class RateLimiter:
    """Sliding-window limiter per uid. In-memory per instance is enough for a
    prototype capped at a handful of Cloud Run instances."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, please slow down")
        q.append(now)


limiter = RateLimiter()


def limited(bucket: str, per_minute: int | None = None):
    async def dep(user: User = Depends(current_user)) -> User:
        limiter.check(f"{bucket}:{user.uid}", per_minute or get_settings().rate_limit_per_minute)
        return user

    return dep
