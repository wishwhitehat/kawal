// Downsamples whatever the AudioContext runs at to 16 kHz mono 16-bit PCM
// (the Gemini Live input format) and posts 100 ms chunks to the main thread.
class PcmRecorder extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.out = new Int16Array(1600);
    this.n = 0;
    this.sum = 0;
    this.count = 0;
    this.phase = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.sum += ch[i];
      this.count++;
      this.phase += 1;
      if (this.phase >= this.ratio) {
        this.phase -= this.ratio;
        const s = Math.max(-1, Math.min(1, this.sum / this.count));
        this.out[this.n++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        this.sum = 0;
        this.count = 0;
        if (this.n === this.out.length) {
          this.port.postMessage(this.out.buffer.slice(0));
          this.n = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-recorder", PcmRecorder);
