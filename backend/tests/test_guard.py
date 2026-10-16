import pytest

from app import guard
from app.config import Settings
from app.main import _sniff


def test_sniff_detects_real_types_and_rejects_disguised_files():
    assert _sniff(b"\x89PNG\r\n\x1a\n" + b"0" * 8) == "image"
    assert _sniff(b"\xff\xd8\xff\xe0" + b"0" * 12) == "image"
    assert _sniff(b"%PDF-1.7" + b"0" * 8) == "pdf"
    assert _sniff(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "audio"
    assert _sniff(b"\x00\x00\x00\x20ftypM4A " + b"0" * 4) == "audio"
    assert _sniff(b"MZ\x90\x00 this is an exe") is None


def test_partial_quota_override_keeps_other_caps(monkeypatch):
    monkeypatch.setenv("GLOBAL_DAILY", '{"check": 5}')
    s = Settings()
    assert s.global_daily["check"] == 5
    assert all(s.global_daily.get(k) for k in ("grounding", "live", "tts", "ask", "bulletin"))


def test_ip_key_is_keyed_hash_not_raw_ip():
    k = guard.ip_key("203.0.113.7")
    assert "203" not in k and len(k) == 24
    assert k == guard.ip_key("203.0.113.7")


def test_client_ip_uses_first_forwarded_hop():
    assert guard.client_ip({"x-forwarded-for": "203.0.113.7, 10.0.0.1"}) == "203.0.113.7"
    assert guard.client_ip({}) == "unknown"


def test_cache_key_normalises_whitespace_and_case():
    assert guard.cache_key("v1", "Hello   WORLD", "en") == guard.cache_key("v1", "hello world", "en")
    assert guard.cache_key("v1", "hello", "en") != guard.cache_key("v1", "hello", "ms")


def test_quota_exceeded_is_a_friendly_429():
    exc = guard.QuotaExceeded("global", "check")
    assert exc.status_code == 429 and exc.detail["code"] == "quota_global"


def test_app_check_required_rejects_missing_token(monkeypatch):
    monkeypatch.setattr(guard, "get_settings", lambda: Settings(appcheck_required=True))
    with pytest.raises(Exception) as exc:
        guard.verify_app_check(None)
    assert exc.value.status_code == 401
