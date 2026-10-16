"""Generate the synthetic scam-call samples used by the Live Guardian demo.

Every line is voiced separately with Gemini TTS and stitched together with a
short silence, so the result has natural turn-taking (which is also what the
Live API's voice-activity detection expects from a real phone call).

All dialogue below is fictional and written by the Kawal team for testing.

Usage:
    python scripts/generate_sample_calls.py --project <PROJECT_ID>     # needs ffmpeg
"""

from __future__ import annotations

import argparse
import io
import pathlib
import shutil
import subprocess
import tempfile
import wave

from google import genai
from google.genai import types

OUT_DIR = pathlib.Path(__file__).resolve().parents[1] / "frontend" / "public" / "samples"
RATE = 24_000
GAP_SECONDS = 0.9

VOICES = {"caller": "Charon", "victim": "Kore", "agent": "Puck"}

SAMPLES: dict[str, list[tuple[str, str]]] = {
    # Bahasa Melayu - "Macau scam": fake police + "safe account" at the central bank.
    "macau-scam-ms": [
        ("caller", "Hello, selamat petang. Saya Inspektor Razak dari Ibu Pejabat Polis Bukit Aman, bahagian jenayah komersial."),
        ("victim", "Ya? Kenapa ya, tuan?"),
        ("caller", "Nama puan ada dalam siasatan kes pengubahan wang haram. Akaun bank puan digunakan untuk terima dua ratus ribu ringgit."),
        ("victim", "Apa? Saya tak tahu apa-apa pun!"),
        ("caller", "Ini kes sangat serius. Jangan beritahu sesiapa, termasuk keluarga. Kalau tidak, puan boleh ditangkap hari ini juga."),
        ("caller", "Untuk lindungi duit puan, puan perlu pindahkan semua simpanan ke akaun selamat Bank Negara yang saya berikan."),
        ("victim", "Berapa saya perlu pindah?"),
        ("caller", "Semua sekali. Sekarang juga, dalam masa tiga puluh minit. Jangan letak telefon."),
    ],
    # English - fake bank fraud team asking for the TAC and a remote-access app.
    "bank-impersonation-en": [
        ("caller", "Good morning, this is Daniel from the fraud prevention team at your bank. We detected a suspicious login to your account from Vietnam."),
        ("victim", "Oh no. What should I do?"),
        ("caller", "Don't worry, I can secure it for you right now. You will receive a six digit code by SMS. Please read it to me so I can block the transaction."),
        ("victim", "Okay, it says four eight two..."),
        ("caller", "Good. Next, please install the app called Secure Assist from the link I am sending. It lets our technician protect your phone remotely."),
        ("caller", "You must do this in the next ten minutes, otherwise the hacker will empty your savings."),
    ],
    # Mandarin - courier parcel + transfer to fake mainland police.
    "parcel-police-zh": [
        ("caller", "您好，这里是顺丰快递。您有一个寄往上海的包裹被海关扣留了，里面发现了十二本假护照。"),
        ("victim", "什么？我没有寄过包裹啊。"),
        ("caller", "那您的身份可能被盗用了。我现在帮您转接上海公安局的王警官。"),
        ("caller", "我是王警官。你涉嫌洗钱案件，现在有逮捕令。这件事是保密的，不可以告诉家人。"),
        ("victim", "我该怎么办？"),
        ("caller", "为了证明你的清白，你需要把账户里所有的钱转到我们的安全监管账户，调查结束后会退还给你。今天之内必须完成。"),
    ],
    # English - a legitimate bank call (control sample: should stay low risk).
    "legit-bank-en": [
        ("agent", "Hello, this is Aisyah from the card services team. I'm calling about a declined card payment at an electronics store at two p.m. today."),
        ("victim", "Yes, that was me. I was buying a laptop."),
        ("agent", "Thank you. I won't ask for your PIN, password or any one-time code. If you'd like to verify me, you can hang up and call the number on the back of your card."),
        ("victim", "That's fine, I'll call the hotline later."),
        ("agent", "Of course. Your card is not blocked, and you can retry the purchase anytime. Have a good day."),
    ],
}


def synth(client: genai.Client, model: str, text: str, voice: str) -> bytes:
    resp = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    blob = resp.candidates[0].content.parts[0].inline_data
    if blob.mime_type == "audio/wav":
        with wave.open(io.BytesIO(blob.data)) as w:
            if w.getframerate() != RATE or w.getsampwidth() != 2 or w.getnchannels() != 1:
                raise ValueError(f"unexpected TTS format: {w.getparams()}")
            return w.readframes(w.getnframes())
    return blob.data  # raw 16-bit PCM @ 24 kHz


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--location", default="global")
    ap.add_argument("--model", default="gemini-3.8-flash-tts")
    ap.add_argument("--only", nargs="*", help="sample ids to (re)generate")
    args = ap.parse_args()

    client = genai.Client(vertexai=True, project=args.project, location=args.location)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    gap = b"\x00\x00" * int(RATE * GAP_SECONDS)

    for sample_id, lines in SAMPLES.items():
        if args.only and sample_id not in args.only:
            continue
        pcm = bytearray(gap)
        for speaker, text in lines:
            pcm += synth(client, args.model, text, VOICES[speaker]) + gap
        path = OUT_DIR / f"{sample_id}.m4a"
        with tempfile.TemporaryDirectory() as tmp:
            wav = pathlib.Path(tmp) / "call.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(bytes(pcm))
            # AAC keeps each sample around 300 KB instead of 2 MB of WAV.
            subprocess.run([shutil.which("ffmpeg") or "ffmpeg", "-y", "-loglevel", "error", "-i", str(wav),
                            "-c:a", "aac", "-b:a", "64k", str(path)], check=True)
        print(f"wrote {path.name}: {len(pcm) / 2 / RATE:.1f}s")


if __name__ == "__main__":
    main()
