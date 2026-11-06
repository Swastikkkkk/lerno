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
FIX_ATTEMPTS = 2

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
            with free_slots:
                r = requests.post(FREE_URL, json=body, headers=headers, timeout=150)
            if r.status_code == 402:
                raise FreeQuota("Lerno is busy right now. Try again in a minute.")
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


def split_scene(raw: str) -> dict:
    """Scene replies are a JSON object followed by a ```python block; tolerate the old all-JSON shape too."""
    code_m = re.search(r"```(?:python)?\s*(.*?)```", raw, re.S)
    meta_part = raw[:code_m.start()] if code_m else raw
    try:
        d = _loads(meta_part)
    except Exception:
        d = {}
    if code_m:
        d["code"] = code_m.group(1)
    return d


def ask_json(prompt: str, key: str | None, **kw) -> dict:
    return _loads(ask(prompt, key, as_json=True, **kw))


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

Reply in exactly two parts:
1. A JSON object with:
   "narration": 2 to 4 friendly sentences a narrator reads while the animation plays,
   "question": one multiple choice question that checks this scene,
   "choices": exactly 4 short answer options, plain text, no letters in front,
   "correct_index": index (0-3) of the right option.
2. Then the complete Manim Community v0.19 Python file in a ```python code block (NOT inside the JSON).

Rules for "code":
- Start with `from manim import *` and define exactly one class `Scene{n}(LernoScene)` with `construct`.
- LAYOUT IS HANDLED FOR YOU. Use these helpers, never position text by hand:
    self.set_title("Short title")                      # top strip
    d = VGroup(...).arrange(RIGHT, buff=0.8)            # build the diagram as ONE VGroup, centered at ORIGIN
    self.show(d)                                        # fits and centers it, animates Create
    self.label(d[2], "New tail", DOWN)                 # short label next to an object; it finds a free side
    self.label(d[3], r"k=2", UP, tex=True)
    self.note(r"k \bmod n = 2")                        # formulas go to the bottom row (max 3)
    self.clear_labels()
  Animate changes with self.play(...) on parts of d (Indicate, Transform, d[i].animate.set_color(...), GrowArrow).
- Labels: 1 to 4 words each, at most 4 per scene. Formulas only through self.note.
- Keep the screen calm: at most 6 separate things visible at once. Before a new idea, FadeOut the old group.
  Build rows with VGroup(...).arrange(RIGHT, buff=0.6) and stacks with .arrange(DOWN, buff=0.5): never place
  two shapes by hand on top of or touching each other. Everything is centered by default; don't shift it aside.
- Use only: Text, MathTex, Circle, Square, Rectangle, RoundedRectangle, Dot, Line, Arrow, Vector, NumberPlane,
  Axes, VGroup, Brace, SurroundingRectangle, and animations Create, Write, FadeIn, FadeOut, Transform,
  GrowArrow, Indicate, self.wait.
- No images, SVGs, sounds, external files, updaters, ValueTracker, always_redraw or 3D.
- Plain ASCII inside Text(). In MathTex wrap words in \\text{{}}, e.g. r"\\text{{new tail}}.next = \\text{{null}}".
- Make the diagram big and clear: few, large shapes (circles radius 0.5+, squares side 0.8+), font_size 32+ inside shapes.
- Total runtime 8 to 14 seconds. End with self.wait(1).
"""

FIX = """This Manim Community v0.19 file failed to render.

```python
{code}
```

Error (last lines):
```
{error}
```

Reply with only the corrected complete file in one ```python code block. Keep the class name {cls}
and keep using the LernoScene helpers (set_title, show, label, note, clear_labels).
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


