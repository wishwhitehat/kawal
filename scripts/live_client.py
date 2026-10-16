"""Stream a sample call into the Live Guardian WebSocket and print every event.

Handy for testing the backend without a browser, and used for the latency
numbers in docs/BENCHMARK.md.

    python scripts/live_client.py frontend/public/samples/macau-scam-ms.m4a --lang ms
    python scripts/live_client.py <file> --url wss://<api>/ws/live --token <Firebase ID token>
"""

import argparse
import asyncio
import json
import subprocess
import time

import websockets


def pcm16k(path: str) -> bytes:
    return subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                          check=True, capture_output=True).stdout


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--url", default="ws://localhost:8080/ws/live")
    ap.add_argument("--token", default="")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="MY")
    ap.add_argument("--share", action="store_true")
    args = ap.parse_args()

    pcm = pcm16k(args.audio)
    t0 = time.time()
    first_alert = None
    async with websockets.connect(args.url, max_size=None) as ws:
        await ws.send(json.dumps({"type": "start", "token": args.token, "lang": args.lang,
                                  "country": args.country, "speak": True, "share": args.share}))

        ready = json.loads(await ws.recv())
        print(f"[{time.time() - t0:5.1f}] {ready}", flush=True)
        if ready.get("type") != "ready":
            return

        async def sender():
            for i in range(0, len(pcm), 3200):  # 100 ms chunks, real-time pace
                await ws.send(pcm[i:i + 3200])
                await asyncio.sleep(0.1)
            await asyncio.sleep(1.0)
            await ws.send(json.dumps({"type": "stop"}))

        task = asyncio.create_task(sender())
        audio = 0
        async for msg in ws:
            now = time.time() - t0
            if isinstance(msg, bytes):
                audio += len(msg)
                continue
            m = json.loads(msg)
            if m["type"] == "alert" and first_alert is None:
                first_alert = now
            brief = {k: v for k, v in m.items() if k not in ("hotline",)}
            print(f"[{now:5.1f}] {json.dumps(brief, ensure_ascii=False)[:220]}", flush=True)
            if m["type"] in ("summary", "error"):
                break
        await task
    print(f"spoken warning audio: {audio / 48000:.1f}s; first alert at {first_alert}s; audio length {len(pcm) / 32000:.1f}s")


asyncio.run(main())
