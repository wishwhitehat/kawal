import base64, json, subprocess, sys, wave
import numpy as np

V, DECK, SAMPLE, OUT = sys.argv[1:5]
R = 24000
meta = json.load(open(f"{V}/meta.json"))


def run(*a):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *a], check=True)


def wav(path):
    w = wave.open(path); a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)
    assert w.getframerate() == R
    return a


def track(dur, items):
    out = np.zeros(int(dur * R) + R, np.float32)
    for at, a, gain in items:
        i = int(at * R); out[i:i + len(a)] += a[: len(out) - i] * gain
    return np.clip(out, -32768, 32767).astype(np.int16)


def write(path, a):
    w = wave.open(path, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(R); w.writeframes(a.tobytes()); w.close()


def dur_of(path):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                capture_output=True, text=True).stdout)


VF = "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p"


def part(name, video_args, audio, dur, vf=VF):
    write(f"{V}/{name}.wav", audio)
    run(*video_args, "-i", f"{V}/{name}.wav", "-t", f"{dur:.2f}",
        "-vf", f"{vf},fade=t=in:st=0:d=0.4,fade=t=out:st={dur - 0.4:.2f}:d=0.4",
        "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={dur - 0.4:.2f}:d=0.4",
        "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", f"{V}/p_{name}.mp4")


n = {k: wav(f"{V}/{k}.wav") for k in ("n1", "n2", "n3", "n4", "n5", "n6")}

# 1. intro over the "Brief" slide
d = len(n["n1"]) / R + 1.6
part("intro", ["-loop", "1", "-framerate", "30", "-i", f"{DECK}/render/s02.png"], track(d, [(0.6, n["n1"], 1.0)]), d)

# 2. live guardian: narration + the real sample call + Kawal's captured voice
L = meta["live"]
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", SAMPLE, "-f", "s16le", "-ac", "1", "-ar", str(R), "-"],
                     capture_output=True, check=True).stdout
call = np.frombuffer(raw, np.int16).astype(np.float32)
kawal, end = [], 0.0
for c in L["chunks"]:
    pcm = np.frombuffer(base64.b64decode(c["b64"]), np.int16).astype(np.float32)
    at = max(c["t"], end); kawal.append((at, pcm, 1.15)); end = at + len(pcm) / R
items = [(0.3, n["n2"], 1.0), (L["sampleStart"], call, 0.8), *kawal, (L["summaryAt"] + 1.4, n["n3"], 1.0)]
d = min(L["dur"], L["summaryAt"] + 1.4 + len(n["n3"]) / R + 0.8)
run("-i", f"{V}/live.webm", "-vf", VF, "-c:v", "libx264", "-crf", "18", f"{V}/live_cfr.mp4")
part("live", ["-i", f"{V}/live_cfr.mp4"], track(d, items), d, vf="null")

# 3. scam check
d = min(meta["check"]["dur"], 27.0)
run("-i", f"{V}/check.webm", "-vf", VF, "-c:v", "libx264", "-crf", "18", f"{V}/check_cfr.mp4")
part("check", ["-i", f"{V}/check_cfr.mp4"], track(d, [(3.0, n["n4"], 1.0)]), d, vf="null")

# 4. intel console
d = meta["intel"]["dur"]
run("-i", f"{V}/intel.webm", "-vf", VF, "-c:v", "libx264", "-crf", "18", f"{V}/intel_cfr.mp4")
part("intel", ["-i", f"{V}/intel_cfr.mp4"], track(d, [(6.5, n["n5"], 1.0)]), d, vf="null")

# 5. close: architecture then links slides
d6 = len(n["n6"]) / R + 2.0
run("-loop", "1", "-framerate", "30", "-t", f"{d6 * 0.55:.2f}", "-i", f"{DECK}/render/s07.png",
    "-loop", "1", "-framerate", "30", "-t", f"{d6 * 0.45:.2f}", "-i", f"{DECK}/render/s13.png",
    "-filter_complex", f"[0:v]{VF}[a];[1:v]{VF}[b];[a][b]concat=n=2:v=1[v]", "-map", "[v]",
    "-c:v", "libx264", "-crf", "18", f"{V}/close_v.mp4")
part("close", ["-i", f"{V}/close_v.mp4"], track(d6, [(0.5, n["n6"], 1.0)]), d6, vf="null")

with open(f"{V}/list.txt", "w") as f:
    for p in ("intro", "live", "check", "intel", "close"):
        f.write(f"file 'p_{p}.mp4'\n")
run("-f", "concat", "-safe", "0", "-i", f"{V}/list.txt", "-c", "copy", "-movflags", "+faststart", OUT)
print("total", round(dur_of(OUT), 1), "s ->", OUT)