# Injected into every generated scene: before each play() it moves new labels off anything they
# would overlap, then scales/shifts everything on screen so nothing leaves the frame.
LERNO_BASE = r"""
import re
from manim.animation.animation import prepare_animation


class LernoScene(Scene):
    # zones (Manim units, frame is ~14.2 x 8): title strip on top, diagram in the middle, notes row at the bottom
    _W, _H = 13.0, 7.2
    TOP_Y, DIAGRAM_TOP, DIAGRAM_BOTTOM, NOTES_Y = 3.3, 2.4, -1.7, -2.75
    GAP = 0.45          # minimum clear space between separate elements (~1 cm on a laptop screen)
    SHAPE_GAP = 0.25    # between shapes the code placed itself

    def setup(self):
        self._title = None
        self._diagram = None
        self._labels_on = []
        self._notes = VGroup()

    # ---------------------------------------------------------------- helpers for the generated code
    def set_title(self, text):
        t = Text(text, font_size=38, weight=BOLD)
        t.scale_to_fit_width(min(t.width, 11.5)).move_to(UP * self.TOP_Y)
        if self._title is None:
            self.play(Write(t), run_time=0.8)
        else:
            self.play(Transform(self._title, t), run_time=0.6)
            t = self._title
        self._title = t
        return t

    def show(self, diagram, anim=Create, run_time=1.2):
        if self._diagram is not None and self._diagram in self.mobjects:
            self.play(FadeOut(self._diagram), *[FadeOut(l) for l in self._labels_on], run_time=0.5)
            self._labels_on = []
        self._spread(diagram)
        self._fit_diagram(diagram)
        self._diagram = diagram
        self.play(anim(diagram), run_time=run_time)
        return diagram

    def label(self, target, text, direction=UP, tex=False, color=WHITE):
        lab = MathTex(text, color=color) if tex else Text(text, font_size=26, color=color)
        lab.scale_to_fit_height(min(lab.height, 0.42))
        self._place(lab, target, direction)
        self._labels_on.append(lab)
        self.play(FadeIn(lab, shift=direction * 0.15), run_time=0.5)
        return lab

    def note(self, text, tex=True):
        plain = re.sub(r"\\\\text\{([^}]*)\}", r"\1", text)
        sentence = len(re.findall(r"[A-Za-z]{3,}", plain)) >= 3 and not re.search(r"[\\^_]", plain)
        if sentence or not tex:
            n = Text(plain.replace("\\", ""), font_size=28)
        else:
            n = MathTex(text)
        n.scale_to_fit_height(min(n.height, 0.5))
        if n.width > 11:
            n.scale_to_fit_width(11)
        if len(self._notes) >= 2 or (len(self._notes) == 1 and self._notes[0].width + n.width > 10.5):
            old = self._notes[0]
            self._notes.remove(old)
            self.play(FadeOut(old), run_time=0.3)
        self._notes.add(n)
        target = self._notes.copy().arrange(RIGHT, buff=1.0).move_to(UP * self.NOTES_Y)
        if target.width > 12:
            target.scale_to_fit_width(12)
        if target.height < 0.3:
            target.scale_to_fit_height(0.3)
        anims = [m.animate.move_to(t.get_center()).scale(t.height / max(m.height, 1e-3)) for m, t in zip(self._notes[:-1], target[:-1])]
        n.move_to(target[-1]).scale(target[-1].height / max(n.height, 1e-3))
        self.play(*anims, FadeIn(n, shift=UP * 0.15), run_time=0.6)
        return n

    def clear_labels(self):
        if self._labels_on:
            self.play(*[FadeOut(l) for l in self._labels_on], run_time=0.4)
        self._labels_on = []

    # ---------------------------------------------------------------- geometry
    @staticmethod
    def _box(m):
        return m.get_left()[0], m.get_right()[0], m.get_bottom()[1], m.get_top()[1]

    def _hits(self, a, b, pad=0.12):
        l1, r1, b1, t1 = self._box(a)
        l2, r2, b2, t2 = self._box(b)
        return l1 < r2 + pad and l2 < r1 + pad and b1 < t2 + pad and b2 < t1 + pad

    def _contains(self, a, b, slack=0.05):
        l1, r1, b1, t1 = self._box(a)
        l2, r2, b2, t2 = self._box(b)
        return l1 <= l2 + slack and r2 <= r1 + slack and b1 <= b2 + slack and t2 <= t1 + slack

    @staticmethod
    def _is_connector(m):
        return isinstance(m, (Line, Arrow, DashedLine, Brace, Vector)) or type(m).__name__ in ("CurvedArrow", "DoubleArrow", "Arc", "ArcBetweenPoints")

    @staticmethod
    def _is_highlight(m):
        # an empty outline (SurroundingRectangle, a ring around a node): meant to sit on top of something
        try:
            return isinstance(m, VMobject) and not m.submobjects and m.get_fill_opacity() < 0.05 and not isinstance(m, (Text, MathTex, Tex))
        except Exception:
            return False

    def _is_text(self, m):
        return isinstance(m, (Text, MarkupText, MathTex, Tex)) or (
            isinstance(m, VGroup) and len(m) > 0 and all(isinstance(x, (Text, MarkupText, MathTex, Tex)) for x in m))

    def _parts(self, m):
        # a group is judged by its pieces, so a label can sit next to one node of a list
        subs = [s for s in m.submobjects if s.width + s.height > 0.05] if isinstance(m, (VGroup, Group)) and not self._is_text(m) else []
        return subs if len(subs) > 1 else [m]

    def _inside(self, m):
        l, r, b, t = self._box(m)
        return l > -self._W / 2 and r < self._W / 2 and b > -3.7 and t < self.TOP_Y - 0.35

    # ---------------------------------------------------------------- layout internals
    def _spread(self, d):
        # siblings that partly overlap (not one inside another) get re-laid out in a row or grid with a real gap
        kids = [k for k in d.submobjects if not self._is_connector(k)]
        if len(kids) < 2 or len(kids) != len(d.submobjects):
            return  # connectors depend on the original positions; leave those layouts alone
        def overlap(a, b):  # share of the smaller box that is covered; touching cells (arrays) score ~0
            l1, r1, b1, t1 = self._box(a)
            l2, r2, b2, t2 = self._box(b)
            w, h = min(r1, r2) - max(l1, l2), min(t1, t2) - max(b1, b2)
            if w <= 0 or h <= 0:
                return 0.0
            small = min((r1 - l1) * (t1 - b1), (r2 - l2) * (t2 - b2)) or 1e-6
            return w * h / small
        clash = any(overlap(a, b) > 0.12 and not self._contains(a, b) and not self._contains(b, a)
                    for i, a in enumerate(kids) for b in kids[i + 1:])
        if not clash:
            return
        xs = [k.get_center()[0] for k in kids]
        ys = [k.get_center()[1] for k in kids]
        wide = (max(xs) - min(xs)) >= (max(ys) - min(ys))  # keep the direction the code was going for
        if not wide:
            kids.sort(key=lambda k: -k.get_center()[1])
            d.submobjects = kids
        else:
            kids.sort(key=lambda k: k.get_center()[0])
            d.submobjects = kids
        if len(kids) <= 6:
            d.arrange(RIGHT if wide else DOWN, buff=self.GAP + 0.15)
        else:
            d.arrange_in_grid(buff=self.GAP + 0.15)

    def _fit_diagram(self, d):
        h_room = self.DIAGRAM_TOP - self.DIAGRAM_BOTTOM - 1.0  # leave space for labels above/below
        k = min(10.0 / max(d.width, 1e-3), h_room / max(d.height, 1e-3), 2.2)
        d.scale(k)
        d.move_to(UP * (self.DIAGRAM_TOP + self.DIAGRAM_BOTTOM) / 2)

    def _obstacles(self, exclude):
        obs = []
        for o in self.mobjects:
            if o is exclude or self._is_connector(o):
                continue
            obs += self._parts(o)
        return obs

    def _place(self, lab, target, direction):
        dirs = [direction, UP, DOWN, RIGHT, LEFT, UR, UL, DR, DL]
        seen, order = set(), []
        for d in dirs:
            k = tuple(np.round(d, 2))
            if k not in seen:
                seen.add(k)
                order.append(d)
        obs = [o for o in self._obstacles(lab) if o is not target and o not in target.get_family()]
        for buff in (0.25, 0.5, 0.8):
            for d in order:
                lab.next_to(target, d, buff=buff)
                if self._inside(lab) and not any(self._hits(lab, o, pad=self.GAP * 0.6) for o in obs):
                    return
        lab.next_to(target, direction, buff=0.25)

    def _free(self, m, obs, pad):
        return not any(self._hits(m, o, pad=pad) for o in obs if o is not m)

    def _nudge(self, m, obs, pad):
        # move m to the closest free spot around where the code put it; shrink it a little if nothing fits
        if self._free(m, obs, pad):
            return
        home = m.get_center().copy()
        for shrink in (1.0, 0.85, 0.7):
            if shrink < 1.0:
                m.move_to(home).scale(shrink)
            sx, sy = m.width + pad, m.height + pad
            for step in (1, 2, 3, 4):
                for d in (DOWN, UP, RIGHT, LEFT, DR, DL, UR, UL):
                    m.move_to(home + np.array([d[0] * sx, d[1] * sy, 0]) * step * 0.6)
                    if self._inside(m) and self._free(m, obs, pad):
                        return
        m.move_to(home)

    def _tidy(self, anims):
        # safety net for every play(): gaps between elements, wide things centered, nothing outside the frame
        try:
            keep = {id(x) for x in [self._title, self._diagram] + self._labels_on + list(self._notes) if x is not None}
            placed_now = []
            todo = []
            for a in anims:
                m = getattr(a, "mobject", None)
                if m is None or isinstance(a, FadeOut):
                    continue
                t = getattr(a, "target_mobject", None)
                if t is not None and t is not m and self._is_text(t) and t not in self.mobjects:
                    todo.append((t, m))  # text that something is turning into: place it like new text
                if m in self.mobjects or id(m) in keep or self._is_connector(m) or self._is_highlight(m):
                    continue
                todo.append((m, None))
            for m, source in todo:
                if self._is_text(m) and m.height < 0.26:
                    m.scale_to_fit_height(0.26)  # never smaller than readable
                if self._is_text(m) and source is None:
                    for o in list(self.mobjects):  # same spot: an updated value replaces the old one
                        if o is not m and o is not source and id(o) not in keep and self._is_text(o) and self._hits(m, o, pad=0.02) \
                                and abs(o.get_center()[1] - m.get_center()[1]) < 0.15 and abs(o.get_center()[0] - m.get_center()[0]) < 0.5:
                            self.remove(o)
                else:
                    if isinstance(m, (VGroup, Group)):
                        c0 = m.get_center().copy()
                        self._spread(m)  # pieces drawn on top of each other get a real gap
                        m.move_to(c0)
                    others = [o for o in self.mobjects if o is not self._title and not self._is_text(o) and not self._is_connector(o)]
                    if not others and abs(m.get_center()[0]) > 0.6:
                        m.set_x(0)  # first thing on screen: center it
                skip = set(id(x) for x in source.get_family()) if source is not None else set()
                obs = []
                for o in self._obstacles(m) + placed_now:
                    if id(o) in skip:
                        continue
                    if self._is_text(o) and self._is_text(m):
                        obs.append(o)  # two texts never share space
                        continue
                    elif (self._contains(o, m) and o.width * o.height > 1.6 * m.width * m.height) or \
                            (self._contains(m, o) and m.width * m.height > 1.6 * o.width * o.height):
                        continue  # text inside its box, box around its content: intentional
                    obs.append(o)
                self._nudge(m, obs, self.GAP if self._is_text(m) else self.SHAPE_GAP)
                placed_now.append(m)
            every = list(self.mobjects)
            for a in anims:
                m = getattr(a, "mobject", None)
                if m is not None and not isinstance(a, FadeOut) and m not in every:
                    every.append(m)
                t = getattr(a, "target_mobject", None)
                if t is not None:
                    every.append(t)
            if not every:
                return
            g = Group(*every)
            k = min(1.0, self._W / max(g.width, 1e-3), 7.4 / max(g.height, 1e-3))
            if k < 1.0:
                c = g.get_center()
                for m in every:
                    m.scale(k, about_point=c)
                g = Group(*every)
            dx = max(0.0, -self._W / 2 - g.get_left()[0]) - max(0.0, g.get_right()[0] - self._W / 2)
            dy = max(0.0, -3.7 - g.get_bottom()[1]) - max(0.0, g.get_top()[1] - 3.7)
            if dx or dy:
                for m in every:
                    m.shift(RIGHT * dx + UP * dy)
        except Exception:
            pass

    def _settle_moves(self, anims):
        # things moved with .animate or turned into another shape: check where they END UP, against where
        # everything else ends up, and shift the end spot if it would land on top of something
        try:
            moving = {}
            for a in anims:
                m = getattr(a, "mobject", None)
                if m is None or isinstance(a, FadeOut):
                    continue
                if isinstance(a, MoveToTarget) and getattr(m, "target", None) is not None:
                    moving[id(m)] = (m, m.target)
                else:
                    t = getattr(a, "target_mobject", None)
                    if t is not None and t is not m and not self._is_text(t) and not self._is_connector(t):
                        moving[id(m)] = (m, t)
            if not moving:
                return
            finals, seen = [], set()
            for o in self.mobjects:
                if self._is_connector(o) or o is self._title:
                    continue
                for p in self._parts(o):
                    finals.append((p, moving[id(p)][1] if id(p) in moving else p))
                    seen.add(id(p))
            for k, (m, t) in moving.items():
                if k not in seen:
                    finals.append((m, t))
            for m, t in list(moving.values()):
                if self._is_highlight(m) or self._is_connector(m):
                    continue
                fam = {id(x) for x in m.get_family()}
                others = []
                for p2, t2 in finals:
                    if id(p2) in fam or id(m) in {id(x) for x in p2.get_family()}:
                        continue
                    if self._is_text(t2) and self._is_text(t):
                        others.append(t2)
                    elif not ((self._contains(t2, t) and t2.width * t2.height > 1.6 * t.width * t.height) or
                              (self._contains(t, t2) and t.width * t.height > 1.6 * t2.width * t2.height)):
                        others.append(t2)
                self._nudge(t, others, self.GAP if self._is_text(t) else self.SHAPE_GAP)
        except Exception:
            pass

    def add(self, *mobs):
        # things added without an animation get the same layout pass (play() adds its own mobjects; skip those)
        if not getattr(self, "_in_play", False) and hasattr(self, "_notes"):
            class _Added:
                def __init__(self, m):
                    self.mobject = m
            self._tidy([_Added(m) for m in mobs if m not in self.mobjects])
        return super().add(*mobs)

    def play(self, *anims, **kw):
        anims = [prepare_animation(a) for a in anims]
        self._tidy(anims)
        self._settle_moves(anims)
        self._in_play = True
        try:
            return super().play(*anims, **kw)
        finally:
            self._in_play = False
"""


