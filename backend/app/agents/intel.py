"""Community-intel agent - connects one report to everything Kawal has seen:
repeat indicators (by privacy-preserving fingerprint) and similar reports
(Firestore vector search over Gemini embeddings), grouped into campaigns."""

from __future__ import annotations

import logging
import uuid

from .. import genai_client, store
from ..config import get_settings
from ..redact import Indicator

log = logging.getLogger(__name__)

# Cosine distance under which two reports are treated as the same campaign.
SAME_CAMPAIGN = 0.20
SAME_CAMPAIGN_ANY_TYPE = 0.12


def fingerprints(indicators: list[Indicator]) -> list[tuple[str, Indicator]]:
    pepper = get_settings().indicator_pepper
    return [(ind.fingerprint(pepper), ind) for ind in indicators]


def campaign_for(scam_type: str, pattern_name: str, neighbours: list[dict]) -> dict:
    for n in neighbours:
        if not n.get("campaignId"):
            continue
        d = n.get("distance", 1.0)
        if d <= SAME_CAMPAIGN_ANY_TYPE or (d <= SAME_CAMPAIGN and n.get("scamType") == scam_type):
            return {"id": n["campaignId"], "new": False}
    return {"id": "c_" + uuid.uuid4().hex[:12], "new": True, "title": pattern_name[:90] or "Unnamed pattern"}


async def run(*, summary_en: str, scam_type: str, pattern_name: str,
              indicators: list[Indicator]) -> dict:
    fps = fingerprints(indicators)
    vec = (await genai_client.embed([f"{scam_type}: {pattern_name}. {summary_en}"]))[0]
    seen = await store.lookup_indicators([fp for fp, _ in fps])
    neighbours = await store.similar_reports(vec, limit=5)
    campaign = campaign_for(scam_type, pattern_name, neighbours)
    existing = await store.get_campaign(campaign["id"]) if not campaign["new"] else None

    repeat = []
    for fp, ind in fps:
        prior = seen.get(fp)
        if prior:
            repeat.append({"kind": ind.kind, "masked": ind.masked, "count": prior.get("count", 0),
                           "countries": prior.get("countries", {})})
    return {
        "vector": vec,
        "fingerprints": fps,
        "repeatIndicators": repeat,
        "similar": neighbours[:3],
        "campaign": campaign,
        "campaignInfo": existing,
    }
