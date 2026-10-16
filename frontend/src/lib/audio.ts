/** Audio plumbing for the Live Call Guardian. */

export interface Capture {
  stop: () => void;
  level: () => number;
  /** Resolves when a sample call finishes playing (never for the microphone). */
  ended: Promise<void>;
}

async function recorderNode(ctx: AudioContext, onChunk: (pcm: ArrayBuffer) => void) {
  await ctx.audioWorklet.addModule("/worklets/pcm-recorder.js");
  const node = new AudioWorkletNode(ctx, "pcm-recorder");
  node.port.onmessage = (e) => onChunk(e.data as ArrayBuffer);
  // Keep the node pulled by the graph without making it audible.
  const mute = ctx.createGain();
  mute.gain.value = 0;
  node.connect(mute).connect(ctx.destination);
  return node;
}

function meter(ctx: AudioContext, src: AudioNode) {
  const an = ctx.createAnalyser();
  an.fftSize = 512;
  src.connect(an);
  const data = new Uint8Array(an.fftSize);
  return () => {
    an.getByteTimeDomainData(data);
    let peak = 0;
    for (const v of data) peak = Math.max(peak, Math.abs(v - 128));
    return peak / 128;
  };
}

export async function captureMic(onChunk: (pcm: ArrayBuffer) => void): Promise<Capture> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  const rec = await recorderNode(ctx, onChunk);
  src.connect(rec);
  const level = meter(ctx, src);
  return {
    level,
    ended: new Promise(() => {}),
    stop: () => {
      stream.getTracks().forEach((t) => t.stop());
      void ctx.close();
    },
  };
}

/** Plays a sample call through the speakers AND streams it to Kawal,
 * paced in real time exactly like a live call. */
export async function captureSample(url: string, onChunk: (pcm: ArrayBuffer) => void): Promise<Capture> {
  const ctx = new AudioContext();
  const buf = await ctx.decodeAudioData(await (await fetch(url)).arrayBuffer());
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const rec = await recorderNode(ctx, onChunk);
  src.connect(rec);
  src.connect(ctx.destination);
  const level = meter(ctx, src);
  const ended = new Promise<void>((resolve) => (src.onended = () => resolve()));
  src.start();
  return {
    level,
    ended,
    stop: () => {
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
      void ctx.close();
    },
  };
}

/** Plays Kawal's spoken warnings (16-bit PCM, 24 kHz) gap-free. */
export class PcmPlayer {
  private ctx = new AudioContext({ sampleRate: 24000 });
  private at = 0;

  play(chunk: ArrayBuffer) {
    const pcm = new Int16Array(chunk);
    const f = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i++) f[i] = pcm[i] / 0x8000;
    const buf = this.ctx.createBuffer(1, f.length, 24000);
    buf.copyToChannel(f, 0);
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.connect(this.ctx.destination);
    this.at = Math.max(this.at, this.ctx.currentTime + 0.05);
    src.start(this.at);
    this.at += buf.duration;
  }

  close() {
    void this.ctx.close();
  }
}
