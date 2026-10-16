"""PII redaction and privacy-preserving indicator fingerprints.

Kawal stores *patterns*, not people: raw messages, audio and screenshots are
never persisted. Phone numbers, bank accounts and wallets are reduced to a
keyed HMAC fingerprint (so repeat reports can be counted) plus a masked label.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from urllib.parse import urlparse

CALLING_CODES = {"MY": "60", "SG": "65", "ID": "62", "PH": "63", "TH": "66", "VN": "84",
                 "AU": "61", "IN": "91", "HK": "852", "TW": "886", "JP": "81", "KR": "82"}

URL_RE = re.compile(
    r"\b(?:https?://|www\.)[^\s<>\"']+"
    r"|\b[a-z0-9][a-z0-9-]{1,62}\.(?:com|net|org|info|xyz|top|shop|site|online|club|vip|cc|me|io|my|sg|id|ph"
    r"|th|vn|link|app|live|icu|buzz)(?:/[^\s<>\"']*)?",
    re.I,
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"(?<![\w])(?:\+?\d[\d\s().-]{7,16}\d)(?![\w])")
WALLET_RE = re.compile(r"\b(?:0x[a-fA-F0-9]{40}|T[1-9A-HJ-NP-Za-km-z]{33}|(?:bc1|[13])[a-zA-HJ-NP-Z0-9]{25,59})\b")


@dataclass(frozen=True)
class Indicator:
    kind: str  # phone | account | url | domain | email | wallet
    value: str  # normalised raw value - never persisted
    masked: str

    def fingerprint(self, pepper: str) -> str:
        msg = f"{self.kind}:{self.value}".encode()
        return hmac.new(pepper.encode(), msg, hashlib.sha256).hexdigest()[:32]


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def normalise_phone(raw: str, country: str = "MY") -> str:
    d = _digits(raw)
    if raw.strip().startswith("+"):
        return d
    code = CALLING_CODES.get(country.upper(), "")
    if d.startswith("00"):
        return d[2:]
    if d.startswith("0") and code:
        return code + d[1:]
    return d


def mask_digits(d: str, keep_start: int = 4, keep_end: int = 2) -> str:
    if len(d) <= keep_start + keep_end:
        return "*" * len(d)
    return d[:keep_start] + "*" * (len(d) - keep_start - keep_end) + d[-keep_end:]


def domain_of(url: str) -> str:
    u = url if "://" in url else "http://" + url
    host = (urlparse(u).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _luhn_ok(d: str) -> bool:
    total, alt = 0, False
    for ch in reversed(d):
        n = int(ch)
        if alt:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
        alt = not alt
    return total % 10 == 0


def classify_number(raw: str, country: str = "MY") -> Indicator | None:
    d = _digits(raw)
    if len(d) < 8:
        return None
    looks_phone = raw.strip().startswith(("+", "0")) and 9 <= len(d) <= 15
    if 13 <= len(d) <= 19 and _luhn_ok(d) and not looks_phone:
        return Indicator("account", d, "card ****" + d[-4:])
    if looks_phone:
        n = normalise_phone(raw, country)
        return Indicator("phone", n, "+" + mask_digits(n))
    if 8 <= len(d) <= 18:
        return Indicator("account", d, "acct ****" + d[-4:])
    return None


def extract_indicators(text: str, country: str = "MY") -> list[Indicator]:
    """Find phones, accounts, URLs, emails and wallets in free text."""
    found: dict[tuple[str, str], Indicator] = {}
    text = text or ""
    for m in URL_RE.finditer(text):
        dom = domain_of(m.group(0))
        if dom:
            found[("domain", dom)] = Indicator("domain", dom, dom)
    for m in EMAIL_RE.finditer(text):
        e = m.group(0).lower()
        user, _, dom = e.partition("@")
        found[("email", e)] = Indicator("email", e, f"{user[:2]}***@{dom}")
    for m in WALLET_RE.finditer(text):
        w = m.group(0)
        found[("wallet", w)] = Indicator("wallet", w, w[:6] + "…" + w[-4:])
    scrubbed = URL_RE.sub(" ", EMAIL_RE.sub(" ", text))
    for m in PHONE_RE.finditer(scrubbed):
        ind = classify_number(m.group(0), country)
        if ind:
            found[(ind.kind, ind.value)] = ind
    return list(found.values())


def indicator_from_model(kind: str, value: str, country: str = "MY") -> Indicator | None:
    """Normalise an indicator the model extracted from an image/audio."""
    value = (value or "").strip()
    if not value:
        return None
    if kind in ("url", "domain"):
        dom = domain_of(value)
        return Indicator("domain", dom, dom) if dom else None
    if kind == "email":
        found = extract_indicators(value, country)
        return found[0] if found else None
    if kind == "wallet":
        return Indicator("wallet", value, value[:6] + "…" + value[-4:])
    if kind in ("phone", "account"):
        ind = classify_number(value, country)
        if ind and kind == "phone" and ind.kind != "phone":
            n = normalise_phone(value, country)
            return Indicator("phone", n, "+" + mask_digits(n))
        return ind
    return None


def extract_urls(text: str) -> list[str]:
    """Full URLs (scheme added if missing) - used transiently for Web Risk, never stored."""
    out = []
    for m in URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(".,;:!?)」】")
        out.append(u if "://" in u else "http://" + u)
    return list(dict.fromkeys(out))


def redact_text(text: str) -> str:
    """Replace contact details in free text with placeholders."""
    text = EMAIL_RE.sub("[EMAIL]", text or "")
    text = URL_RE.sub(lambda m: f"[LINK:{domain_of(m.group(0))}]", text)
    text = WALLET_RE.sub("[WALLET]", text)
    return PHONE_RE.sub(lambda m: "[NUMBER]" if len(_digits(m.group(0))) >= 8 else m.group(0), text)
