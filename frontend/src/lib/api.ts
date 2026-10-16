import { idToken } from "./firebase";
import type { Bulletin, CheckResult, Overview, StageEvent } from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE as string).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function authed(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await idToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...(init.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = (await res.json()).detail ?? msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, msg);
  }
  return res;
}

export async function getJson<T>(path: string): Promise<T> {
  return (await authed(path)).json();
}

export async function postJson<T>(path: string, body: unknown = {}): Promise<T> {
  const res = await authed(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

/** POST /api/check and consume the Server-Sent Events stream. */
export async function runCheck(
  form: FormData,
  onStage: (e: StageEvent) => void,
): Promise<CheckResult> {
  const res = await authed("/api/check", { method: "POST", body: form });
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (!event || !data) continue;
      const payload = JSON.parse(data);
      if (event === "stage") onStage(payload);
      else if (event === "result") return payload as CheckResult;
      else if (event === "error") throw new ApiError(500, payload.message);
    }
  }
  throw new ApiError(500, "Connection closed before the result arrived");
}

export const getOverview = () => getJson<Overview>("/api/intel/overview");
export const makeBulletin = () => postJson<Bulletin>("/api/intel/bulletin");
export const askIntel = (question: string) =>
  postJson<{ answer: string; trace: { tool: string; args: Record<string, unknown>; preview: string }[] }>(
    "/api/intel/ask",
    { question },
  );

export async function speak(text: string, lang: string): Promise<HTMLAudioElement> {
  const res = await authed("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text.slice(0, 900), lang }),
  });
  const url = URL.createObjectURL(await res.blob());
  const audio = new Audio(url);
  audio.onended = () => URL.revokeObjectURL(url);
  await audio.play();
  return audio;
}

export function liveSocketUrl(): string {
  return API_BASE.replace(/^http/, "ws") + "/ws/live";
}
