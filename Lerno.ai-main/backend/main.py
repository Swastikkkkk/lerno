"""ExplAInr backend.

POST /generate {prompt}      -> {job_id}
GET  /jobs/{job_id}          -> status, stage, progress, scenes (with video_url when rendered)
POST /chat {lesson, question, message, history}
POST /tts {text}             -> {audio_url} via Murf, or 503 so the browser falls back to speechSynthesis
GET  /health

No paid keys anywhere. With no key, the LLM work runs on Pollinations' free anonymous
OpenAI-compatible API. Visitors can optionally paste their own free Gemini key (X-Gemini-Key header)
for faster, steadier results; if Gemini hits its free quota we drop back to Pollinations.

One LLM call writes the whole lesson. It never writes Manim code: it describes each scene as a small JSON spec and scene_engine.py draws it
with a fixed layout, so text and shapes never overlap and every scene renders.
"""
import hashlib
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
NVIDIA_KEY = os.getenv("NVIDIA_API_KEY")  # free key from build.nvidia.com; used for every visitor when set
NVIDIA_URL = os.getenv("NVIDIA_URL", "https://integrate.api.nvidia.com/v1/chat/completions")
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b")
MURF_KEY = (os.getenv("MURF_API_KEY") or "").strip().strip('"').strip("'") or None
MURF_VOICE = os.getenv("MURF_VOICE", "en-IN-nikhil")
MURF_MODEL = os.getenv("MURF_MODEL", "FALCON")
# language code -> (English name, native name, Murf Falcon voice)
LANGS = {
    "en-IN": ("English", "English", MURF_VOICE),
    "hi-IN": ("Hindi", "हिन्दी", "hi-IN-karan"),
    "bn-IN": ("Bengali", "বাংলা", "bn-IN-arnab"),
    "ta-IN": ("Tamil", "தமிழ்", "ta-IN-sarvesh"),
    "mr-IN": ("Marathi", "मराठी", "mr-IN-vaibhav"),
    "gu-IN": ("Gujarati", "ગુજરાતી", "gu-IN-hardik"),
    "kn-IN": ("Kannada", "ಕನ್ನಡ", "kn-IN-harshitha"),
    "ml-IN": ("Malayalam", "മലയാളം", "ml-IN-madhavan"),
    "pa-IN": ("Punjabi", "ਪੰਜਾਬੀ", "pa-IN-harman"),
    "es-ES": ("Spanish", "Español", "es-ES-javier"),
    "fr-FR": ("French", "Français", "fr-FR-axel"),
    "de-DE": ("German", "Deutsch", "de-DE-ralf"),
    "pt-BR": ("Portuguese", "Português", "pt-BR-yago"),
    "it-IT": ("Italian", "Italiano", "it-IT-vincenzo"),
    "ja-JP": ("Japanese", "日本語", "ja-JP-denki"),
    "ko-KR": ("Korean", "한국어", "ko-KR-hwan"),
    "zh-CN": ("Chinese", "中文", "zh-CN-tao"),
}
_translations: dict[tuple[str, str], str] = {}
MEDIA = Path(os.getenv("MEDIA_DIR", "/tmp/lerno-media"))
MEDIA.mkdir(parents=True, exist_ok=True)
JOB_TTL = 3 * 60 * 60          # forget jobs and their videos after 3 hours
RENDER_TIMEOUT = 150           # seconds per manim run

_clients: dict[str, genai.Client] = {}
free_slots = threading.Semaphore(int(os.getenv("FREE_LLM_SLOTS", "1")))  # anonymous tier allows ~1 request at a time


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


class FreeQuota(Exception):
    pass
render_slots = threading.Semaphore(int(os.getenv("RENDER_SLOTS", "3")))
pool = ThreadPoolExecutor(max_workers=8)
jobs: dict[str, dict] = {}
recent: dict[str, str] = {}  # same request again -> reuse the finished lesson while its videos still exist
jobs_lock = threading.Lock()

