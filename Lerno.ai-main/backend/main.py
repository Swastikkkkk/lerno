"""Lerno.ai backend.

POST /generate {prompt}      -> {job_id}
GET  /jobs/{job_id}          -> status, stage, progress, scenes (with video_url when rendered)
POST /chat {lesson, question, message, history}
POST /tts {text}             -> {audio_url} via Murf, or 503 so the browser falls back to speechSynthesis
GET  /health

No paid keys anywhere. With no key, the LLM work runs on Pollinations' free anonymous
OpenAI-compatible API. Visitors can optionally paste their own free Gemini key (X-Gemini-Key header)
for faster, steadier results; if Gemini hits its free quota we drop back to Pollinations. Manim scenes that fail to
render are sent back to Gemini with the error, and a guaranteed-safe scene is used as a
last resort, so a lesson always finishes.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel

GEMINI_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FREE_URL = os.getenv("FREE_LLM_URL", "https://text.pollinations.ai/openai")
FREE_MODEL = os.getenv("FREE_LLM_MODEL", "openai")
FREE_TOKEN = os.getenv("POLLINATIONS_TOKEN")  # optional, raises rate limits
MURF_KEY = os.getenv("MURF_API_KEY")
MURF_VOICE = os.getenv("MURF_VOICE", "en-US-natalie")
MEDIA = Path(os.getenv("MEDIA_DIR", "/tmp/lerno-media"))
MEDIA.mkdir(parents=True, exist_ok=True)
JOB_TTL = 3 * 60 * 60          # forget jobs and their videos after 3 hours
RENDER_TIMEOUT = 150           # seconds per manim run
FIX_ATTEMPTS = 2

_clients: dict[str, genai.Client] = {}


def client_for(key: str | None) -> genai.Client:
    key = (key or GEMINI_KEY or "").strip()
    if not key:
        raise NeedKey()
    if key not in _clients:
        if len(_clients) > 200:
            _clients.clear()
        _clients[key] = genai.Client(api_key=key)
    return _clients[key]


class NeedKey(Exception):
    pass


class BadKey(Exception):
    pass
render_slots = threading.Semaphore(int(os.getenv("RENDER_SLOTS", "3")))
pool = ThreadPoolExecutor(max_workers=8)
jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()

app = FastAPI(title="Lerno.ai")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory=str(MEDIA)), name="media")


# ----------------------------------------------------------------------------- llm
def ask_free(prompt: str, as_json: bool, temperature: float, max_tokens: int = 4096) -> str:
    """Pollinations: free, no signup, OpenAI-compatible."""
    msgs = [{"role": "user", "content": prompt + ("\n\nReply with only the JSON object." if as_json else "")}]
    # the free model reasons before answering; cap reasoning so it doesn't eat the token budget
    body = {"model": FREE_MODEL, "messages": msgs, "temperature": temperature, "private": True,
            "max_tokens": max(max_tokens, 6000) + 2000, "reasoning_effort": "low"}
    if as_json:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json"}
    if FREE_TOKEN:
        headers["Authorization"] = f"Bearer {FREE_TOKEN}"
    last = None
    for attempt in range(4):
        try:
            r = requests.post(FREE_URL, json=body, headers=headers, timeout=120)
            if r.status_code in (400, 429) or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            r.raise_for_status()
            return (r.json()["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:
            last = e
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"Free model failed: {last}")


def ask(prompt: str, key: str | None, as_json: bool = False, temperature: float = 0.6, max_tokens: int = 4096) -> str:
    key = (key or GEMINI_KEY or "").strip()
    if not key:
        return ask_free(prompt, as_json, temperature, max_tokens)
    client = client_for(key)
    cfg = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_mime_type="application/json" if as_json else "text/plain",
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    for attempt in range(2):
        try:
            r = client.models.generate_content(model=MODEL, contents=prompt, config=cfg)
            return (r.text or "").strip()
        except Exception as e:
            msg = str(e)
            if "API_KEY_INVALID" in msg or "API key not valid" in msg or "PERMISSION_DENIED" in msg:
                raise BadKey("That Gemini key was rejected. Check it in Google AI Studio, or remove it to use the free model.")
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
                break  # free quota used up, go keyless
            time.sleep(3 * (attempt + 1))
    return ask_free(prompt, as_json, temperature, max_tokens)


def ask_json(prompt: str, key: str | None, **kw) -> dict:
    text = ask(prompt, key, as_json=True, **kw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


# ----------------------------------------------------------------------------- prompts
PLAN = """You are planning a short animated lesson.
Learner request: "{req}"

