"""Seed the intel store with SYNTHETIC scam reports so the console has history.

Every message below was written by the Kawal team to mirror publicly documented
scam patterns in Asia-Pacific. Phone numbers, accounts and domains are made up.
Reports are run through the real pipeline (Gemini triage -> embeddings ->
campaign clustering) and stored with `synthetic: true` / `source: "seed"`.

Run with the production pepper so fingerprints match live traffic:
    INDICATOR_PEPPER=$(gcloud secrets versions access latest --secret kawal-indicator-pepper) \\
    PROJECT_ID=<project> python scripts/seed_intel.py
"""

from __future__ import annotations

import asyncio
import datetime as dt
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))

from app import pipeline  # noqa: E402

# (country, days_ago, text). Repeated numbers/domains are deliberate: they power
# the "reported N times" signal and campaign clustering.
SEEDS: list[tuple[str, int, str]] = [
    # --- Malaysia ----------------------------------------------------------
    ("MY", 2, "LHDN: Tahniah! Anda layak menerima bayaran balik cukai RM980.20. Kemas kini akaun bank anda di https://lhdn-refund-claim.xyz/semak dalam masa 24 jam."),
    ("MY", 5, "LHDN NOTIS: Bayaran balik cukai anda RM1,412 tertangguh. Sahkan butiran perbankan di lhdn-refund-claim.xyz sebelum tamat tempoh."),
    ("MY", 1, "Hi dear! Shopee Marketing is hiring part-time. Like products & earn RM300-800/day. Registration fee RM50 only. WhatsApp +60 11-2345 6789 now!"),
    ("MY", 3, "Kerja sambilan dari rumah! Tekan 'like' video TikTok dapat RM15 setiap tugasan. Deposit RM100 untuk buka akaun misi. Hubungi +60 11-2345 6789"),
    ("MY", 6, "Hello, I am Mandy from Lazada HR. Simple online task, daily salary RM500. Need to top up RM200 to unlock VIP tasks. Contact +60 11-2345 6789"),
    ("MY", 0, "Someone called saying they are from Pos Malaysia, a parcel under my IC had 20 fake passports, then transferred me to 'Inspector Lim' from Bukit Aman who said to move my savings to a safe account at Bank Negara."),
    ("MY", 2, "Panggilan dari 'pegawai Bank Negara' kata akaun saya terlibat kes pengubahan wang haram, suruh pindah semua duit ke akaun amanah 7612 3398 1021 untuk siasatan."),
    ("MY", 8, "Got a call from a 'police officer' with a video call in uniform, said I have an arrest warrant for money laundering, must not tell family, and transfer RM30,000 to clear my name."),
    ("MY", 4, "Join our VIP WhatsApp group! AI gold trading robot gives guaranteed 30% monthly profit. Minimum invest RM1,000, withdraw anytime. Register at goldbot-asia.vip"),
    ("MY", 11, "Pelaburan patuh syariah, pulangan tetap 5% seminggu! Ramai dah untung. Masukkan RM3,000 ke akaun 5512 0098 7765 Maybank atas nama Syarikat Mega Untung."),
    ("MY", 9, "Pinjaman peribadi tanpa CTOS/CCRIS, lulus dalam 24 jam! Bayar yuran guaman RM350 dahulu sebelum pengeluaran. WhatsApp 017-889 2214."),
    ("MY", 1, "【顺丰速运】您的包裹因地址不详无法派送，请于24小时内访问 sf-redelivery-my.top 更新地址并支付 RM3.50 重新派送费。"),
    ("MY", 3, "Pos Malaysia: Your parcel is on hold due to unpaid fee of RM2.99. Pay now at poslaju-redeliver.top to avoid return."),
    ("MY", 0, "Pos Malaysia: Bungkusan anda tertahan. Bayar caj penghantaran RM1.99 di poslaju-redeliver.top dalam 12 jam."),
    ("MY", 7, "Maybank2u: Your account will be suspended today due to incomplete verification. Login to m2u-secure-login.com to reactivate."),
    ("MY", 2, "KWSP: Pengeluaran khas RM2,000 kini dibuka! Mohon segera di kwsp-i-akaun.online sebelum 31 Oktober. Masukkan nombor TAC untuk pengesahan."),
    ("MY", 14, "My dear, I'm a US army doctor on mission in Syria. I'm sending you a box with gold and dollars, but customs need RM5,000 clearance fee. Please transfer to my agent."),
    ("MY", 5, "Buyer on Carousell says he already paid for my sofa and sent a link to 'receive payment' asking for my card number, CVV and OTP."),
    ("MY", 3, "Got a video call from my 'boss' asking me urgently to transfer RM48,000 to a new supplier account before 3pm, said not to tell the finance team. His voice sounded slightly robotic."),
    ("MY", 1, "Ma, ini nombor baru adik. Phone lama rosak. Tolong transfer RM800 urgent untuk bayar sewa, nanti adik pulangkan. Jangan call, adik dalam meeting."),
    # --- Singapore ---------------------------------------------------------
    ("SG", 2, "DBS: Your card has been temporarily suspended due to suspicious activity. Reactivate immediately at dbs-sg-verify.com"),
    ("SG", 6, "DBS Alert: Unusual login detected. Verify your identity at dbs-sg-verify.com within 2 hours or your account will be frozen."),
    ("SG", 4, "Caller claimed to be from ICA, said my passport was used in a crime in China and transferred me to 'Shanghai police' who asked for my bank details to prove innocence."),
    ("SG", 10, "Call from 'MOH officer' saying I spread COVID false information and will be charged, then 'police' asked me to transfer savings to a safe account for investigation."),
    ("SG", 1, "Telegram: Earn $200/day rating hotels on Agoda! Complete 30 tasks, pay a small deposit to unlock combo tasks with 3x commission. Contact @AgodaTaskSG"),
    ("SG", 5, "Part-time job: like Google Maps reviews, $8 per task, paid daily. Join the Telegram channel and top up USDT to start premium tasks."),
    ("SG", 8, "Met someone on a dating app who showed me crypto profits on a platform called BitNexa Pro. I deposited $5,000 and now they ask 20% 'tax' to withdraw."),
    # --- Indonesia ---------------------------------------------------------
    ("ID", 3, "Selamat! Anda memenangkan undian Shopee 2026 senilai Rp 50 juta. Hubungi admin di 0812-7766-1234 dan bayar pajak hadiah Rp 500 ribu."),
    ("ID", 1, "Paket J&T Anda tertunda. Silakan cek foto paket di aplikasi berikut: Lihat-Foto-Paket.apk"),
    ("ID", 4, "Kurir: Mohon konfirmasi alamat pengiriman, buka file Undangan-Pernikahan.apk untuk detail. Terima kasih."),
    ("ID", 9, "Pinjol cepat cair tanpa BI checking! Cukup kirim foto KTP dan selfie, bayar biaya admin Rp 250 ribu ke rekening 1234 5678 9012."),
    # --- Philippines -------------------------------------------------------
    ("PH", 2, "GCash: Your account is restricted due to unusual activity. Verify now at gcash-verify-ph.com to avoid permanent suspension."),
    ("PH", 5, "GCash Advisory: You received P2,500 ayuda. Claim within 24 hours at gcash-verify-ph.com"),
    ("PH", 3, "Hiring! Like YouTube videos and earn P500 per day. Message us on Telegram, small deposit required to start VIP tasks."),
    # --- Thailand ----------------------------------------------------------
    ("TH", 2, "เจ้าหน้าที่ DSI แจ้งว่าบัญชีของคุณเกี่ยวข้องกับคดีฟอกเงิน ต้องโอนเงินทั้งหมดไปยังบัญชีตรวจสอบภายในวันนี้ ห้ามบอกใคร"),
    ("TH", 6, "Kerry Express: พัสดุของคุณมีสินค้าผิดกฎหมาย กรุณาติดต่อตำรวจเพื่อยืนยันตัวตนและโอนเงินค้ำประกัน"),
    # --- Australia / Hong Kong / India -------------------------------------
    ("AU", 1, "Hi Mum, I dropped my phone in the toilet, this is my new number. Can you pay a bill for me today? I'll pay you back tomorrow xx"),
    ("AU", 4, "Hi Dad, it's me, new number. I'm locked out of my banking app, can you transfer $1,950 to this account for my rent urgently?"),
    ("HK", 3, "Hongkong Post: Your parcel has unpaid import duties of HK$12. Pay at hkpost-duty.top or it will be returned."),
    ("IN", 2, "Video call from a 'CBI officer' saying I am under digital arrest for money laundering, must stay on camera and transfer my fixed deposit for 'verification'."),
    ("IN", 5, "Courier call: your FedEx parcel to Taiwan has drugs, connecting you to Mumbai Cyber Police on Skype. Do not disconnect, you are under digital arrest."),
    # --- extra recent volume for trending campaigns ------------------------
    ("MY", 0, "J&T Express: Penghantaran gagal. Kemas kini alamat dan bayar RM2.50 di poslaju-redeliver.top"),
    ("SG", 0, "Job offer: TikTok Shop is hiring remote reviewers, $300 daily. Pay $50 training fee to activate account. WhatsApp +65 8123 4567"),
    ("MY", 0, "Ada orang call kata dari TNB, bil elektrik tertunggak RM1,200, kalau tak bayar hari ini bekalan dipotong. Suruh bayar ke akaun peribadi."),
]


async def main() -> None:
    sem = asyncio.Semaphore(4)
    now = dt.datetime.now(dt.timezone.utc)
    done = 0

    async def one(country: str, days: int, text: str) -> None:
        nonlocal done
        created = now - dt.timedelta(days=days, hours=random.randint(0, 20), minutes=random.randint(0, 59))
        async with sem:
            async for event, payload in pipeline.check(text=text, media=[], lang="en", country=country, share=True,
                                                       source="seed", created_at=created, verify=False):
                if event == "result":
                    done += 1
                    camp = (payload["community"].get("campaign") or {})
                    print(f"[{done:2d}/{len(SEEDS)}] {country} {payload['verdict']:<11} {payload['scamType']:<24} "
                          f"{'NEW ' if camp.get('new') else 'join'} {camp.get('title', '')[:50]}", flush=True)

    # Oldest first so campaigns form in chronological order.
    for country, days, text in sorted(SEEDS, key=lambda s: -s[1]):
        await one(country, days, text)


if __name__ == "__main__":
    asyncio.run(main())
