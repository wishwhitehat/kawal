"""Shared scam taxonomy: scam types, persuasion tactics, kill-chain stages, hotlines.

Keeping this deterministic (not generated) means hotline numbers and labels
shown to a frightened user never depend on a model's memory.
"""

SCAM_TYPES: dict[str, str] = {
    "authority_impersonation": "Government / police impersonation (e.g. Macau scam)",
    "bank_impersonation": "Bank or payment-provider impersonation",
    "parcel_courier": "Parcel / courier / customs scam",
    "investment": "Investment, crypto or forex scam",
    "job_task": "Job or 'like-and-earn' task scam",
    "romance": "Romance or friendship scam",
    "ecommerce": "Online shopping / marketplace scam",
    "phishing": "Phishing link or fake login page",
    "loan": "Loan or debt-relief scam",
    "prize_lottery": "Prize, lottery or giveaway scam",
    "family_emergency": "Family-in-trouble / fake-friend call",
    "tech_support": "Tech-support or malware / remote-access scam",
    "deepfake_voice": "Deepfake voice or video impersonation",
    "other": "Other / unclear",
    "none": "No scam detected",
}

TACTICS: dict[str, str] = {
    "authority_impersonation": "Claims to be police, a court, a regulator or a bank",
    "urgency_pressure": "Creates time pressure: act now, minutes left",
    "secrecy_isolation": "Tells you not to tell family, friends or the bank",
    "fear_threat": "Threatens arrest, fines, account freeze or harm",
    "payment_request": "Asks you to transfer money, buy gift cards or crypto",
    "safe_account": "Asks you to move money to a 'safe' or 'holding' account",
    "credential_request": "Asks for passwords, PIN, TAC/OTP or card details",
    "remote_access": "Asks you to install an app or share your screen",
    "too_good_to_be_true": "Promises guaranteed returns, prizes or easy money",
    "emotional_manipulation": "Plays on love, sympathy, guilt or excitement",
    "suspicious_link": "Contains a link to an unofficial or look-alike website",
    "spoofed_identity": "Sender identity or number looks spoofed or inconsistent",
}

# A scam "kill chain" - where in the attack the victim currently is.
KILL_CHAIN: list[dict[str, str]] = [
    {"id": "contact", "label": "First contact"},
    {"id": "hook", "label": "Hook / pretext"},
    {"id": "pressure", "label": "Pressure & isolation"},
    {"id": "extraction", "label": "Money or data request"},
    {"id": "cashout", "label": "Cash-out / mule"},
]
KILL_CHAIN_IDS = [s["id"] for s in KILL_CHAIN]

VERDICTS = ["scam", "suspicious", "likely_safe"]
CHANNELS = ["phone_call", "sms", "whatsapp", "telegram", "email", "social_media", "website", "marketplace",
            "in_person", "unknown"]

# Official reporting channels per country (JAPAC first). Verified Oct 2026.
HOTLINES: dict[str, dict] = {
    "MY": {"name": "Malaysia", "primary": "NSRC 997", "tel": "997",
           "steps": ["Call the National Scam Response Centre at 997 immediately if money was sent.",
                     "Call your bank's 24h fraud hotline and use the bank app 'kill switch' to freeze your account.",
                     "Check numbers and accounts at semakmule.rmp.gov.my."]},
    "SG": {"name": "Singapore", "primary": "ScamShield Helpline 1799", "tel": "1799",
           "steps": ["Call the ScamShield Helpline at 1799 for advice.",
                     "Call your bank immediately and use its emergency self-service 'kill switch'.",
                     "Report at police.gov.sg/i-witness or call 1800-255-0000."]},
    "ID": {"name": "Indonesia", "primary": "Indonesia Anti-Scam Centre (IASC)", "tel": "157",
           "steps": ["Report to the Indonesia Anti-Scam Centre at iasc.ojk.go.id or call OJK at 157.",
                     "Contact your bank to block the transfer.",
                     "Check accounts and numbers at cekrekening.id."]},
    "PH": {"name": "Philippines", "primary": "CICC Hotline 1326", "tel": "1326",
           "steps": ["Call the CICC Inter-Agency Response Center at 1326.",
                     "Contact your bank or e-wallet provider to freeze the transfer.",
                     "Report to the PNP Anti-Cybercrime Group."]},
    "TH": {"name": "Thailand", "primary": "AOC Hotline 1441", "tel": "1441",
           "steps": ["Call the Anti Online Scam Operation Center at 1441.",
                     "Ask your bank to suspend the receiving account.",
                     "File a report at thaipoliceonline.go.th."]},
    "VN": {"name": "Vietnam", "primary": "Police 113", "tel": "113",
           "steps": ["Call the police at 113.", "Contact your bank to block the transaction.",
                     "Report the scam at canhbao.khonggianmang.gov.vn."]},
    "AU": {"name": "Australia", "primary": "Scamwatch / IDCARE 1800 595 160", "tel": "1800595160",
           "steps": ["Contact your bank immediately.", "Report at scamwatch.gov.au and cyber.gov.au.",
                     "Call IDCARE on 1800 595 160 for identity support."]},
    "IN": {"name": "India", "primary": "Cyber Crime Helpline 1930", "tel": "1930",
           "steps": ["Call 1930 immediately (within the 'golden hour').", "Report at cybercrime.gov.in.",
                     "Inform your bank to freeze the transaction."]},
    "HK": {"name": "Hong Kong", "primary": "Anti-Scam Helpline 18222", "tel": "18222",
           "steps": ["Call the Anti-Scam Helpline 18222.", "Check numbers with Scameter.",
                     "Contact your bank immediately."]},
    "TW": {"name": "Taiwan", "primary": "Anti-Fraud Hotline 165", "tel": "165",
           "steps": ["Call the 165 anti-fraud hotline.", "Contact your bank to stop the transfer."]},
    "JP": {"name": "Japan", "primary": "Police consultation #9110", "tel": "#9110",
           "steps": ["Call the police consultation line #9110 (or 110 in an emergency).",
                     "Contact your bank immediately."]},
    "KR": {"name": "South Korea", "primary": "Police 112 / FSS 1332", "tel": "112",
           "steps": ["Call 112 to request an account payment suspension.", "Report to the FSS at 1332."]},
}
DEFAULT_COUNTRY = "MY"

LANGS = {"en": "English", "ms": "Bahasa Melayu", "zh": "Simplified Chinese"}


def hotline(country: str | None) -> dict:
    code = (country or DEFAULT_COUNTRY).upper()
    data = HOTLINES.get(code, HOTLINES[DEFAULT_COUNTRY])
    return {"country": code if code in HOTLINES else DEFAULT_COUNTRY, **data}


def clamp_enum(value: str | None, allowed, default: str) -> str:
    return value if value in allowed else default