app = FastAPI(title="ExplAInr")
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
            with free_slots:
                r = requests.post(FREE_URL, json=body, headers=headers, timeout=150)
            if r.status_code == 402:
                raise FreeQuota("ExplAInr is busy right now. Try again in a minute.")
            if r.status_code in (400, 429) or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            r.raise_for_status()
            return (r.json()["choices"][0]["message"].get("content") or "").strip()
        except FreeQuota:
            raise
        except Exception as e:
            last = e
            print(f"free llm attempt {attempt + 1} failed: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Free model failed: {last}")


def ask_nvidia(prompt: str, as_json: bool, temperature: float, max_tokens: int = 4096) -> str:
    """NVIDIA's free API (Nemotron). OpenAI-compatible; thinking off so the answer comes back fast."""
    msgs = [{"role": "user", "content": prompt + ("\n\nReply with only the JSON object." if as_json else "")}]
    body = {"model": NVIDIA_MODEL, "messages": msgs, "temperature": temperature,
            "max_tokens": max(max_tokens, 6000) + 2000, "chat_template_kwargs": {"enable_thinking": False}}
    last = None
    for attempt in range(3):
        try:
            r = requests.post(NVIDIA_URL, json=body, headers={"Authorization": f"Bearer {NVIDIA_KEY}"}, timeout=180)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            r.raise_for_status()
            return (r.json()["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:
            last = e
            print(f"nvidia attempt {attempt + 1} failed: {e}", flush=True)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"NVIDIA failed: {last}")


def ask(prompt: str, key: str | None, as_json: bool = False, temperature: float = 0.6, max_tokens: int = 4096) -> str:
    key = (key or GEMINI_KEY or "").strip()
    if not key:
        if NVIDIA_KEY:
            try:
                return ask_nvidia(prompt, as_json, temperature, max_tokens)
            except Exception as e:
                print(f"nvidia unavailable, trying the free model: {e}", flush=True)
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


def _loads(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    body = m.group(0) if m else text
    # \frac, \text, \times... are valid-looking JSON escapes (\f, \t, \b, \r) that would eat the LaTeX
    body = re.sub(r"(?<!\\)\\(?=(?:frac|tfrac|dfrac|text|times|theta|tau|top|beta|bmod|binom|bar|rightarrow|rho|rangle|bf)(?![a-z]))",
                  r"\\\\", body)
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        # LaTeX like \frac inside a JSON string is an invalid escape; double any lone backslash
        return json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", body))


def ask_json(prompt: str, key: str | None, **kw) -> dict:
    return _loads(ask(prompt, key, as_json=True, **kw))


# ----------------------------------------------------------------------------- prompts
LESSON = """You are making a short animated lesson. Learner request: "{req}"

Work out who the learner is (default: curious high-school student) and the exact topic. Teach it in exactly
3 scenes that build on each other, each one idea. You do NOT write code: you describe each scene as JSON and a
layout engine draws it, so keep every on-screen text short. Prefer a real diagram over bullets.

Return one JSON object:
{{"topic": "...", "audience": "...",
  "scenes": [{{
    "title": "2 to 4 word title",
    "narration": "2 to 4 friendly sentences the narrator reads while this scene plays",
    "question": "one multiple choice question that checks this scene",
    "choices": ["4 short options", "plain text", "no letters", "in front"],
    "correct_index": 0,
    "visual": {{ ...one visual, see below... }},
    "steps": [ ...3 to 6 steps that animate it in the order the narration talks about it... ],
    "takeaway": "optional final line, max 8 words"
  }}]}}

VISUALS (pick the one that fits best):
- {{"kind":"row","style":"boxes|nodes|cells|circles","items":["A","B","C"],"arrows":true,"terminal":"null","indices":false}}
    nodes = linked-list nodes with a pointer cell; cells = array (touching boxes, set "indices":true for 0,1,2...);
    boxes with arrows = a pipeline / process / timeline. Max 7 items, each item max 12 characters.
- {{"kind":"stack","items":["top item","...","bottom item"]}}  (call stack, layers, stack data structure)
- {{"kind":"tree","items":[{{"id":"a","text":"8"}},{{"id":"b","text":"3","parent":"a"}}]}}  (max 9 nodes)
- {{"kind":"cycle","items":["Stage 1","Stage 2","Stage 3","Stage 4"]}}  (3 to 6 stages that loop)
- {{"kind":"network","items":[{{"id":"A","text":"A"}}],"edges":[["A","B"]],"arrows":false}}  (graphs, max 7 nodes)
- {{"kind":"plot","x":[-3,3],"functions":[{{"expr":"x^2","label":"y = x^2"}}],"x_label":"x","y_label":"y"}}
    expr uses x, numbers, + - * / ^ ( ), sin cos tan exp log sqrt abs pi. Max 3 functions.
- {{"kind":"bars","items":[{{"label":"A","value":5}}]}}  (max 8 bars; sorting, comparisons, data)
- {{"kind":"equation","lines":["a^2 + b^2 = c^2","3^2 + 4^2 = c^2","c = 5"]}}  (LaTeX, max 4 lines, one per step)
- {{"kind":"compare","left":{{"title":"X","points":["...","..."]}},"right":{{"title":"Y","points":["..."]}}}}  (max 4 points each)
- {{"kind":"bullets","points":["...","..."]}}  (last resort, max 4 points, max 6 words each)

STEPS (target = item index from 0, or the item's id/text; indexes shift after add/remove):
- {{"op":"highlight","target":1}}            colour an item (optional "color": good|bad|accent)
- {{"op":"trace","targets":[0,1,2]}}         walk along items one by one (traversal, search, flow)
- {{"op":"label","target":0,"text":"head"}}  1 to 3 words next to an item; reusing the same text moves it
- {{"op":"change","target":2,"text":"25"}}   change an item's value (bars: "value": 25)
- {{"op":"add","text":"15","at":1}}          insert into row/stack/cycle ("parent":"id" for tree)
- {{"op":"remove","target":1}}
- {{"op":"swap","targets":[0,1]}}            row or bars (sorting)
- {{"op":"connect","from":"A","to":"B"}}     network or tree
- {{"op":"draw","f":0}} / {{"op":"dot","f":0,"x":2,"text":"(2, 4)"}} / {{"op":"area","f":0,"from":0,"to":2}}   plot only
- {{"op":"next"}}                            equation, compare, bullets: reveal the next line
- {{"op":"note","text":"k mod n = 2"}}       one short line under the diagram (max 10 words or one formula)
Any step may also carry "note". Labels: at most 4 per scene. Everything must fit the idea of THIS scene.
Notes and labels appear on screen for the learner: write the idea ("largest value ends up last"), never
describe the animation ("checkmark appears", "arrow moves"). "terminal" is only for linked lists."""


def safe_scene(n: int, title: str, narration: str) -> str:
    """Plain Manim that always renders: title plus the narration split into short lines."""
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

class Lesson(Scene):
    def construct(self):
        title = Text("{t}", font_size=40, weight=BOLD).move_to(UP * 3.3)
        body = VGroup(
            {body}
        ).arrange(DOWN, buff=0.35).move_to(UP * 0.6)
        self.play(Write(title))
        for row in body:
            self.play(FadeIn(row, shift=UP * 0.2), run_time=0.8)
        self.wait(2)
'''


# ----------------------------------------------------------------------------- render
ENGINE = (Path(__file__).resolve().parent / "scene_engine.py").read_text(encoding="utf-8")
KINDS = {"row", "stack", "tree", "cycle", "network", "plot", "bars", "equation", "compare", "bullets"}


def render(code: str, out_path: Path, cls: str = "Lesson") -> tuple[bool, str]:
    work = Path(tempfile.mkdtemp(prefix="lerno-"))
    try:
        (work / "scene.py").write_text(code, encoding="utf-8")
        with render_slots:
            p = subprocess.run(
                ["manim", "-qm", "--disable_caching", "--progress_bar", "none",
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
        return False, f"Render took longer than {RENDER_TIMEOUT}s."
    finally:
        shutil.rmtree(work, ignore_errors=True)


def spec_code(spec: dict) -> str:
    return ENGINE + "\nimport json as _json\nSPEC = _json.loads(" + repr(json.dumps(spec)) + ")\n"


def narration_seconds(text: str) -> float:
    # ~2.5 words a second for Murf and browser voices, plus a beat at the end
    return max(9.0, min(26.0, len(text.split()) / 2.5 + 1.5))


def _short(v, n=40):
    return re.sub(r"\s+", " ", str(v if v is not None else "")).strip()[:n]


def normalize_spec(d: dict, title: str, narration: str) -> dict:
    """Clamp whatever the LLM sent into something the engine can always draw."""
    v = d.get("visual") if isinstance(d.get("visual"), dict) else {}
    kind = str(v.get("kind", "")).lower().strip()
    kind = {"list": "row", "array": "row", "linkedlist": "row", "linked_list": "row", "pipeline": "row",
            "flow": "row", "timeline": "row", "graph": "network", "chart": "bars", "math": "equation",
            "comparison": "compare", "text": "bullets"}.get(kind, kind)
    if kind not in KINDS:
        kind = "bullets"
    out = {"kind": kind}
    if kind in ("row", "stack", "cycle"):
        items = [_short(x.get("text") if isinstance(x, dict) else x, 14) for x in (v.get("items") or [])][:7]
        out["items"] = [x for x in items if x] or [title[:14]]
        if kind == "cycle" and len(out["items"]) < 3:
            kind = out["kind"] = "row"
        out["style"] = str(v.get("style", "boxes")).lower()
        for k in ("arrows", "indices"):
            if k in v:
                out[k] = bool(v[k])
        if v.get("terminal") and kind == "row" and out["style"] == "nodes":
            out["terminal"] = _short(v["terminal"], 8)
    elif kind in ("tree", "network"):
        items = []
        for x in (v.get("items") or [])[:9]:
            if isinstance(x, dict):
                items.append({"id": _short(x.get("id") or x.get("text"), 20), "text": _short(x.get("text") or x.get("id"), 10),
                              "parent": _short(x.get("parent"), 20) or None})
            elif x is not None:
                items.append({"id": _short(x, 20), "text": _short(x, 10)})
        out["items"] = items or [{"id": "a", "text": title[:10]}]
        out["edges"] = [[_short(e[0], 20), _short(e[1], 20)] for e in (v.get("edges") or [])
                        if isinstance(e, (list, tuple)) and len(e) >= 2][:12]
        if "arrows" in v:
            out["arrows"] = bool(v["arrows"])
        out["style"] = str(v.get("style", "circles" if kind == "network" else "boxes")).lower()
    elif kind == "plot":
        fns = [{"expr": _short(f.get("expr"), 60), "label": _short(f.get("label") or f.get("expr"), 30)}
               for f in (v.get("functions") or []) if isinstance(f, dict) and f.get("expr")][:3]
        if not fns:
            kind, out = "bullets", {"kind": "bullets"}
        else:
            out["functions"] = fns
            try:
                x = [float(a) for a in v.get("x", [-5, 5])][:2]
                out["x"] = x if x[0] < x[1] else [-5, 5]
            except Exception:
                out["x"] = [-5, 5]
            try:
                y = [float(a) for a in v["y"]][:2]
                if y[0] < y[1]:
                    out["y"] = y
            except Exception:
                pass
            out["x_label"], out["y_label"] = _short(v.get("x_label", "x"), 12), _short(v.get("y_label", "y"), 12)
    elif kind == "bars":
        items = []
        for x in (v.get("items") or [])[:8]:
            if isinstance(x, dict):
                try:
                    items.append({"label": _short(x.get("label"), 12), "value": float(x.get("value", 0))})
                except Exception:
                    pass
        if items:
            out["items"] = items
        else:
            kind, out = "bullets", {"kind": "bullets"}
    elif kind == "equation":
        out["lines"] = [_short(x, 80) for x in (v.get("lines") or []) if str(x).strip()][:4] or [title]
    elif kind == "compare":
        for side in ("left", "right"):
            c = v.get(side) if isinstance(v.get(side), dict) else {}
            out[side] = {"title": _short(c.get("title"), 22), "points": [_short(p, 32) for p in (c.get("points") or [])][:4]}
    if out["kind"] == "bullets":
        pts = [_short(p, 44) for p in (v.get("points") or []) if str(p).strip()][:4]
        if not pts:
            pts = [_short(s_, 44) for s_ in re.split(r"(?<=[.!?])\s+", narration) if s_.strip()][:4]
        out["points"] = pts or [title]
    steps = [s_ for s_ in (d.get("steps") or []) if isinstance(s_, dict) and s_.get("op")][:10]
    return {"title": _short(title, 44), "visual": out, "steps": steps, "takeaway": _short(d.get("takeaway"), 60),
            "duration": narration_seconds(narration)}


# ----------------------------------------------------------------------------- jobs
def update(job_id: str, **kw):
    with jobs_lock:
        jobs[job_id].update(kw)


def build_scene(job_id: str, n: int, total: int, d: dict) -> dict:
    title = _short(d.get("title"), 44) or f"Part {n}"
    narration = str(d.get("narration") or title)
    choices = [str(c) for c in (d.get("choices") or [])][:4]
    if len(choices) < 2:
        choices = ["I understand this part", "I need to see it again"]
    ci = d.get("correct_index", 0)
    scene = {
        "scene_number": n,
        "title": title,
        "narration": narration,
        "assessment": {"multiple_choice": {
            "question": d.get("question") or f"Did this explain {title.lower()}?",
            "choices": choices,
            "correct_index": int(ci) if str(ci).isdigit() and int(ci) < len(choices) else 0,
        }},
        "video_url": None,
    }
    out = MEDIA / job_id / f"Scene{n}.mp4"
    spec = normalize_spec(d, title, narration)
    ok, err = render(spec_code(spec), out)
    if not ok:  # the engine skips bad steps itself; this catches anything else: no steps, then plain text
        print(f"scene {n} render failed: {err[-600:]}", flush=True)
        ok, err = render(spec_code({**spec, "steps": []}), out)
    if not ok:
        ok, _ = render(safe_scene(n, title, narration), out)
    if ok:
        scene["video_url"] = f"/media/{job_id}/Scene{n}.mp4"
    with jobs_lock:
        jobs[job_id]["done_scenes"] += 1
        done = jobs[job_id]["done_scenes"]
    update(job_id, stage=f"Animated scene {done} of {total}", progress=0.35 + 0.65 * done / total)
    return scene


def run_job(job_id: str, req: str, key: str | None):
    try:
        update(job_id, status="running", stage="Writing the lesson", progress=0.05)
        lesson = {}
        for _ in range(2):  # one LLM call per lesson; retry once if the reply is unusable
            try:
                lesson = ask_json(LESSON.format(req=req.replace('"', "'")[:500]), key, max_tokens=8000)
            except (FreeQuota, BadKey, NeedKey):
                raise
            except Exception as e:
                print(f"lesson reply unusable: {e}", flush=True)
            if [x for x in lesson.get("scenes", []) if isinstance(x, dict) and x.get("title")]:
                break
        scenes = [x for x in lesson.get("scenes", []) if isinstance(x, dict) and x.get("title")][:3]
        if not scenes:
            raise RuntimeError("Could not plan a lesson for that request. Try rephrasing it.")
        update(job_id, topic=lesson.get("topic", req), audience=lesson.get("audience", ""),
               stage="Animating scenes", progress=0.35)
        futures = [pool.submit(build_scene, job_id, i + 1, len(scenes), x) for i, x in enumerate(scenes)]
        update(job_id, status="done", stage="Ready", progress=1.0, scenes=[f.result() for f in futures])
        with jobs_lock:
            recent[cache_key(req)] = job_id
    except NeedKey:
        update(job_id, status="error", stage="Failed", error="Add your Gemini API key to generate lessons.", code="NEED_KEY")
    except FreeQuota as e:
        update(job_id, status="error", stage="Failed", error=str(e), code="NEED_KEY")
    except BadKey as e:
        update(job_id, status="error", stage="Failed", error=str(e), code="BAD_KEY")
    except Exception as e:
        update(job_id, status="error", stage="Failed", error=str(e))


def cache_key(req: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", req.lower()).strip()


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
    lang: str = "en-IN"
    message: str
    lesson: str = ""
    content: str = ""
    question: str = ""
    history: list[dict] = []


class TtsIn(BaseModel):
    text: str
    lang: str = "en-IN"


class TranslateIn(BaseModel):
    texts: list[str]
    lang: str = "en-IN"


@app.get("/health")
def health():
    return {"ok": True, "server_key": bool(GEMINI_KEY), "nvidia": bool(NVIDIA_KEY), "free_llm": FREE_URL, "murf": bool(MURF_KEY), "jobs": len(jobs)}


@app.post("/generate")
def generate(body: GenerateIn, x_gemini_key: str | None = Header(default=None)):
    req = body.prompt.strip()
    if not req:
        raise HTTPException(400, "Tell me what you want to learn.")
    with jobs_lock:
        prev = jobs.get(recent.get(cache_key(req), ""))
        if prev and prev["status"] == "done":
            return {"job_id": prev["id"]}
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
              "Answer in 2 to 4 short sentences. Don't give away the quiz answer directly; guide them."
              + (f" Reply in {LANGS[body.lang][0]}." if body.lang in LANGS and body.lang != "en-IN" else ""))
    try:
        return {"reply": ask(prompt, x_gemini_key, temperature=0.7, max_tokens=400)}
    except (NeedKey, FreeQuota):
        raise HTTPException(401, {"code": "NEED_KEY", "message": "The tutor is busy right now. Try again in a minute."})
    except BadKey as e:
        raise HTTPException(401, {"code": "BAD_KEY", "message": str(e)})
    except Exception:
        raise HTTPException(502, "The tutor is busy, try again in a moment.")


def llm_translate(texts: list[str], language: str) -> list[str]:
    prompt = (f"Translate each string in this JSON array into {language}. Keep numbers, code and technical "
              f"terms like node, head, tail as they are. Return JSON {{\"texts\": [...]}} with the same order "
              f"and length.\n{json.dumps(texts, ensure_ascii=False)}")
    out = ask_json(prompt, None, temperature=0.2, max_tokens=3000).get("texts") or []
    return [str(o) for o in out][:len(texts)] + texts[len(out):]


@app.get("/languages")
def languages():
    return [{"code": k, "name": v[0], "native": v[1]} for k, v in LANGS.items()]


@app.post("/translate")
def translate(body: TranslateIn):
    """Translate lesson text with Murf. English (or no key) returns the text unchanged."""
    texts = [t if isinstance(t, str) else "" for t in body.texts][:40]
    if body.lang not in LANGS or body.lang == "en-IN" or not MURF_KEY:
        return {"texts": texts}
    todo = [t for t in dict.fromkeys(texts) if t.strip() and (body.lang, t) not in _translations]
    if todo:
        try:
            r = requests.post("https://api.murf.ai/v1/text/translate",
                              headers={"api-key": MURF_KEY, "Content-Type": "application/json"},
                              json={"targetLanguage": body.lang, "texts": todo}, timeout=60)
            if r.status_code == 400:  # Murf can't translate into this language; use the LLM instead
                out = llm_translate(todo, LANGS[body.lang][0])
            else:
                r.raise_for_status()
                out = [item.get("translated_text") or src for src, item in zip(todo, r.json().get("translations", []))]
            for src, t in zip(todo, out):
                _translations[(body.lang, src)] = t or src
        except Exception as e:
            print(f"translate failed: {e}", flush=True)
            raise HTTPException(503, "Translation unavailable right now")
    if len(_translations) > 5000:
        _translations.clear()
    return {"texts": [_translations.get((body.lang, t), t) for t in texts]}


@app.post("/tts")
def tts(body: TtsIn):
    if not MURF_KEY:
        raise HTTPException(503, "No TTS key, use the browser voice")
    try:
        text = body.text.strip()[:2500]
        voice = LANGS.get(body.lang, LANGS["en-IN"])[2]
        name = hashlib.sha1(f"{voice}|{text}".encode()).hexdigest()[:16] + ".mp3"
        out = MEDIA / "tts" / name
        if not out.exists():
            r = requests.post("https://api.murf.ai/v1/speech/stream",
                              headers={"api-key": MURF_KEY, "Content-Type": "application/json"},
                              json={"text": text, "voiceId": voice, "model": MURF_MODEL, "format": "MP3"},
                              timeout=60)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]} (key len {len(MURF_KEY)}, starts {MURF_KEY[:4]})")
            if "audio" not in r.headers.get("content-type", "") or not r.content:
                raise ValueError("no audio")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(r.content)
        return {"audio_url": f"/media/tts/{name}"}
    except Exception as e:
        print(f"murf failed: {e}", flush=True)
        raise HTTPException(503, "TTS unavailable, use the browser voice")
