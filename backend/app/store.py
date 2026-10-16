"""Firestore persistence: reports, indicator fingerprints, campaigns, stats, feed.

Collections
-----------
reports/{id}       redacted report + 768-d embedding (server-only)
indicators/{fp}    HMAC fingerprint of a phone/account/domain, with counts (server-only)
campaigns/{id}     clusters of similar reports            (readable by signed-in clients)
stats/global       running counters for the console       (readable by signed-in clients)
feed/{id}          short redacted headlines for the live ticker (readable)
bulletins/{id}     Gemini-written threat bulletins        (readable)
liveSessions/{id}  summaries of Live Guardian sessions     (server-only)
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1 import Increment
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from .config import get_settings

# Rough median loss per scam type in MYR, used only for the clearly-labelled
# "estimated loss averted" KPI. Sources and method: docs/BENCHMARK.md.
MEDIAN_LOSS_MYR = {
    "investment": 20000, "romance": 25000, "authority_impersonation": 15000, "parcel_courier": 12000,
    "bank_impersonation": 8000, "job_task": 6000, "tech_support": 7000, "deepfake_voice": 15000,
    "phishing": 3000, "loan": 2000, "family_emergency": 4000, "prize_lottery": 2000, "ecommerce": 500,
    "other": 3000,
}


@lru_cache
def db() -> firestore.AsyncClient:
    s = get_settings()
    return firestore.AsyncClient(project=s.project_id or None, database=s.firestore_database)


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, dt.datetime) else v


def clean(doc: dict) -> dict:
    """Make a Firestore document JSON-safe and drop server-only fields."""
    out = {}
    for k, v in doc.items():
        if k in ("embedding", "indicatorFps", "expireAt"):
            continue
        if isinstance(v, dict):
            out[k] = clean(v)
        elif isinstance(v, list):
            out[k] = [clean(i) if isinstance(i, dict) else _iso(i) for i in v]
        else:
            out[k] = _iso(v)
    return out


# ---------------------------------------------------------------- indicators
async def lookup_indicators(fps: list[str]) -> dict[str, dict]:
    if not fps:
        return {}
    refs = [db().collection("indicators").document(fp) for fp in fps]
    found = {}
    async for snap in db().get_all(refs):
        if snap.exists:
            found[snap.id] = snap.to_dict()
    return found


async def top_indicators(limit: int = 8) -> list[dict]:
    q = db().collection("indicators").order_by("count", direction=firestore.Query.DESCENDING).limit(limit)
    return [{"id": s.id, **clean(s.to_dict())} async for s in q.stream()]


# ---------------------------------------------------------------- vectors
async def similar_reports(vec: list[float], limit: int = 5) -> list[dict]:
    q = db().collection("reports").find_nearest(
        vector_field="embedding", query_vector=Vector(vec), limit=limit,
        distance_measure=DistanceMeasure.COSINE, distance_result_field="distance",
    )
    out = []
    async for s in q.stream():
        d = s.to_dict()
        out.append({"id": s.id, "distance": d.get("distance", 1.0), "summary": d.get("summary"),
                    "scamType": d.get("scamType"), "campaignId": d.get("campaignId"),
                    "country": d.get("country"), "createdAt": _iso(d.get("createdAt"))})
    return out


# ---------------------------------------------------------------- campaigns
async def get_campaign(cid: str) -> dict | None:
    snap = await db().collection("campaigns").document(cid).get()
    return {"id": snap.id, **clean(snap.to_dict())} if snap.exists else None


async def list_campaigns(limit: int = 12, scam_type: str | None = None, country: str | None = None) -> list[dict]:
    q = db().collection("campaigns")
    if scam_type:
        q = q.where(filter=firestore.FieldFilter("scamType", "==", scam_type))
    q = q.order_by("count", direction=firestore.Query.DESCENDING).limit(limit * 3 if country else limit)
    rows = [{"id": s.id, **clean(s.to_dict())} async for s in q.stream()]
    if country:
        rows = [r for r in rows if country in (r.get("countries") or {})]
    return rows[:limit]


# ---------------------------------------------------------------- reports
async def save_report(report: dict, vec: list[float], indicators: list[tuple[str, dict]],
                      campaign: dict) -> str:
    """Atomically write a report plus its indicator, campaign, stats and feed side-effects."""
    t = report.get("createdAt") or now()
    batch = db().batch()
    rref = db().collection("reports").document()
    batch.set(rref, {**report, "createdAt": t, "expireAt": t + dt.timedelta(days=180), "embedding": Vector(vec),
                     "indicatorFps": [fp for fp, _ in indicators], "campaignId": campaign["id"]})

    for fp, ind in indicators:
        batch.set(db().collection("indicators").document(fp), {
            "kind": ind["kind"], "masked": ind["masked"], "count": Increment(1), "lastSeen": t,
            "scamTypes": {report["scamType"]: Increment(1)}, "countries": {report["country"]: Increment(1)},
        }, merge=True)

    cref = db().collection("campaigns").document(campaign["id"])
    cdoc = {"count": Increment(1), "lastSeen": t, "countries": {report["country"]: Increment(1)},
            "channels": {report.get("channel", "unknown"): Increment(1)}}
    if campaign.get("new"):
        cdoc.update({"title": campaign["title"], "scamType": report["scamType"], "summary": report["summary"],
                     "tactics": report.get("tactics", []), "firstSeen": t, "severity": report.get("riskScore", 50)})
    batch.set(cref, cdoc, merge=True)

    is_scam = report["verdict"] == "scam"
    stats = {"reports": Increment(1), "updatedAt": now(),
             "verdicts": {report["verdict"]: Increment(1)},
             "byType": {report["scamType"]: Increment(1)},
             "byCountry": {report["country"]: Increment(1)},
             "byChannel": {report.get("channel", "unknown"): Increment(1)}}
    if is_scam and report.get("killChainStage") != "cashout":
        stats["lossAvertedMYR"] = Increment(MEDIAN_LOSS_MYR.get(report["scamType"], 3000))
    batch.set(db().collection("stats").document("global"), stats, merge=True)

    batch.set(db().collection("feed").document(rref.id), {
        "createdAt": t, "expireAt": t + dt.timedelta(days=30), "country": report["country"],
        "scamType": report["scamType"],
        "verdict": report["verdict"], "riskScore": report.get("riskScore", 0),
        "headline": report.get("headline", "")[:140], "source": report.get("source", "check"),
        "campaignId": campaign["id"],
    })
    await batch.commit()
    return rref.id


async def recent_reports(days: int = 21, limit: int = 1000) -> list[dict]:
    since = now() - dt.timedelta(days=days)
    q = (db().collection("reports").where(filter=firestore.FieldFilter("createdAt", ">=", since))
         .order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
         .select(["createdAt", "scamType", "country", "verdict", "campaignId", "channel", "tactics", "summary",
                  "riskScore"]))
    return [{"id": s.id, **clean(s.to_dict())} async for s in q.stream()]


async def recent_feed(limit: int = 12) -> list[dict]:
    q = db().collection("feed").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
    return [{"id": s.id, **clean(s.to_dict())} async for s in q.stream()]


async def get_stats() -> dict:
    snap = await db().collection("stats").document("global").get()
    return clean(snap.to_dict() or {})


# ---------------------------------------------------------------- live + bulletins
async def save_live_session(doc: dict) -> str:
    ref = db().collection("liveSessions").document()
    await ref.set(doc)
    upd = {"liveSessions": Increment(1), "updatedAt": now()}
    if doc.get("warned"):
        upd["liveWarnings"] = Increment(1)
    await db().collection("stats").document("global").set(upd, merge=True)
    return ref.id


async def save_bulletin(doc: dict) -> str:
    ref = db().collection("bulletins").document()
    await ref.set({**doc, "createdAt": now()})
    return ref.id


async def latest_bulletin() -> dict | None:
    q = db().collection("bulletins").order_by("createdAt", direction=firestore.Query.DESCENDING).limit(1)
    async for s in q.stream():
        return {"id": s.id, **clean(s.to_dict())}
    return None
