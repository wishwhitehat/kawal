"""Live Call Guardian - a WebSocket bridge between the browser and Gemini Live.

Two paths run side by side on the same call audio:

* Fast path  - Gemini 3.8 Live hears the raw audio (tone, urgency, language
               switching), calls `flag_scam_signal` the moment a tactic appears,
               and speaks a one-line warning to the user when risk is high.
* Deep path  - every few seconds Gemini Flash-Lite re-scores the rolling
               transcript into a stable risk score, scam type and kill-chain stage.

Protocol (browser <-> Cloud Run):
  -> {"type":"start","token":"<Firebase ID token>","lang":"ms","country":"MY","speak":true}
  -> binary frames: 16-bit PCM mono @ 16 kHz
  -> {"type":"stop"}
  <- {"type":"ready"} | transcript | signal | risk | alert | kawal_said | summary | error
  <- binary frames: Kawal's spoken warnings, 16-bit PCM mono @ 24 kHz
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from . import genai_client, store
from .agents import intel
from .auth import limiter, verify_token
from .config import get_settings
from .redact import redact_text
from .taxonomy import KILL_CHAIN_IDS, LANGS, SCAM_TYPES, TACTICS, clamp_enum, hotline

log = logging.getLogger(__name__)

SPEAK_THRESHOLD = 60
# Control tokens the native-audio model sometimes transcribes, e.g. "<no speech>{pause}".
_CONTROL = re.compile(r"<[^>]*>|\{[^}]*\}|<[^>]*$")


def clean_said(text: str) -> str:
    return re.sub(r"\s+", " ", _CONTROL.sub("", text)).strip()

FLAG_TOOL = types.FunctionDeclaration(
    name="flag_scam_signal",
    description="Report a scam tactic you just heard the CALLER use.",
    parameters_json_schema={
        "type": "object",
        "properties": {
            "tactic": {"type": "string", "enum": list(TACTICS)},
            "evidence": {"type": "string", "description": "Short quote from the call, original language."},
            "risk_score": {"type": "integer", "description": "Overall scam risk of the call so far, 0-100."},
        },
        "required": ["tactic", "evidence", "risk_score"],
    },
)

LIVE_SYSTEM = """You are Kawal, a silent anti-scam guardian. You are listening, through the USER's device,
to a phone call on speakerphone between the USER and an unknown CALLER. Languages may switch mid-call
(Malay, English, Mandarin, Cantonese, Tamil, Indonesian, Tagalog, Thai...).

1. Each time the CALLER uses a scam tactic, immediately call flag_scam_signal with the tactic, a short
   quote and your overall risk score so far. Flag each tactic once; flag again only if the risk rises.
2. Never speak to the CALLER, never answer questions, never role-play or continue the conversation.
   Never describe yourself or the monitoring process. Silence (no audio at all) is your default.
3. Stay completely silent while the risk score is below 70. Once it reaches 70, speak ONE short, calm
   sentence to the USER in {lang}: tell them it is a scam pattern and what to do now
   (hang up, do not transfer money or share codes, call {hotline}). Do not repeat yourself within 30 seconds.
4. If the call is legitimate (for example the caller tells the user to call the official number on their
   card and never asks for codes or transfers), stay silent and do not flag anything.
"""

SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "scam_type": {"type": "string", "enum": list(SCAM_TYPES)},
        "stage": {"type": "string", "enum": KILL_CHAIN_IDS},
        "tactics": {"type": "array", "maxItems": 6, "items": {
            "type": "object",
            "properties": {"tactic": {"type": "string", "enum": list(TACTICS)}, "evidence": {"type": "string"}},
            "required": ["tactic", "evidence"]}},
        "caller_claims_to_be": {"type": "string"},
        "advice": {"type": "string"},
    },
    "required": ["risk_score", "scam_type", "stage", "tactics", "caller_claims_to_be", "advice"],
}

SCORE_SYSTEM = """You score the scam risk of an in-progress phone call from its live transcript.
Be calibrated and evidence-based:
- A caller merely stating who they are (bank, courier, police) is NOT a tactic by itself and keeps risk
  at or below 30. It becomes authority_impersonation only when combined with accusations, threats,
  secrecy, or requests for money, codes, personal data or app installs.
