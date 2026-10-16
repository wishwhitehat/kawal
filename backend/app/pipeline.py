"""Scam Check orchestration: Triage -> (Evidence || Community intel) -> Advice -> Share.

`check()` is an async generator of (event, payload) tuples so the HTTP layer can
stream each agent's progress to the browser as Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

from . import store
from .agents import evidence, intel, triage
from .redact import extract_indicators, extract_urls, indicator_from_model, redact_text
from .taxonomy import KILL_CHAIN, SCAM_TYPES, TACTICS, clamp_enum, hotline

log = logging.getLogger(__name__)

Event = tuple[str, dict]


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


async def _skip_evidence() -> dict:
    return {"findings": "", "sources": [], "queries": [], "webRisk": []}


async def check(*, text: str, media: list[tuple[bytes, str]], lang: str, country: str,
                share: bool, source: str = "check", created_at=None, verify: bool = True) -> AsyncIterator[Event]:
    t_all = time.perf_counter()

    # With text in hand, the evidence agent starts immediately, in parallel with triage.
    t_ev = time.perf_counter()
    ev_task = None
    if not verify:
        ev_task = asyncio.create_task(_skip_evidence())
    elif text.strip():
        ev_task = asyncio.create_task(evidence.run(context=text, urls=extract_urls(text), lang=lang))
        yield "stage", {"id": "evidence", "status": "running"}

    # 1. Triage (multimodal, structured)
    yield "stage", {"id": "triage", "status": "running"}
    t0 = time.perf_counter()
    try:
        tri = await triage.run(text=text, media=media, lang=lang, country=country)
    except Exception:
        if ev_task:
            ev_task.cancel()
        raise
    tri["scam_type"] = clamp_enum(tri.get("scam_type"), SCAM_TYPES, "other")
    tri["red_flags"] = [f for f in tri.get("red_flags", []) if f.get("tactic") in TACTICS]
    yield "stage", {"id": "triage", "status": "done", "ms": _ms(t0)}

    # Indicators: regex over the text we have + whatever the model read from media.
    seen_text = f"{text}\n{tri.get('extracted_text', '')}"
    inds = {(i.kind, i.value): i for i in extract_indicators(seen_text, country)}
    for raw in tri.get("indicators", []):
        ind = indicator_from_model(raw.get("kind", ""), raw.get("value", ""), country)
        if ind:
            inds.setdefault((ind.kind, ind.value), ind)
    indicators = list(inds.values())

    # 2. Evidence (if not already running) + 3. Community intel, in parallel
    if ev_task is None:
        t_ev = time.perf_counter()
        media_urls = extract_urls(tri.get("extracted_text", "")) + [
            r["value"] if "://" in r["value"] else "http://" + r["value"]
            for r in tri.get("indicators", []) if r.get("kind") == "url"]
        context = f"{tri.get('headline', '')}. {tri.get('extracted_text', '')}"
        ev_task = asyncio.create_task(evidence.run(context=context, urls=media_urls, lang=lang))
        yield "stage", {"id": "evidence", "status": "running"}
    yield "stage", {"id": "intel", "status": "running"}
    t0 = time.perf_counter()
    in_task = asyncio.create_task(intel.run(summary_en=tri.get("summary_en", ""), scam_type=tri["scam_type"],
                                            pattern_name=tri.get("pattern_name", ""), indicators=indicators))
    pending = {ev_task: "evidence", in_task: "intel"}
    results: dict[str, object] = {}
    while pending:
        done, _ = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            name = pending.pop(task)
            try:
                results[name] = task.result()
                yield "stage", {"id": name, "status": "done", "ms": _ms(t_ev if name == "evidence" else t0)}
            except Exception:
                log.exception("%s agent failed", name)
                results[name] = None
                yield "stage", {"id": name, "status": "error", "ms": _ms(t_ev if name == "evidence" else t0)}
    ev = results.get("evidence") or {"findings": "", "sources": [], "webRisk": []}
    it = results.get("intel")

    # Web Risk is authoritative: a flagged link always means scam.
    if ev.get("webRisk") and tri["verdict"] != "scam":
        tri["verdict"], tri["risk_score"] = "scam", max(tri.get("risk_score", 0), 90)

    # 4. Advice (deterministic hotlines + model's tailored steps)
    yield "stage", {"id": "advice", "status": "done", "ms": 0}

    stage_ids = [s["id"] for s in KILL_CHAIN]
    result = {
        "verdict": tri["verdict"],
        "riskScore": int(tri.get("risk_score", 0)),
        "confidence": tri.get("confidence"),
        "scamType": tri["scam_type"],
        "scamTypeLabel": SCAM_TYPES[tri["scam_type"]],
        "channel": tri.get("channel", "unknown"),
        "headline": tri.get("headline", ""),
        "explanation": tri.get("explanation", ""),
        "redFlags": [{**f, "label": TACTICS[f["tactic"]]} for f in tri["red_flags"]],
        "killChain": {"stages": KILL_CHAIN,
                      "current": clamp_enum(tri.get("kill_chain_stage"), stage_ids, "contact")},
        "impersonated": tri.get("impersonated_entity", ""),
        "indicators": [{"kind": i.kind, "masked": i.masked} for i in indicators],
        "doNow": tri.get("do_now", []),
        "dont": tri.get("dont", []),
        "hotline": hotline(country),
        "evidence": ev,
        "community": {
            "repeatIndicators": it["repeatIndicators"] if it else [],
            "similar": it["similar"] if it else [],
            "campaign": ({"id": it["campaign"]["id"], "new": it["campaign"]["new"],
                          "title": (it["campaignInfo"] or {}).get("title") or it["campaign"].get("title"),
                          "count": (it["campaignInfo"] or {}).get("count", 0)} if it else None),
        },
        "extractedText": tri.get("extracted_text", ""),
        "shared": False,
        "timingMs": _ms(t_all),
        "model": tri.get("_usage", {}),
    }

    # 5. Share (privacy-preserving) - only scams/suspicious, only with consent.
    if share and it and tri["verdict"] in ("scam", "suspicious"):
        try:
            report = {
                "verdict": tri["verdict"], "riskScore": result["riskScore"], "scamType": tri["scam_type"],
                "channel": result["channel"], "country": country, "lang": lang, "source": source,
                "summary": redact_text(tri.get("summary_en", ""))[:600],
                "headline": redact_text(tri.get("pattern_name", ""))[:140],
                "tactics": sorted({f["tactic"] for f in tri["red_flags"]}),
                "killChainStage": result["killChain"]["current"],
                "impersonated": tri.get("impersonated_entity", "")[:80],
                "synthetic": source == "seed",
            }
            if created_at:
                report["createdAt"] = created_at
            fps = [(fp, {"kind": ind.kind, "masked": ind.masked}) for fp, ind in it["fingerprints"]]
            rid = await store.save_report(report, it["vector"], fps, it["campaign"])
            result["shared"], result["reportId"] = True, rid
        except Exception:
            log.exception("failed to save report")

    yield "result", result