Work out who the learner is (default: curious high-school student) and the exact topic.
Split the topic into exactly 3 scenes. Each scene is one idea that can be shown with simple
2D shapes, arrows, graphs, numbers and short text in under 15 seconds. No quiz scenes.

Return JSON:
{{"topic": "...", "audience": "...",
  "scenes": [{{"title": "short title", "idea": "one or two sentences on what this scene shows"}}]}}"""

SCENE = """You are writing one scene of an animated lesson about "{topic}" for a {audience}.
Scene {n} of {total}: "{title}". What it shows: {idea}

Return JSON with:
- "narration": 2 to 4 friendly sentences a narrator reads while the animation plays.
- "question": one multiple choice question that checks this scene.
- "choices": exactly 4 short answer options, plain text, no letters in front.
- "correct_index": index (0-3) of the right option.
- "code": a complete Manim Community v0.19 Python file.

Rules for "code":
- Start with `from manim import *` and define exactly one class `Scene{n}(Scene)` with `construct`.
- Use only: Text, MathTex, Circle, Square, Rectangle, Dot, Line, Arrow, Vector, NumberPlane, Axes,
  VGroup, Brace, SurroundingRectangle, and animations Create, Write, FadeIn, FadeOut, Transform,
  GrowArrow, Indicate, self.wait.
- No images, SVGs, sounds, external files, updaters, ValueTracker, always_redraw or 3D.
- Layout: title at the top, diagram centered below it (shift DOWN*0.5), scaled so it fits a 5x4 box.
  Place every label with .next_to(target, direction, buff=0.2); never put two objects on the same spot.
  Before showing a new diagram, FadeOut the previous one. Arrange groups with .arrange(...).
- Keep every object inside the frame (x between -6.5 and 6.5, y between -3.5 and 3.5).
  Text font_size 28 to 40. Title at the top with .to_edge(UP).
- Total runtime 8 to 14 seconds. End with self.wait(1).
- Plain ASCII inside Text(). Use MathTex only for simple formulas.
"""

FIX = """This Manim Community v0.19 file failed to render.

```python
{code}
```

Error (last lines):
```
{error}
```

