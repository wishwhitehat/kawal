"""Bulletin agent - turns community intel into a threat bulletin a bank fraud
team can act on, with ready-to-send customer advisories in EN / BM / 中文."""

from __future__ import annotations

import json

from .. import genai_client, store
from ..config import get_settings
from ..taxonomy import SCAM_TYPES, TACTICS

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "threat_level": {"type": "string", "enum": ["low", "elevated", "high", "critical"]},
        "executive_summary": {"type": "string"},
        "campaigns": {"type": "array", "maxItems": 5, "items": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "scam_type": {"type": "string", "enum": list(SCAM_TYPES)},
                "trend": {"type": "string", "enum": ["rising", "stable", "falling", "new"]},
                "what_is_happening": {"type": "string"},
                "tactics": {"type": "array", "items": {"type": "string", "enum": list(TACTICS)}},
                "countries": {"type": "array", "items": {"type": "string"}},
                "bank_controls": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
            },
            "required": ["name", "scam_type", "trend", "what_is_happening", "tactics", "countries", "bank_controls"]}},
        "mule_signals": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        "customer_advisory": {"type": "object", "properties": {
            "en": {"type": "string"}, "ms": {"type": "string"}, "zh": {"type": "string"}},
            "required": ["en", "ms", "zh"]},
    },
    "required": ["title", "threat_level", "executive_summary", "campaigns", "mule_signals", "customer_advisory"],
}

SYSTEM = """You are a financial-crime intelligence analyst writing for bank fraud-operations teams and
regulators in Asia-Pacific. Use ONLY the data provided. Be specific and operational: bank_controls are
concrete detection rules or customer-journey interventions (e.g. cooling-off for first-time large payees,
step-up checks when a customer is on an active call, mule-account velocity rules). customer_advisory is
SMS-length (max 280 characters) and must never include links. Trend: compare last-7-day counts with the
week before."""


async def generate() -> dict:
    s = get_settings()
    stats = await store.get_stats()
    campaigns = await store.list_campaigns(limit=8)
    reports = await store.recent_reports(days=14, limit=400)
    now = store.now()
    weekly: dict[str, list[int]] = {}
    for r in reports:
        created = r.get("createdAt") or ""
        age_days = (now - store.dt.datetime.fromisoformat(created)).days if created else 99
        bucket = 0 if age_days < 7 else 1
        weekly.setdefault(r.get("campaignId") or "?", [0, 0])[bucket] += 1
    payload = {
        "totals": {k: stats.get(k) for k in ("reports", "verdicts", "byType", "byCountry", "byChannel")},
        "campaigns": [{"name": c.get("title"), "scam_type": c.get("scamType"), "total": c.get("count"),
                       "last7d": weekly.get(c["id"], [0, 0])[0], "prev7d": weekly.get(c["id"], [0, 0])[1],
                       "countries": c.get("countries"), "channels": c.get("channels"),
                       "tactics": c.get("tactics"), "summary": c.get("summary")} for c in campaigns],
    }
    resp = await genai_client.generate(
        model=s.model_flash,
        contents="Community intelligence (redacted, last 14 days):\n" + json.dumps(payload, default=str),
        config=genai_client.json_config(SCHEMA, system=SYSTEM, thinking="MEDIUM", temperature=0.3,
                                        max_tokens=4096),
    )
    bulletin = genai_client.parse_json(resp)
    bulletin["basedOn"] = {"reports": len(reports), "campaigns": len(campaigns)}
    bulletin["id"] = await store.save_bulletin(bulletin)
    return bulletin
