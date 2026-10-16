"""Analyst agent ("Ask Kawal Intel") - answers natural-language questions from
bank / regulator analysts by calling tools over the Firestore intel store.
The tool trace is returned so every answer is auditable."""

from __future__ import annotations

import collections
import json
import logging

from google.genai import types

from .. import genai_client, store
from ..config import get_settings
from ..redact import indicator_from_model
from ..taxonomy import SCAM_TYPES
from .intel import fingerprints

log = logging.getLogger(__name__)

SYSTEM = """You are Kawal Intel, an assistant for bank fraud teams and regulators in Asia-Pacific.
Answer ONLY from tool results; call tools before answering. If data is insufficient, say so.
Be concise: a direct answer first, then up to 5 bullet points with numbers. Never reveal raw personal data;
indicators are masked. Mention that community data is unverified user reports where relevant.
Scam type ids: """ + ", ".join(SCAM_TYPES)

TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(name="get_overview", description="Totals by verdict, scam type, country and channel.",
                              parameters_json_schema={"type": "object", "properties": {}}),
    types.FunctionDeclaration(
        name="list_campaigns", description="Scam campaigns (clusters of similar reports), largest first.",
        parameters_json_schema={"type": "object", "properties": {
            "scam_type": {"type": "string", "description": "optional scam type id"},
            "country": {"type": "string", "description": "optional ISO country code, e.g. MY"},
            "limit": {"type": "integer"}}}),
    types.FunctionDeclaration(
        name="search_reports", description="Semantic search over redacted report summaries.",
        parameters_json_schema={"type": "object", "properties": {
            "query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}),
    types.FunctionDeclaration(
        name="daily_counts", description="Reports per day for the last N days, optionally for one scam type.",
        parameters_json_schema={"type": "object", "properties": {
            "days": {"type": "integer"}, "scam_type": {"type": "string"}}}),
    types.FunctionDeclaration(
        name="lookup_indicator", description="How often a phone number, bank account or domain was reported.",
        parameters_json_schema={"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["phone", "account", "url", "email", "wallet"]},
            "value": {"type": "string"}, "country": {"type": "string"}}, "required": ["kind", "value"]}),
])]


async def _call(name: str, args: dict) -> object:
    if name == "get_overview":
        s = await store.get_stats()
        return {k: s.get(k) for k in ("reports", "verdicts", "byType", "byCountry", "byChannel", "liveSessions")}
    if name == "list_campaigns":
        rows = await store.list_campaigns(limit=min(int(args.get("limit") or 6), 12),
                                          scam_type=args.get("scam_type"), country=args.get("country"))
        return [{k: r.get(k) for k in ("title", "scamType", "count", "countries", "channels", "tactics",
                                       "firstSeen", "lastSeen", "summary")} for r in rows]
    if name == "search_reports":
        vec = (await genai_client.embed([args["query"]]))[0]
        rows = await store.similar_reports(vec, limit=min(int(args.get("limit") or 5), 10))
        return [{k: r.get(k) for k in ("summary", "scamType", "country", "createdAt", "distance")} for r in rows]
    if name == "daily_counts":
        days = min(int(args.get("days") or 14), 60)
        rows = await store.recent_reports(days=days)
        st = args.get("scam_type")
        counts = collections.Counter((r.get("createdAt") or "")[:10] for r in rows if not st or r.get("scamType") == st)
        return dict(sorted(counts.items()))
    if name == "lookup_indicator":
        ind = indicator_from_model(args.get("kind", ""), args.get("value", ""), args.get("country") or "MY")
        if not ind:
            return {"found": False}
        fp, _ = fingerprints([ind])[0]
        hit = (await store.lookup_indicators([fp])).get(fp)
        return {"found": bool(hit), "masked": ind.masked, **({"count": hit.get("count"),
                "countries": hit.get("countries"), "scamTypes": hit.get("scamTypes")} if hit else {})}
    return {"error": f"unknown tool {name}"}


async def ask(question: str) -> dict:
    s = get_settings()
    contents: list[types.Content] = [types.Content(role="user", parts=[types.Part.from_text(text=question)])]
    config = types.GenerateContentConfig(system_instruction=SYSTEM, tools=TOOLS, temperature=0.2,
                                         thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                                         automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
    trace = []
    for _ in range(5):
        resp = await genai_client.generate(s.model_flash, contents, config)
        calls = resp.function_calls or []
        if not calls:
            return {"answer": (resp.text or "").strip(), "trace": trace}
        contents.append(resp.candidates[0].content)
        parts = []
        for fc in calls:
            try:
                result = await _call(fc.name, dict(fc.args or {}))
            except Exception as exc:
                log.exception("tool %s failed", fc.name)
                result = {"error": type(exc).__name__}
            preview = json.dumps(result, default=str, ensure_ascii=False)
            trace.append({"tool": fc.name, "args": dict(fc.args or {}), "preview": preview[:240]})
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": json.loads(preview)}))
        contents.append(types.Content(role="user", parts=parts))
    return {"answer": "I could not complete this analysis in time. Try a narrower question.", "trace": trace}