- Only list a tactic when a quote clearly shows it. Ordinary scheduling or transaction details are not urgency.
- Legitimate calls that never ask for money, codes or app installs, or that tell the user to call the
  official number on their card, score below 15.
- Requests to move money to a 'safe account', share a TAC/OTP, keep secrets, or install apps, especially
  under time pressure, score above 85.
`advice` is one short sentence for the user in {lang}."""

# The deep path only adds tactic chips once the call is genuinely suspicious.
DEEP_SIGNAL_MIN_RISK = 50

SUMMARY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["scam", "suspicious", "likely_safe"]},
        "scam_type": {"type": "string", "enum": list(SCAM_TYPES)},
        "headline": {"type": "string"},
        "summary_en": {"type": "string"},
        "pattern_name": {"type": "string"},
        "user_message": {"type": "string"},
    },
    "required": ["verdict", "scam_type", "headline", "summary_en", "pattern_name", "user_message"],
}


class LiveGuardian:
    def __init__(self, ws: WebSocket, uid: str, lang: str, country: str, speak: bool, share: bool):
        self.ws, self.uid, self.lang, self.country = ws, uid, lang, country
        self.speak, self.share = speak, share
        self.s = get_settings()
        self.transcript: list[str] = []
        self.scored_len = 0
        self.flags: dict[str, dict] = {}
        self.live_risk = 0
        self.deep: dict = {}
        self.max_risk = 0
        self.last_alert = 0.0
        self.alerts = 0
        self.said = ""
        self.started = time.time()
        self.stopping = asyncio.Event()

    # ------------------------------------------------------------ helpers
    async def emit(self, payload: dict) -> None:
        with contextlib.suppress(Exception):
            await self.ws.send_text(json.dumps(payload, ensure_ascii=False))

    def risk(self) -> int:
        return max(self.live_risk, int(self.deep.get("risk_score", 0)))

    async def maybe_alert(self, text: str | None = None) -> None:
        r = self.risk()
        self.max_risk = max(self.max_risk, r)
        if r >= 70 and time.time() - self.last_alert > 25:
            self.last_alert = time.time()
            self.alerts += 1
            # Only borrow the deep scorer's advice if it agrees the call is high-risk.
            deep_agrees = int(self.deep.get("risk_score", 0)) >= 70
            advice = text or (self.deep.get("advice") if deep_agrees else "") or ""
            await self.emit({"type": "alert", "risk": r, "text": advice,
                             "hotline": hotline(self.country)})

    def live_config(self) -> types.LiveConnectConfig:
        hl = hotline(self.country)["primary"]
        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=LIVE_SYSTEM.replace("{lang}", LANGS.get(self.lang, "English")).replace("{hotline}", hl),
            tools=[types.Tool(function_declarations=[FLAG_TOOL])],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            # Lets the model decide NOT to respond - essential for a silent listener.
            proactivity=types.ProactivityConfig(proactive_audio=True),
            realtime_input_config=types.RealtimeInputConfig(
                # The caller keeps talking over warnings; Kawal must finish its sentence.
                activity_handling=types.ActivityHandling.NO_INTERRUPTION,
                automatic_activity_detection=types.AutomaticActivityDetection(
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    prefix_padding_ms=100,
                    silence_duration_ms=450,
                )
            ),
        )

    # ------------------------------------------------------------ loops
    async def pump_client(self, session) -> None:
        """Browser -> Gemini: forward PCM audio until the user stops."""
        deadline = self.started + self.s.live_max_seconds
        while time.time() < deadline:
            msg = await self.ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break
            if msg.get("bytes"):
                await session.send_realtime_input(
                    audio=types.Blob(data=msg["bytes"], mime_type="audio/pcm;rate=16000"))
            elif msg.get("text"):
                data = json.loads(msg["text"])
                if data.get("type") == "stop":
                    break
                if data.get("type") == "speak":
                    self.speak = bool(data.get("value"))
        with contextlib.suppress(Exception):
            await session.send_realtime_input(audio_stream_end=True)

    async def pump_model(self, session) -> None:
        """Gemini -> browser: transcripts, tool calls (signals) and spoken warnings."""
        while not self.stopping.is_set():
            async for m in session.receive():
                if m.tool_call:
                    responses = []
                    for fc in m.tool_call.function_calls:
                        args = fc.args or {}
                        tactic = args.get("tactic")
                        if tactic in TACTICS:
                            self.live_risk = max(self.live_risk, int(args.get("risk_score", 0)))
                            sig = {"tactic": tactic, "label": TACTICS[tactic], "evidence": args.get("evidence", ""),
                                   "risk": self.live_risk, "t": round(time.time() - self.started, 1), "by": "live"}
                            self.flags.setdefault(tactic, sig)
                            await self.emit({"type": "signal", **sig})
                            await self.maybe_alert()
                        responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"ok": True}))
                    await session.send_tool_response(function_responses=responses)
                sc = m.server_content
                if not sc:
                    continue
                if sc.input_transcription and sc.input_transcription.text:
                    txt = sc.input_transcription.text
                    self.transcript.append(txt)
                    await self.emit({"type": "transcript", "text": txt, "t": round(time.time() - self.started, 1)})
                # Kawal's voice is gated: it may only speak once the call is clearly risky.
                gate_open = self.risk() >= SPEAK_THRESHOLD
                if sc.output_transcription and sc.output_transcription.text:
                    self.said += sc.output_transcription.text
                    text = clean_said(self.said)
                    if text and gate_open:
                        await self.emit({"type": "kawal_said", "text": text})
                if sc.turn_complete:
                    self.said = ""
                if sc.model_turn and self.speak and gate_open:
                    for p in sc.model_turn.parts:
                        if p.inline_data and p.inline_data.data:
                            with contextlib.suppress(Exception):
                                await self.ws.send_bytes(p.inline_data.data)

    async def score_loop(self) -> None:
        """Deep path: re-score the transcript whenever it has grown."""
        system = SCORE_SYSTEM.replace("{lang}", LANGS.get(self.lang, "English"))
        while not self.stopping.is_set():
            await asyncio.sleep(2.5)
            text = " ".join(self.transcript)
            if len(text) - self.scored_len < 25:
                continue
            self.scored_len = len(text)
            try:
                resp = await genai_client.generate(
                    self.s.model_lite, f"Live call transcript so far:\n{text[-6000:]}",
                    genai_client.json_config(SCORE_SCHEMA, system=system, thinking="MINIMAL"))
                self.deep = genai_client.parse_json(resp)
            except Exception:
                log.exception("deep scorer failed")
                continue
            tactics = []
            for t in self.deep.get("tactics", []):
                if t.get("tactic") in TACTICS:
                    tactics.append({**t, "label": TACTICS[t["tactic"]]})
                    if t["tactic"] not in self.flags and self.deep.get("risk_score", 0) >= DEEP_SIGNAL_MIN_RISK:
                        sig = {"tactic": t["tactic"], "label": TACTICS[t["tactic"]], "evidence": t.get("evidence", ""),
                               "risk": self.deep.get("risk_score", 0), "t": round(time.time() - self.started, 1),
                               "by": "deep"}
                        self.flags[t["tactic"]] = sig
                        await self.emit({"type": "signal", **sig})
            scam_type = clamp_enum(self.deep.get("scam_type"), SCAM_TYPES, "other")
            await self.emit({"type": "risk", "risk": self.risk(), "deepRisk": self.deep.get("risk_score", 0),
                             "liveRisk": self.live_risk, "scamType": scam_type, "scamTypeLabel": SCAM_TYPES[scam_type],
                             "stage": clamp_enum(self.deep.get("stage"), KILL_CHAIN_IDS, "contact"),
                             "claims": self.deep.get("caller_claims_to_be", ""), "advice": self.deep.get("advice", "")})
            await self.maybe_alert()

    async def summarise(self) -> None:
        text = " ".join(self.transcript).strip()
        if len(text) < 20:
            await self.emit({"type": "summary", "verdict": "likely_safe", "headline": "", "userMessage": "",
                             "maxRisk": self.max_risk, "signals": list(self.flags.values()), "durationS": 0})
            return
        resp = await genai_client.generate(
            self.s.model_lite,
            (f"Phone call transcript:\n{text[-8000:]}\nTactics flagged live: {list(self.flags)}. "
                      f"Peak risk {self.max_risk}. Write user_message and headline in {LANGS.get(self.lang)}; "
                      "summary_en and pattern_name in generic English without names or numbers."),
            genai_client.json_config(SUMMARY_SCHEMA, thinking="LOW"))
        out = genai_client.parse_json(resp)
        scam_type = clamp_enum(out.get("scam_type"), SCAM_TYPES, "other")
        duration = round(time.time() - self.started)
        await self.emit({"type": "summary", "verdict": out.get("verdict"), "headline": out.get("headline"),
                         "userMessage": out.get("user_message"), "scamType": scam_type,
                         "scamTypeLabel": SCAM_TYPES[scam_type], "maxRisk": self.max_risk,
                         "signals": list(self.flags.values()), "durationS": duration,
                         "hotline": hotline(self.country)})
        # Persist only the redacted outcome - never audio, never the transcript.
        session_doc = {"startedAt": store.now(), "durationS": duration, "lang": self.lang, "country": self.country,
                       "maxRisk": self.max_risk, "verdict": out.get("verdict"), "scamType": scam_type,
                       "tactics": sorted(self.flags), "warned": self.alerts > 0,
                       "summary": redact_text(out.get("summary_en", ""))[:600]}
        await store.save_live_session(session_doc)
        if self.share and out.get("verdict") in ("scam", "suspicious"):
            it = await intel.run(summary_en=out.get("summary_en", ""), scam_type=scam_type,
                                 pattern_name=out.get("pattern_name", ""), indicators=[])
            await store.save_report({
                "verdict": out["verdict"], "riskScore": self.max_risk, "scamType": scam_type,
                "channel": "phone_call", "country": self.country, "lang": self.lang, "source": "live",
                "summary": session_doc["summary"], "headline": redact_text(out.get("pattern_name", ""))[:140],
                "tactics": sorted(self.flags),
                "killChainStage": clamp_enum(self.deep.get("stage"), KILL_CHAIN_IDS, "pressure"),
                "impersonated": "", "synthetic": False}, it["vector"], [], it["campaign"])

    # ------------------------------------------------------------ entry
    async def run(self) -> None:
        try:
            async with genai_client.live_client().aio.live.connect(model=self.s.model_live,
                                                                   config=self.live_config()) as session:
                await self.emit({"type": "ready", "model": self.s.model_live})
                tasks = [asyncio.create_task(self.pump_client(session)),
                         asyncio.create_task(self.pump_model(session)),
                         asyncio.create_task(self.score_loop())]
                await tasks[0]  # ends when the user stops or disconnects
                await asyncio.sleep(1.5)  # let the last transcript/tool calls arrive
                self.stopping.set()
                for t in tasks[1:]:
                    t.cancel()
                try:
                    await self.summarise()
                except Exception:
                    log.exception("summary failed")
        except WebSocketDisconnect:
            pass
        except Exception as exc:
            log.exception("live session failed")
            await self.emit({"type": "error", "message": f"Live session error: {type(exc).__name__}"})


async def handle(ws: WebSocket) -> None:
    s = get_settings()
    origin = ws.headers.get("origin")
    if origin and origin not in s.origins:
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        start = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=10))
        user = verify_token(start.get("token"))
        limiter.check(f"live:{user.uid}", 8, window=600)
    except Exception:
        await ws.send_text(json.dumps({"type": "error", "message": "Unauthorized or rate limited"}))
        await ws.close(code=1008)
        return
    lang = clamp_enum(start.get("lang"), LANGS, "en")
    guardian = LiveGuardian(ws, user.uid, lang, (start.get("country") or "MY").upper()[:2],
                            speak=bool(start.get("speak", True)), share=bool(start.get("share", True)))
    await guardian.run()
    with contextlib.suppress(Exception):
        await ws.close()