def clean_code(code: str) -> str:
    code = code.strip()
    m = re.search(r"```(?:python)?\s*(.*?)```", code, re.S)
    if m:
        code = m.group(1)
    code = re.sub(r"^\s*from manim import \*\s*$", "", code, flags=re.M)
    code = re.sub(r"class (Scene\d+)\(\s*Scene\s*\)", r"class \1(LernoScene)", code)
    return "from manim import *\n" + LERNO_BASE + "\n" + code


# ----------------------------------------------------------------------------- jobs
def update(job_id: str, **kw):
    with jobs_lock:
        jobs[job_id].update(kw)


def build_scene(job_id: str, plan: dict, i: int, s: dict, key: str | None) -> dict:
    n, total = i + 1, len(plan["scenes"])
    cls = f"Scene{n}"
    try:
        d = {}
        for _ in range(2):  # one retry if the reply can't be parsed
            raw = ask(SCENE.format(topic=plan["topic"], audience=plan["audience"], n=n, total=total,
                                   title=s["title"], idea=s["idea"]), key, max_tokens=6000)
            d = split_scene(raw)
            if d.get("code"):
                break
    except FreeQuota:
        raise
    except Exception as e:
        print(f"scene {n} generation failed: {e}", flush=True)
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
            code = clean_code(ask(FIX.format(code=code, error=err, cls=cls), key, temperature=0.3, max_tokens=6000))
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
    except FreeQuota as e:
        update(job_id, status="error", stage="Failed", error=str(e), code="NEED_KEY")
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
