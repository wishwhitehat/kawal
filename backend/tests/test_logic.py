import pytest
from fastapi import HTTPException

from app.agents.intel import campaign_for
from app.auth import RateLimiter
from app.live import clean_said
from app.taxonomy import HOTLINES, clamp_enum, hotline


def test_hotline_falls_back_to_malaysia():
    assert hotline("SG")["tel"] == "1799"
    assert hotline("XX")["country"] == "MY"
    assert all(h["steps"] for h in HOTLINES.values())


def test_clamp_enum():
    assert clamp_enum("scam", ["scam", "safe"], "safe") == "scam"
    assert clamp_enum("weird", ["scam", "safe"], "safe") == "safe"


def test_rate_limiter_blocks_after_limit():
    rl = RateLimiter()
    for _ in range(3):
        rl.check("u1", 3)
    with pytest.raises(HTTPException) as exc:
        rl.check("u1", 3)
    assert exc.value.status_code == 429
    rl.check("u2", 3)  # other users unaffected


def test_campaign_joins_close_neighbour_of_same_type():
    n = [{"campaignId": "c1", "distance": 0.15, "scamType": "parcel_courier"}]
    assert campaign_for("parcel_courier", "x", n) == {"id": "c1", "new": False}


def test_campaign_new_when_far_or_different_type():
    n = [{"campaignId": "c1", "distance": 0.15, "scamType": "investment"}]
    out = campaign_for("parcel_courier", "Fake courier fee SMS", n)
    assert out["new"] and out["title"] == "Fake courier fee SMS"


def test_live_control_tokens_are_removed():
    assert clean_said("<no speech>{pause}") == ""
    assert clean_said("Ini satu penipuan, <no ") == "Ini satu penipuan,"