Return JSON {{"code": "..."}} with a corrected complete file. Keep the class name {cls}.
Simplify anything risky: prefer Text over MathTex, drop anything not in the basic Manim API."""


def safe_scene(n: int, title: str, narration: str) -> str:
    """A scene that always renders: title plus the narration split into short lines."""
    words = re.sub(r"[^A-Za-z0-9 ,.?!'\-]", "", narration).split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) > 46:
            lines.append(cur.strip())
            cur = ""
        cur += w + " "
        if len(lines) == 4:
            break
    if cur.strip() and len(lines) < 4:
        lines.append(cur.strip())
    t = re.sub(r"[^A-Za-z0-9 ,.?!'\-]", "", title)[:40] or f"Part {n}"
    body = ",\n            ".join(f'Text("{l}", font_size=30)' for l in lines) or 'Text("", font_size=30)'
    return f'''from manim import *

class Scene{n}(Scene):
    def construct(self):
        title = Text("{t}", font_size=44, weight=BOLD).to_edge(UP)
        line = Line(LEFT * 4, RIGHT * 4).next_to(title, DOWN, buff=0.3)
        body = VGroup(
            {body}
        ).arrange(DOWN, buff=0.35).next_to(line, DOWN, buff=0.6)
        self.play(Write(title), Create(line))
        for row in body:
            self.play(FadeIn(row, shift=UP * 0.2), run_time=0.8)
        self.wait(2)
'''


# ----------------------------------------------------------------------------- render
def render(code: str, cls: str, out_path: Path) -> tuple[bool, str]:
    work = Path(tempfile.mkdtemp(prefix="lerno-"))
    try:
        (work / "scene.py").write_text(code, encoding="utf-8")
        with render_slots:
            p = subprocess.run(
                ["manim", "-ql", "--disable_caching", "--progress_bar", "none",
                 "--media_dir", str(work / "media"), "scene.py", cls],
                cwd=work, capture_output=True, text=True, timeout=RENDER_TIMEOUT,
            )
        mp4s = list((work / "media").rglob(f"{cls}.mp4"))
        if p.returncode == 0 and mp4s:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(mp4s[0]), out_path)
            return True, ""
        return False, (p.stderr or p.stdout)[-2500:]
    except subprocess.TimeoutExpired:
        return False, f"Render took longer than {RENDER_TIMEOUT}s. Make the scene shorter and simpler."
    finally:
        shutil.rmtree(work, ignore_errors=True)


def clean_code(code: str) -> str:
    code = code.strip()
    m = re.search(r"```(?:python)?\s*(.*?)```", code, re.S)
    if m:
        code = m.group(1)
    if "from manim import" not in code:
        code = "from manim import *\n\n" + code
    return code


# ----------------------------------------------------------------------------- jobs
def update(job_id: str, **kw):
    with jobs_lock:
        jobs[job_id].update(kw)


def build_scene(job_id: str, plan: dict, i: int, s: dict, key: str | None) -> dict:
    n, total = i + 1, len(plan["scenes"])
    cls = f"Scene{n}"
    try:
        d = ask_json(SCENE.format(topic=plan["topic"], audience=plan["audience"], n=n, total=total,
                                  title=s["title"], idea=s["idea"]), key, max_tokens=6000)
    except Exception:
        d = {}
    narration = d.get("narration") or s["idea"]
    choices = [str(c) for c in (d.get("choices") or [])][:4]
    if len(choices) < 2:
        choices = ["I understand this part", "I need to see it again"]
    scene = {
        "scene_number": n,
        "title": s["title"],
        "narration": narration,
        "assessment": {"multiple_choice": {
            "question": d.get("question") or f"Did this explain {s['title'].lower()}?",
            "choices": choices,
            "correct_index": int(d.get("correct_index", 0)) if str(d.get("correct_index", 0)).isdigit() else 0,
        }},
        "video_url": None,
    }

    out = MEDIA / job_id / f"{cls}.mp4"
    code = clean_code(d.get("code", "")) if d.get("code") else None
    ok, err = (False, "no code") if not code else render(code, cls, out)
    tries = 0
    while not ok and code and tries < FIX_ATTEMPTS:
        tries += 1
        try:
            code = clean_code(ask_json(FIX.format(code=code, error=err, cls=cls), key, temperature=0.3, max_tokens=6000)["code"])
            ok, err = render(code, cls, out)
        except Exception as e:
            err = str(e)
    if not ok:
        ok, _ = render(safe_scene(n, s["title"], narration), cls, out)
    if ok:
        scene["video_url"] = f"/media/{job_id}/{cls}.mp4"
    with jobs_lock:
        jobs[job_id]["done_scenes"] += 1
        done = jobs[job_id]["done_scenes"]
    update(job_id, stage=f"Rendered scene {done} of {total}", progress=0.2 + 0.8 * done / total)
    return scene


def run_job(job_id: str, req: str, key: str | None):
    try:
        update(job_id, status="running", stage="Planning the lesson", progress=0.05)
        plan = ask_json(PLAN.format(req=req.replace('"', "'")[:500]), key)
        plan["scenes"] = [s for s in plan.get("scenes", []) if s.get("title")][:3]
        if not plan["scenes"]:
            raise RuntimeError("Could not plan a lesson for that request. Try rephrasing it.")
        update(job_id, topic=plan.get("topic", req), audience=plan.get("audience", ""),
               stage="Writing and animating scenes", progress=0.2)
        futures = [pool.submit(build_scene, job_id, plan, i, s, key) for i, s in enumerate(plan["scenes"])]
        scenes = [f.result() for f in futures]
        update(job_id, status="done", stage="Ready", progress=1.0, scenes=scenes)
    except NeedKey:
        update(job_id, status="error", stage="Failed", error="Add your Gemini API key to generate lessons.", code="NEED_KEY")
    except BadKey as e:
        update(job_id, status="error", stage="Failed", error=str(e), code="BAD_KEY")
    except Exception as e:
        update(job_id, status="error", stage="Failed", error=str(e))


def sweep():
    while True:
        cutoff = time.time() - JOB_TTL
        with jobs_lock:
            old = [k for k, v in jobs.items() if v["created"] < cutoff]
            for k in old:
                jobs.pop(k, None)
        for k in old:
            shutil.rmtree(MEDIA / k, ignore_errors=True)
        time.sleep(600)


threading.Thread(target=sweep, daemon=True).start()


# ----------------------------------------------------------------------------- routes
class GenerateIn(BaseModel):
    prompt: str


class ChatIn(BaseModel):
    message: str
    lesson: str = ""
    content: str = ""
    question: str = ""
    history: list[dict] = []


class TtsIn(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"ok": True, "server_key": bool(GEMINI_KEY), "free_llm": FREE_URL, "murf": bool(MURF_KEY), "jobs": len(jobs)}


@app.post("/generate")
def generate(body: GenerateIn, x_gemini_key: str | None = Header(default=None)):
    req = body.prompt.strip()
    if not req:
        raise HTTPException(400, "Tell me what you want to learn.")
    job_id = uuid.uuid4().hex[:12]
    with jobs_lock:
        jobs[job_id] = {"id": job_id, "status": "queued", "stage": "Queued", "progress": 0.0,
                        "prompt": req, "scenes": [], "done_scenes": 0, "created": time.time()}
    pool.submit(run_job, job_id, req, x_gemini_key)
    return {"job_id": job_id}


@app.get("/jobs/{job_id}")
def job(job_id: str):
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            raise HTTPException(404, "That lesson has expired. Generate it again.")
        return {k: v for k, v in j.items() if k != "created"}


@app.post("/chat")
def chat(body: ChatIn, x_gemini_key: str | None = Header(default=None)):
    history = "\n".join(f"{'Student' if h.get('role') == 'user' else 'Tutor'}: {h.get('text', '')}"
                        for h in body.history[-8:])
    prompt = (f"You are a friendly tutor. Lesson: \"{body.lesson}\". Lesson text: \"{body.content}\". "
              f"Current quiz question: \"{body.question}\".\n{history}\nStudent: {body.message}\n"
              "Answer in 2 to 4 short sentences. Don't give away the quiz answer directly; guide them.")
    try:
        return {"reply": ask(prompt, x_gemini_key, temperature=0.7, max_tokens=400)}
    except NeedKey:
        raise HTTPException(401, {"code": "NEED_KEY", "message": "Add your Gemini API key to chat."})
    except BadKey as e:
        raise HTTPException(401, {"code": "BAD_KEY", "message": str(e)})
    except Exception:
        raise HTTPException(502, "The tutor is busy, try again in a moment.")


@app.post("/tts")
def tts(body: TtsIn):
    if not MURF_KEY:
        raise HTTPException(503, "No TTS key, use the browser voice")
    try:
        r = requests.post("https://api.murf.ai/v1/speech/generate",
                          headers={"api-key": MURF_KEY, "Content-Type": "application/json"},
                          json={"text": body.text[:2500], "voiceId": MURF_VOICE, "format": "MP3"},
                          timeout=40)
        r.raise_for_status()
        url = r.json().get("audioFile")
        if not url:
            raise ValueError("no audio")
        return {"audio_url": url}
    except Exception:
        raise HTTPException(503, "TTS unavailable, use the browser voice")
