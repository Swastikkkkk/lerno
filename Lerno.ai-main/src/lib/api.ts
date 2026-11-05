import axios from "axios";

// Set VITE_API_URL to the backend (Hugging Face Space). Falls back to a local dev server.
export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:7860").replace(/\/$/, "");

export const api = axios.create({ baseURL: API_URL, timeout: 30000 });

// ---- bring-your-own Gemini key -------------------------------------------------
const STORE = "lerno_gemini_key";
export const KEY_EVENT = "lerno:need-key";

export const getKey = () => {
  try { return localStorage.getItem(STORE) || ""; } catch { return ""; }
};
export const setKey = (k: string) => {
  try { k ? localStorage.setItem(STORE, k) : localStorage.removeItem(STORE); } catch { /* private mode */ }
};
export const askForKey = (reason = "") => window.dispatchEvent(new CustomEvent(KEY_EVENT, { detail: reason }));

api.interceptors.request.use((cfg) => {
  const k = getKey();
  if (k) cfg.headers.set("X-Gemini-Key", k);
  return cfg;
});

export type Scene = {
  scene_number: number;
  title: string;
  narration: string;
  video_url: string | null;
  assessment: {
    multiple_choice: { question: string; choices: string[]; correct_index: number };
  };
};

export type Job = {
  id: string;
  status: "queued" | "running" | "done" | "error";
  stage: string;
  progress: number;
  scenes: Scene[];
  topic?: string;
  error?: string;
};

export const mediaUrl = (path: string | null) => (path ? `${API_URL}${path}` : null);

/** Start a lesson and resolve when it finishes. Calls onUpdate with each poll. */
export async function generateLesson(prompt: string, onUpdate?: (j: Job) => void): Promise<Job> {
  const { data } = await api.post<{ job_id: string }>("/generate", { prompt });
  const started = Date.now();
  while (true) {
    await new Promise((r) => setTimeout(r, 2500));
    let job: Job;
    try {
      ({ data: job } = await api.get<Job>(`/jobs/${data.job_id}`));
    } catch (e) {
      if (Date.now() - started > 8 * 60 * 1000) throw e;
      continue; // transient network error, keep polling
    }
    onUpdate?.(job);
    if (job.status === "done") return job;
    if (job.status === "error") {
      throw new Error(job.error || "Generation failed");
    }
    if (Date.now() - started > 8 * 60 * 1000) throw new Error("This is taking too long. Try a simpler topic.");
  }
}

/** Speak text with Murf through the backend; fall back to the browser's own voice. */
export async function speak(text: string, signal: { cancelled: boolean }): Promise<HTMLAudioElement | null> {
  try {
    const { data } = await api.post<{ audio_url: string }>("/tts", { text }, { timeout: 45000 });
    if (signal.cancelled) return null;
    const audio = new Audio(data.audio_url);
    await audio.play().catch(() => {
      const resume = () => audio.play();
      window.addEventListener("click", resume, { once: true });
      window.addEventListener("keydown", resume, { once: true });
    });
    return audio;
  } catch {
    if (signal.cancelled || !("speechSynthesis" in window)) return null;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1;
    window.speechSynthesis.speak(u);
    return null;
  }
}

export function stopSpeaking(audio: HTMLAudioElement | null) {
  if (audio) {
    audio.pause();
    audio.currentTime = 0;
  }
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}
