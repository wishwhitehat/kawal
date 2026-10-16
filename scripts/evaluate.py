"""Offline benchmark for the Scam Check triage agent.

A held-out, hand-labelled set (separate from the seed data) of scam and
*tricky legitimate* messages across EN / BM / 中文 / Bahasa Indonesia. We count
"scam" and "suspicious" as a positive (Kawal warns the user) and report
accuracy, precision, recall, false-positive rate and latency.

    PROJECT_ID=<project> python scripts/evaluate.py [--model gemini-3.8-flash] [--out docs/benchmark.json]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

# label: 1 = scam (Kawal should warn), 0 = legitimate (Kawal should not)
CASES: list[tuple[int, str, str, str]] = [
    # ---- scams ----------------------------------------------------------
    (1, "MY", "ms", "Akaun Bank Islam anda telah disekat. Sila log masuk di bislam-semakan.com untuk aktifkan semula dalam masa 1 jam."),
    (1, "MY", "en", "Congratulations! Your number won RM10,000 in the Petronas Mesra lucky draw. Pay RM150 processing fee to claim, WhatsApp 011-5523 9087."),
    (1, "MY", "ms", "Saya dari JPJ. Saman tertunggak RM300 anda akan dibawa ke mahkamah. Bayar segera di jpj-saman-online.site"),
    (1, "MY", "en", "Hi, this is Agent Wong from Touch 'n Go. Your eWallet is linked to a fraud case. Install the 'TNG Secure' app from this link so we can protect your balance."),
    (1, "MY", "zh", "您好，我是马来西亚国家银行的职员。您的账户涉及洗钱，请将存款转到我们的安全账户以配合调查，不要告诉任何人。"),
    (1, "SG", "en", "SingPost: Your package could not be delivered due to an incomplete address. Update details and pay S$1.80 at singpost-redelivery.info"),
    (1, "SG", "en", "Dear customer, OCBC has detected unauthorised access. Reply with your OTP to cancel the S$2,450 transaction immediately."),
    (1, "SG", "zh", "兼职招聘：在家给酒店点赞，每单佣金S$5，日赚300新元。先充值100 USDT开通高级任务，联系Telegram @HotelTaskSG。"),
    (1, "SG", "en", "Hi, I'm Sarah, we matched on Coffee Meets Bagel. My uncle is a crypto analyst, I made $40k last month on his platform. Let me show you, it's very safe."),
    (1, "ID", "id", "BCA: Tarif transfer berubah menjadi Rp150.000/bulan. Jika tidak setuju, isi formulir di bca-tarif-baru.xyz sebelum hari ini."),
    (1, "ID", "id", "Mama, ini aku ganti nomor. HP-ku hilang. Tolong transfer Rp2 juta ke rekening teman aku dulu ya, darurat banget."),
    (1, "ID", "id", "Selamat, Anda terpilih jadi reseller TikTok Shop! Gaji Rp500 ribu per hari, cukup deposit Rp200 ribu untuk aktivasi akun."),
    (1, "PH", "en", "Maya: Your account will be deactivated. Confirm your MPIN at maya-ph-verify.com to keep your balance."),
    (1, "TH", "en", "Thailand Post: Your parcel contains illegal items. Call our customs officer now and transfer a guarantee deposit to avoid prosecution."),
    (1, "AU", "en", "myGov: You are eligible for a tax refund of $812.40. Claim at mygov-refund-au.com within 48 hours."),
    (1, "IN", "en", "This is TRAI. Your mobile number will be disconnected in 2 hours due to illegal activity. Press 9 to speak to the cyber crime officer."),
    (1, "HK", "zh", "【香港海关】您的包裹涉嫌走私，请立即联络我们的警官核实身份，并将资金转到监管账户。"),
    (1, "MY", "en", "Investment opportunity: Bursa-listed insider tips, guaranteed 20% weekly returns. Join our Telegram and deposit via USDT only."),
    (1, "MY", "ms", "Pinjaman Mudah Lulus! Tiada dokumen. Hanya bayar duti setem RM200 dahulu ke akaun 1623 4401 9987 dan wang akan dimasukkan dalam 1 jam."),
    (1, "SG", "en", "This is the Ministry of Manpower. Your work pass will be cancelled unless you pay a S$600 administrative fine via the link today."),
    # ---- legitimate (tricky) ---------------------------------------------
    (0, "MY", "en", "Maybank: RM120.00 has been debited from your account for a DuitNow transfer to ALI BIN AHMAD on 15/10. If this wasn't you, call the number on the back of your card."),
    (0, "MY", "ms", "Pos Malaysia: Bungkusan EN123456789MY anda telah dihantar dan diterima pada 14/10. Terima kasih kerana menggunakan Pos Laju."),
    (0, "MY", "en", "Your Grab verification code is 482913. Do not share this code with anyone, including Grab staff."),
    (0, "MY", "zh", "妈，我今天加班，晚饭不用等我，大概九点到家。"),
    (0, "SG", "en", "DBS: Your OTP for the transaction of S$58.20 at NTUC FairPrice is 773120. Never share your OTP. If you did not initiate this, call 1800 111 1111."),
    (0, "SG", "en", "Reminder: Your dental appointment at Raffles Medical is tomorrow at 10:30am. Reply C to confirm or call us to reschedule."),
    (0, "ID", "id", "Tokopedia: Pesanan INV/2026/10/1234 sudah dikirim oleh penjual. Lacak di aplikasi Tokopedia."),
    (0, "PH", "en", "Hi team, the quarterly report deadline has moved to Friday. Please upload your sections to the shared drive by Thursday noon. Thanks, Marco"),
    (0, "MY", "en", "Shopee: Your order 2510ABC has been delivered. Rate your purchase in the Shopee app to earn coins."),
    (0, "AU", "en", "Hi, it's Dr Patel's clinic. Your blood test results are ready. Please book a follow-up appointment through our usual online booking page or call the clinic."),
]


async def run(model: str | None) -> dict:
    if model:
        os.environ["MODEL_FLASH"] = model
    from app.agents import triage  # imported after MODEL_FLASH is set

    sem = asyncio.Semaphore(3)
    rows = []

    async def one(label: int, country: str, lang: str, text: str) -> None:
        async with sem:
            t = time.perf_counter()
            out = await triage.run(text=text, media=[], lang=lang, country=country)
            ms = (time.perf_counter() - t) * 1000
        pred = int(out["verdict"] in ("scam", "suspicious"))
        rows.append({"label": label, "pred": pred, "verdict": out["verdict"], "risk": out["risk_score"],
                     "type": out["scam_type"], "ms": round(ms), "lang": lang, "text": text[:70]})
        mark = "✓" if pred == label else "✗"
        print(f"{mark} {lang} label={label} verdict={out['verdict']:<11} risk={out['risk_score']:>3} {ms:6.0f}ms  {text[:60]}",
              flush=True)

    await asyncio.gather(*(one(*c) for c in CASES))
    tp = sum(r["label"] == 1 and r["pred"] == 1 for r in rows)
    tn = sum(r["label"] == 0 and r["pred"] == 0 for r in rows)
    fp = sum(r["label"] == 0 and r["pred"] == 1 for r in rows)
    fn = sum(r["label"] == 1 and r["pred"] == 0 for r in rows)
    lat = sorted(r["ms"] for r in rows)
    return {
        "model": os.environ.get("MODEL_FLASH", "gemini-3.8-flash"),
        "n": len(rows), "scams": tp + fn, "legit": tn + fp,
        "accuracy": round((tp + tn) / len(rows), 3),
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / (tp + fn), 3) if tp + fn else None,
        "false_positive_rate": round(fp / (fp + tn), 3) if fp + tn else None,
        "latency_ms": {"p50": statistics.median(lat), "p95": lat[int(0.95 * (len(lat) - 1))], "max": lat[-1]},
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
        "rows": sorted(rows, key=lambda r: -r["label"]),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--out")
    args = ap.parse_args()
    res = asyncio.run(run(args.model))
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))
    if args.out:
        pathlib.Path(args.out).write_text(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
