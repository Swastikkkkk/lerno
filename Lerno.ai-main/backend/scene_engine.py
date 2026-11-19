"""ExplAInr scene engine.

The LLM never writes Manim code. It returns a small JSON spec (a visual + a list of steps) and this
file draws it. Every position is computed here, so nothing can land on top of anything else:

  * fixed zones: title strip, diagram zone, one note line, and an empty band at the bottom that the
    player's captions sit on
  * every label has a slot next to its target and is checked against everything on screen before it
    appears; if no slot is free it becomes the note instead of overlapping
  * structural changes (insert, remove, swap) re-run the layout and animate to it
  * pacing follows the narration length so the video and the voice end together

main.py writes `SPEC = {...}` at the bottom of a copy of this file and renders class Lesson.
"""
from manim import *
import math
import re

import numpy as np

BG = "#000000"
FG = "#F5F5F7"
DIM = "#8E8E93"
LINE = "#D1D1D6"
ACC = "#0A84FF"
HOT = "#FFD60A"
GOOD = "#30D158"
BAD = "#FF453A"
PALETTE = [ACC, "#FF9F0A", GOOD, "#BF5AF2", "#64D2FF", HOT]
COLORS = {"accent": ACC, "blue": ACC, "yellow": HOT, "highlight": HOT, "good": GOOD, "green": GOOD,
          "bad": BAD, "red": BAD, "orange": "#FF9F0A", "purple": "#BF5AF2"}

config.background_color = BG

# frame is 14.22 x 8 (y from -4 to 4)
TITLE_Y = 3.3
ZONE_TOP, ZONE_BOT = 2.6, -1.35      # diagram and its labels live here
NOTE_Y = -1.9                         # one line of text under the diagram
SAFE_BOT = -2.35                      # the player's caption bar covers everything below this
MAXW = 12.6
GAP = 0.18                            # minimum clear space between two separate things
LABEL_H = 0.32


# ----------------------------------------------------------------------------- text helpers
def clean(s, n=48):
    s = re.sub(r"\s+", " ", str(s if s is not None else "")).strip()
    return s[:n]


def txt(s, size=30, color=FG, weight=NORMAL, n=48):
    s = clean(s, n) or " "
    try:
        return Text(s, font_size=size, color=color, weight=weight)
    except Exception:
        return Text(re.sub(r"[^\x20-\x7e]", "", s) or " ", font_size=size, color=color, weight=weight)


SUPERS = {"²": "^2", "³": "^3", "¹": "^1", "⁰": "^0", "⁴": "^4", "ⁿ": "^n", "×": r"\times ", "·": r"\cdot ",
          "≤": r"\le ", "≥": r"\ge ", "≠": r"\ne ", "π": r"\pi ", "Δ": r"\Delta ", "θ": r"\theta ", "→": r"\to "}


def tex(s, color=FG, size=48):
    orig = s = str(s or "").strip().strip("$")
    for k, v in SUPERS.items():
        s = s.replace(k, v)
    if not s:
        return txt(" ")
    try:
        return MathTex(s, color=color, font_size=size)
    except Exception:  # LaTeX failed: show the text as written (Pango draws the unicode fine)
        s = orig
        plain = re.sub(r"\\text\{([^}]*)\}", r"\1", s)
        plain = re.sub(r"\\[a-zA-Z]+", " ", plain).replace("^", "").replace("{", "").replace("}", "")
        return txt(plain, 30, color)


def looks_tex(s):
    """Formula (MathTex) or sentence (Text)? Any real word means a sentence, unless it is clearly LaTeX."""
    s = str(s)
    words = re.findall(r"(?<![\\a-zA-Z])[A-Za-z]{3,}", re.sub(r"\\text\{[^}]*\}", "", s))
    if re.search(r"\\[a-zA-Z]+|[\^_]", s):
        return len(words) <= 2
    return "=" in s and not words


def fit(m, w=None, h=None):
    k = 1.0
    if w and m.width > w:
        k = min(k, w / m.width)
    if h and m.height > h:
        k = min(k, h / m.height)
    if k < 1.0:
        m.scale(k)
    return m


def box(m):
    return m.get_left()[0], m.get_right()[0], m.get_bottom()[1], m.get_top()[1]


def point_hit(a, mob, pad=0.06):
    """True if any drawn point of mob (a curve, an axis) falls inside a's box."""
    l, r, b, t = box(a)
    try:
        pts = mob.get_all_points()
    except Exception:
        return False
    if len(pts) == 0:
        return False
    x, y = pts[:, 0], pts[:, 1]
    return bool(np.any((x > l - pad) & (x < r + pad) & (y > b - pad) & (y < t + pad)))


def hits(a, b, pad=GAP):
    l1, r1, b1, t1 = box(a)
    l2, r2, b2, t2 = box(b)
    return l1 < r2 + pad and l2 < r1 + pad and b1 < t2 + pad and b2 < t1 + pad


def in_zone(m, top=ZONE_TOP, bot=ZONE_BOT):
    l, r, b, t = box(m)
    return l >= -MAXW / 2 - 0.05 and r <= MAXW / 2 + 0.05 and b >= bot - 0.05 and t <= top + 0.05


def make_label(text, color=FG):
    t = txt(text, 26, color, n=28)
    t.scale_to_fit_height(LABEL_H) if t.height > LABEL_H else None
    bg = BackgroundRectangle(t, color=BG, fill_opacity=0.92, buff=0.07, stroke_width=0)
    g = VGroup(bg, t)
    g.text = clean(text, 28)
    return g


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-6 else np.array([0.0, 1.0, 0.0])


def as_int(v, default=None):
    try:
        return int(v)
    except Exception:
        return default


# ----------------------------------------------------------------------------- base visual
class Visual:
    """Owns the diagram, its labels and how each step op is drawn."""

    def __init__(self, sc, spec):
        self.sc = sc
        self.spec = spec
        self.labels = []          # dicts: {mob, target, side, text}

    # each subclass: build() -> list of intro animations; obstacles(); target(t); anchor(...)
    def obstacles(self):
        return []

    def everything(self, skip=()):
        out = [o for o in self.obstacles() if o not in skip]
        out += [l["mob"] for l in self.labels if l["mob"] not in skip]
        if self.sc.title is not None:
            out.append(self.sc.title)
        return out

    def label_sides(self, target, side):
        order = [side, "top", "bottom", "right", "left"]
        seen = []
        for s in order:
            if s and s not in seen:
                seen.append(s)
        return seen

    def put(self, lab, target_mob, side, buff=0.16):
        if isinstance(side, str):
            d = {"top": UP, "bottom": DOWN, "left": LEFT, "right": RIGHT}.get(side, UP)
        else:  # radial direction given as a vector
            d = side
        lab.next_to(target_mob, d, buff=buff)

    def place_label(self, lab, tkey, tmob, side, skip=()):
        """Find a free slot for lab next to tmob. Returns True if placed."""
        others = self.everything(skip=(tmob,) + tuple(skip))
        for s in self.label_sides(tkey, side):
            for shrink in (1.0, 0.82):
                trial = lab.copy()
                if shrink < 1:
                    trial.scale(shrink)
                maxw = self.label_width(tkey, s)
                if maxw:
                    fit(trial, w=maxw)
                if trial.height < LABEL_H * 0.6:
                    continue
                self.put(trial, tmob, s)
                if in_zone(trial) and not any(hits(trial, o) for o in others):
                    lab.become(trial)
                    lab.side = s
                    return True
        return False

    def label_width(self, tkey, side):
        return 3.2

    def op_label(self, st):
        t = self.find(st.get("target"))
        text = clean(st.get("text"), 28)
        if t is None or not text:
            return self.sc.say(text) if text else None
        tmob = self.mob_of(t)
        side = st.get("side") if st.get("side") in ("top", "bottom", "left", "right") else self.default_side(t)
        color = COLORS.get(str(st.get("color", "")).lower(), FG)
        # the same text already on screen (e.g. "curr" walking along a list): move it
        same = next((l for l in self.labels if l["text"].lower() == text.lower()), None)
        anims = []
        if same is not None and same["target"] == t:
            return self.wiggle([same["mob"]])
        if same is not None:
            new = same["mob"].copy()
            if self.place_label(new, t, tmob, side, skip=(same["mob"],)):
                same["target"] = t
                anims.append(same["mob"].animate.move_to(new.get_center()))
                self.sc.play(*anims, run_time=0.8)
                return
            self.labels.remove(same)
            anims.append(FadeOut(same["mob"]))
        lab = make_label(text, color)
        placed = self.place_label(lab, t, tmob, side)
        if not placed:
            # every slot around this target is taken: the oldest label on it makes room
            old = next((l for l in self.labels if l["target"] == t), None)
            if old is not None:
                self.labels.remove(old)
                anims.append(FadeOut(old["mob"]))
                placed = self.place_label(lab, t, tmob, side, skip=(old["mob"],))
        if not placed:
            if anims:
                self.sc.play(*anims, run_time=0.4)
            return self.sc.say(text)
        self.labels.append({"mob": lab, "target": t, "text": text})
        self.sc.play(*anims, FadeIn(lab, shift=0.12 * unit(lab.get_center() - tmob.get_center())), run_time=0.7)

    def default_side(self, t):
        return "top"

    def relabel(self, old):
        """After a layout change (labels already faded out): put each label back next to its target."""
        anims = []
        self.labels = []
        for l in old:
            t = self.find_exact(l["target"])
            if t is None:
                continue
            m = l["mob"]
            if self.place_label(m, t, self.mob_of(t), getattr(m, "side", "top")):
                self.labels.append(l)
                anims.append(FadeIn(m))
        return anims

    def find(self, t):
        return None

    def find_exact(self, t):
        return self.find(t)

    def mob_of(self, t):
        return None

    def run(self, st):
        op = str(st.get("op", "")).lower()
        fn = getattr(self, "op_" + op, None)
        if fn is None:
            if st.get("text"):
                self.sc.say(st.get("text"))
            return
        fn(st)

    def wiggle(self, mobs):
        if mobs:
            self.sc.play(*[Indicate(m, color=HOT, scale_factor=1.08) for m in mobs], run_time=0.8)


# ----------------------------------------------------------------------------- node diagrams
class Nodes(Visual):
    """row, stack, cycle, tree, network: nodes + edges + a layout function."""

    def __init__(self, sc, spec):
        super().__init__(sc, spec)
        self.kind = spec["kind"]
        self.style = spec.get("style", "boxes")
        if self.kind == "row" and self.style not in ("boxes", "circles", "cells", "nodes"):
            self.style = "boxes"
        if self.kind in ("tree", "network", "cycle") and self.style not in ("boxes", "circles"):
            self.style = "circles"
        if self.kind == "stack" and self.style not in ("boxes", "cells"):
            self.style = "boxes"
        self.directed = bool(spec.get("arrows", self.kind in ("row", "cycle") and self.style != "cells"))
        if self.style == "cells":
            self.directed = False
        self.k = 1.0
        self.nodes = []        # dicts: id, text, mob, w, h, parent, plain
        self.edges = []        # (id_a, id_b)
        self.edge_mobs = []
        self.extra_edges = [tuple(e) for e in spec.get("edges", [])]
        self.indices = bool(spec.get("indices")) and self.kind in ("row", "stack")
        self.index_mobs = []
        self.hl = set()
        self.seq = 0
        for it in spec.get("items", []):
            self.add_node(it)
        if spec.get("terminal") and self.kind == "row" and self.style != "cells":
            self.add_node({"text": spec["terminal"]}, plain=True)

    # ---- nodes
    def new_id(self):
        self.seq += 1
        return f"n{self.seq}"

    def make_mob(self, text, plain=False):
        if plain:
            t = txt(text, 30, DIM, n=10)
            fit(t, w=1.4, h=0.5)
            g = VGroup(t)
            g.shape = None
            g.label_t = t
            return g, max(t.width, 0.8), 0.6
        t = txt(text, 34, FG, n=14)
        if self.style == "circles":
            fit(t, w=0.95, h=0.5)
            sh = Circle(radius=0.62, color=LINE, stroke_width=3).set_fill(BG, 1)
            w = h = 1.24
        elif self.style == "cells":
            fit(t, w=0.85, h=0.5)
            sh = Square(1.0, color=LINE, stroke_width=3).set_fill(BG, 1)
            w = h = 1.0
        elif self.style == "nodes":
            fit(t, w=2.3, h=0.5)
            vw = max(1.15, t.width + 0.4)
            val = Rectangle(width=vw, height=1.0, color=LINE, stroke_width=3).set_fill(BG, 1)
            ptr = Rectangle(width=0.6, height=1.0, color=LINE, stroke_width=3).set_fill(BG, 1)
            ptr.next_to(val, RIGHT, buff=0)
            dot = Dot(ptr.get_center(), radius=0.07, color=ACC)
            sh = VGroup(val, ptr)
            t.move_to(val)
            g = VGroup(sh, t, dot)
            g.shape, g.label_t, g.dot = sh, t, dot
            return g, vw + 0.6, 1.0
        else:
            fit(t, w=2.4, h=0.5)
            w = max(1.3, t.width + 0.55)
            sh = RoundedRectangle(width=w, height=1.0, corner_radius=0.16, color=LINE, stroke_width=3).set_fill(BG, 1)
            h = 1.0
        t.move_to(sh)
        g = VGroup(sh, t)
        g.shape, g.label_t = sh, t
        return g, w, h

    def add_node(self, it, plain=False, index=None):
        if isinstance(it, dict):
            text, nid, parent = it.get("text", ""), it.get("id"), it.get("parent")
        else:
            text, nid, parent = it, None, None
        nid = clean(nid, 20) or self.new_id()
        if any(n["id"] == nid for n in self.nodes):
            nid = self.new_id()
        mob, w, h = self.make_mob(text, plain)
        n = {"id": nid, "text": clean(text, 14), "mob": mob, "w": w, "h": h,
             "parent": clean(parent, 20) or None, "plain": plain}
        if index is None:
            self.nodes.append(n)
        else:
            self.nodes.insert(index, n)
        return n

    # ---- targets
    def find(self, t):
        if t is None:
            return None
        if isinstance(t, bool):
            return None
        if isinstance(t, (int, float)) or (isinstance(t, str) and re.fullmatch(r"-?\d+", t.strip()) and
                                           not any(n["text"] == t.strip() or n["id"] == t.strip() for n in self.nodes)):
            i = int(t)
            if i < 0:
                i += len(self.nodes)
            return self.nodes[i]["id"] if 0 <= i < len(self.nodes) else None
        s = str(t).strip().lower()
        for key in ("id", "text"):
            for n in self.nodes:
                if n[key].lower() == s:
                    return n["id"]
        return None

    def find_exact(self, t):
        return t if any(n["id"] == t for n in self.nodes) else None

    def node(self, nid):
        return next((n for n in self.nodes if n["id"] == nid), None)

    def mob_of(self, nid):
        n = self.node(nid)
        return n["mob"] if n else None

    def obstacles(self):
        return [n["mob"] for n in self.nodes] + self.index_mobs

    # ---- layout (unit coordinates, before scaling)
    def edge_list(self):
        ids = [n["id"] for n in self.nodes]
        if self.kind in ("row", "stack"):
            return list(zip(ids, ids[1:])) if self.directed or self.spec.get("lines") else []
        if self.kind == "cycle":
            return list(zip(ids, ids[1:] + ids[:1])) if len(ids) > 1 else []
        if self.kind == "tree":
            return [(n["parent"], n["id"]) for n in self.nodes if n["parent"] and self.node(n["parent"])]
        known = set(ids)
        out = []
        for a, b in self.extra_edges:
            a2, b2 = self.find(a), self.find(b)
            if a2 in known and b2 in known and a2 != b2:
                out.append((a2, b2))
        return out

    def layout(self):
        n = len(self.nodes)
        pos = {}
        if self.kind == "row":
            gap = 0.0 if self.style == "cells" else (1.0 if self.directed else 0.6)
            x = 0.0
            for nd in self.nodes:
                pos[nd["id"]] = np.array([x + nd["w"] / 2, 0, 0])
                x += nd["w"] + gap
        elif self.kind == "stack":
            gap = 0.0 if self.style == "cells" else (0.7 if self.directed else 0.3)
            y = 0.0
            for nd in self.nodes:
                pos[nd["id"]] = np.array([0, -(y + nd["h"] / 2), 0])
                y += nd["h"] + gap
        elif self.kind in ("cycle", "network"):
            if n == 1:
                pos[self.nodes[0]["id"]] = np.zeros(3)
            else:
                mw = max(nd["w"] for nd in self.nodes)
                mh = max(nd["h"] for nd in self.nodes)
                # ellipse just big enough that neighbours keep a clear gap
                rx = max(1.5, (mw + 0.8) / (2 * math.sin(math.pi / n)) * 0.9, mw * 0.75 + 0.5)
                ry = max(1.2, (mh + 0.9) / (2 * math.sin(math.pi / n)))
                for i, nd in enumerate(self.nodes):
                    a = math.pi / 2 - 2 * math.pi * i / n
                    pos[nd["id"]] = np.array([rx * math.cos(a), ry * math.sin(a), 0])
        else:  # tree
            kids = {nd["id"]: [] for nd in self.nodes}
            roots = []
            for nd in self.nodes:
                if nd["parent"] in kids and nd["parent"] != nd["id"]:
                    kids[nd["parent"]].append(nd["id"])
                else:
                    roots.append(nd["id"])
            xs = {}
            cursor = [0.0]
            seen = set()

            def walk(i, depth):
                if i in seen:
                    return
                seen.add(i)
                ch = [c for c in kids[i] if c not in seen]
                for c in ch:
                    walk(c, depth + 1)
                placed = [c for c in ch if c in xs]
                if placed:
                    x = (xs[placed[0]][0] + xs[placed[-1]][0]) / 2
                else:
                    x = cursor[0]
                    cursor[0] += 1.7
                xs[i] = (x, depth)

            for r in roots:
                walk(r, 0)
            for i, (x, d) in xs.items():
                pos[i] = np.array([x, -d * 1.5, 0])
        return pos

    def fit_scale(self, pos):
        if not pos:
            return 1.0, np.zeros(3), np.zeros(3)
        ls, rs, bs, ts = [], [], [], []
        for nd in self.nodes:
            p = pos[nd["id"]]
            ls.append(p[0] - nd["w"] / 2)
            rs.append(p[0] + nd["w"] / 2)
            bs.append(p[1] - nd["h"] / 2)
            ts.append(p[1] + nd["h"] / 2)
        w, h = max(rs) - min(ls), max(ts) - min(bs)
        cu = np.array([(max(rs) + min(ls)) / 2, (max(ts) + min(bs)) / 2, 0])
        # room kept free for label slots: above/below for rows, beside for stacks and trees, around for rings
        room_w, room_h = {"row": (0.2, 2 * (LABEL_H + 0.3)), "stack": (5.6, 0.1), "tree": (4.0, 0.2),
                          "cycle": (4.4, 2 * (LABEL_H + 0.3)), "network": (4.4, 2 * (LABEL_H + 0.3))}[self.kind]
        idx_room = 0.5 if self.indices else 0
        avail_w = MAXW - room_w
        avail_h = (ZONE_TOP - ZONE_BOT) - room_h - idx_room
        k = min(avail_w / max(w, 1e-3), avail_h / max(h, 1e-3), 1.3)
        center = np.array([0, (ZONE_TOP + ZONE_BOT) / 2 + (idx_room / 2 if self.indices else 0), 0])
        return k, cu, center

    def screen(self, pos, k, cu, center):
        return {i: center + k * (p - cu) for i, p in pos.items()}

    def edge_points(self, a, b):
        ma, mb = self.mob_of(a), self.mob_of(b)
        pa, pb = ma.get_center(), mb.get_center()
        d = unit(pb - pa)
        if self.style == "nodes" and hasattr(ma, "dot") and self.kind == "row":
            start = ma.dot.get_center()
        else:
            start = self.boundary(ma, d)
        end = self.boundary(mb, -d)
        return start, end

    def boundary(self, m, d):
        c = m.get_center()
        if self.style == "circles" and getattr(m, "shape", None) is not None:
            return c + d * (m.shape.width / 2)
        hw, hh = m.width / 2, m.height / 2
        tx = hw / abs(d[0]) if abs(d[0]) > 1e-6 else 1e9
        ty = hh / abs(d[1]) if abs(d[1]) > 1e-6 else 1e9
        return c + d * min(tx, ty)

    def make_edges(self):
        mobs = []
        for a, b in self.edge_list():
            if not self.node(a) or not self.node(b):
                continue
            s, e = self.edge_points(a, b)
            if np.linalg.norm(e - s) < 0.15:
                continue
            directed = self.directed or self.kind in ("cycle",) or (self.kind == "tree" and self.spec.get("arrows"))
            if self.kind == "cycle" and len(self.nodes) > 2:
                m = CurvedArrow(s, e, angle=-0.45, color=DIM, stroke_width=3, tip_length=0.18)
            elif directed:
                m = Arrow(s, e, buff=0.04, color=DIM, stroke_width=3.5, tip_length=0.2,
                          max_tip_length_to_length_ratio=0.35)
            else:
                m = Line(s, e, color=DIM, stroke_width=3)
            mobs.append(m)
        return mobs

    def make_indices(self):
        out = []
        if not self.indices:
            return out
        for i, nd in enumerate(n for n in self.nodes if not n["plain"]):
            t = txt(str(i), 22, DIM)
            if self.kind == "stack":
                t.next_to(nd["mob"], LEFT, buff=0.18)
            else:
                t.next_to(nd["mob"], DOWN, buff=0.14)
            out.append(t)
        return out

    def build(self):
        pos = self.layout()
        self.k, cu, center = self.fit_scale(pos)
        sp = self.screen(pos, self.k, cu, center)
        for nd in self.nodes:
            nd["mob"].scale(self.k).move_to(sp[nd["id"]])
        self.edge_mobs = self.make_edges()
        self.index_mobs = self.make_indices()
        node_anims = [FadeIn(nd["mob"], scale=0.9) for nd in self.nodes]
        anims = [LaggedStart(*node_anims, lag_ratio=0.15, run_time=1.2)]
        if self.edge_mobs:
            anims.append(LaggedStart(*[GrowArrow(m) if isinstance(m, Arrow) else Create(m) for m in self.edge_mobs],
                                     lag_ratio=0.15, run_time=1.2))
        if self.index_mobs:
            anims.append(FadeIn(VGroup(*self.index_mobs)))
        return anims

    def relayout(self, entering=(), leaving=()):
        """Animate everything to the new layout. entering: node ids that fade in, leaving: mobs that fade out."""
        pos = self.layout()
        k_new, cu, center = self.fit_scale(pos)
        sp = self.screen(pos, k_new, cu, center)
        old_edges, old_idx = self.edge_mobs, self.index_mobs
        old_labels = list(self.labels)
        self.labels = []
        anims = [FadeOut(m) for m in old_edges + old_idx] + [FadeOut(m) for m in leaving]
        anims += [FadeOut(l["mob"]) for l in old_labels]
        moves = []
        for nd in self.nodes:
            m = nd["mob"]
            if nd["id"] in entering:
                m.scale(k_new).move_to(sp[nd["id"]])
                moves.append(FadeIn(m, shift=DOWN * 0.3))
            else:
                target = m.copy().scale(k_new / self.k).move_to(sp[nd["id"]])
                moves.append(Transform(m, target))
        self.k = k_new
        self.sc.play(*anims, run_time=0.35)
        self.sc.play(*moves, run_time=0.9)
        self.edge_mobs = self.make_edges()
        self.index_mobs = self.make_indices()
        after = [GrowArrow(m) if isinstance(m, Arrow) else Create(m) for m in self.edge_mobs]
        if self.index_mobs:
            after.append(FadeIn(VGroup(*self.index_mobs)))
        after += self.relabel(old_labels)
        if after:
            self.sc.play(*after, run_time=0.6)

    # ---- label slots
    def default_side(self, t):
        if self.kind == "stack":
            return "right"
        if self.kind in ("cycle", "network"):
            return "radial"
        if self.kind == "tree":
            return "right"
        return "top"

    def label_sides(self, t, side):
        if self.kind in ("cycle", "network"):
            n = self.node(t)
            c = np.array([0, (ZONE_TOP + ZONE_BOT) / 2, 0])
            d = unit(n["mob"].get_center() - c) if n else UP
            return [d, rotate_vector(d, 0.6), rotate_vector(d, -0.6)]
        if self.kind == "stack":
            base = ["right", "left"]
        elif self.kind == "tree":
            base = ["right", "left"]
        else:
            base = ["top", "bottom"] if not self.indices else ["top"]
        if side in base:
            base.remove(side)
            base.insert(0, side)
        return base

    def label_width(self, t, side):
        if self.kind == "row" and side in ("top", "bottom"):
            n = self.node(t)
            if n is None:
                return 3.0
            # room until the neighbours' label slots: node width plus most of the gap
            gap = 0.0 if self.style == "cells" else (1.0 if self.directed else 0.6)
            return max(1.0, (n["w"] + gap * 0.85) * self.k)
        return 3.2

    # ---- ops
    def set_color(self, nid, color):
        n = self.node(nid)
        if not n or n["mob"].shape is None:
            return None
        sh = n["mob"].shape
        if color is None:
            return sh.animate.set_stroke(LINE, width=3).set_fill(BG, 1)
        return sh.animate.set_stroke(color, width=5).set_fill(color, 0.18)

    def op_highlight(self, st):
        ts = st.get("targets") or [st.get("target")]
        ids = [self.find(t) for t in ts if self.find(t)]
        if not ids:
            return
        color = COLORS.get(str(st.get("color", "")).lower(), HOT)
        anims = [a for a in (self.set_color(i, None) for i in self.hl - set(ids)) if a]
        anims += [a for a in (self.set_color(i, color) for i in ids) if a]
        self.hl = set(ids)
        if anims:
            self.sc.play(*anims, run_time=0.6)
        self.wiggle([self.mob_of(i) for i in ids])

    def op_trace(self, st):
        ids = [self.find(t) for t in (st.get("targets") or []) if self.find(t)]
        if not ids:
            return
        color = COLORS.get(str(st.get("color", "")).lower(), HOT)
        prev = list(self.hl)
        for i in ids[:8]:
            anims = [a for a in (self.set_color(p, None) for p in prev if p != i) if a]
            a = self.set_color(i, color)
            if a:
                anims.append(a)
            if anims:
                self.sc.play(*anims, run_time=0.45)
            prev = [i]
        self.hl = set(prev)

    def op_change(self, st):
        nid = self.find(st.get("target"))
        n = self.node(nid)
        if not n or not clean(st.get("text"), 14):
            return
        m = n["mob"]
        new = txt(st["text"], 34, FG, n=14)
        lt = m.label_t
        fit(new, w=(n["w"] - 0.35) * self.k if not n["plain"] else 1.4 * self.k, h=0.5 * self.k)
        new.move_to(lt)
        n["text"] = clean(st["text"], 14)
        self.sc.play(Transform(lt, new), run_time=0.7)
        self.wiggle([m])

    def op_add(self, st):
        text = st.get("text")
        if not clean(text):
            return
        if len([n for n in self.nodes if not n["plain"]]) >= 8:
            return self.sc.say(f"add {clean(text, 20)}")
        if self.kind == "tree":
            parent = self.find(st.get("parent", st.get("target")))
            n = self.add_node({"text": text, "parent": parent})
        elif self.kind == "network":
            n = self.add_node({"text": text})
            for e in (st.get("connect") or [])[:4]:
                self.extra_edges.append((n["id"], e))
        else:
            last = len(self.nodes) - (1 if self.nodes and self.nodes[-1]["plain"] else 0)
            at = as_int(st.get("at"), last)
            at = max(0, min(at, last))
            n = self.add_node({"text": text}, index=at)
        self.relayout(entering=(n["id"],))
        self.op_highlight({"target": n["id"], "color": st.get("color", "good")})

    def op_remove(self, st):
        nid = self.find(st.get("target"))
        n = self.node(nid)
        if not n or len(self.nodes) <= 1:
            return
        anim = self.set_color(nid, BAD)
        if anim:
            self.sc.play(anim, run_time=0.5)
        self.nodes.remove(n)
        self.hl.discard(nid)
        for nd in self.nodes:
            if nd["parent"] == nid:
                nd["parent"] = n["parent"]
        self.relayout(leaving=(n["mob"],))

    def op_swap(self, st):
        ts = st.get("targets") or []
        if len(ts) < 2:
            return
        a, b = self.find(ts[0]), self.find(ts[1])
        if not a or not b or a == b or self.kind not in ("row", "stack", "cycle"):
            return
        ia = next(i for i, n in enumerate(self.nodes) if n["id"] == a)
        ib = next(i for i, n in enumerate(self.nodes) if n["id"] == b)
        ma, mb = self.nodes[ia]["mob"], self.nodes[ib]["mob"]
        self.sc.play(*[a2 for a2 in (self.set_color(a, HOT), self.set_color(b, HOT)) if a2], run_time=0.4)
        # swap the values, not the boxes: arrows and indices stay put, like an array
        ta, tb = ma.label_t, mb.label_t
        ca, cb = ta.get_center(), tb.get_center()
        self.sc.play(ta.animate.move_to(cb), tb.animate.move_to(ca), path_arc=-math.pi / 2, run_time=0.9)
        ma.remove(ta); mb.remove(tb)
        ma.add(tb); mb.add(ta)
        ma.label_t, mb.label_t = tb, ta
        na, nb = self.nodes[ia], self.nodes[ib]
        na["text"], nb["text"] = nb["text"], na["text"]
        self.sc.play(*[a2 for a2 in (self.set_color(a, None), self.set_color(b, None)) if a2], run_time=0.3)
        self.hl -= {a, b}

    def op_connect(self, st):
        a, b = self.find(st.get("from")), self.find(st.get("to"))
        if not a or not b or a == b:
            return
        if self.kind == "network":
            self.extra_edges.append((a, b))
        elif self.kind == "tree":
            self.node(b)["parent"] = a
        else:
            return
        self.relayout()


# ----------------------------------------------------------------------------- plot
SAFE_NAMES = {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp, "log": np.log, "ln": np.log,
              "sqrt": np.sqrt, "abs": np.abs, "pi": np.pi, "e": np.e, "floor": np.floor, "arctan": np.arctan,
              "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh}


def make_fn(expr):
    e = str(expr or "").lower().replace("^", "**").replace("y=", "").replace("f(x)=", "").strip()
    e = re.sub(r"(\d)\s*([a-z(])", r"\1*\2", e)          # 2x -> 2*x
    e = re.sub(r"\)\s*([a-z(\d])", r")*\1", e)           # )(x -> )*(x
    if not re.fullmatch(r"[0-9a-z_+\-*/(). ]+", e):
        return None
    for name in re.findall(r"[a-z_]+", e):
        if name != "x" and name not in SAFE_NAMES:
            return None
    try:
        code = compile(e, "<f>", "eval")
        f = lambda x: float(eval(code, {"__builtins__": {}}, dict(SAFE_NAMES, x=x)))
        f(0.37)
        return f
    except Exception:
        return None


def nice_step(span):
    raw = span / 5
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class Plot(Visual):
    def __init__(self, sc, spec):
        super().__init__(sc, spec)
        self.fns = []
        for i, f in enumerate(spec.get("functions", [])[:3]):
            fn = make_fn(f.get("expr"))
            if fn:
                self.fns.append({"fn": fn, "label": f.get("label") or f.get("expr"), "color": PALETTE[i % len(PALETTE)],
                                 "mob": None, "legend": None})
        x0, x1 = spec.get("x", [-5, 5])
        if self.fns and spec.get("y") is None:
            ys = []
            for f in self.fns:
                for x in np.linspace(x0, x1, 80):
                    try:
                        y = f["fn"](x)
                        if math.isfinite(y):
                            ys.append(y)
                    except Exception:
                        pass
            ys = sorted(ys)
            if ys:
                lo, hi = ys[int(len(ys) * 0.02)], ys[int(len(ys) * 0.98) - 1 if len(ys) > 1 else 0]
                pad = (hi - lo) * 0.1 or 1
                spec["y"] = [min(0, lo - pad), max(0, hi + pad)] if lo < hi else [lo - 1, hi + 1]
        self.y0, self.y1 = spec.get("y") or [-5, 5]
        self.x0, self.x1 = x0, x1
        self.dots = []

    def obstacles(self):
        out = [self.axes]
        out += [f["legend"] for f in self.fns if f["legend"] is not None and f["legend"] in self.sc.mobjects]
        out += self.dots
        return out

    def build(self):
        legend_w = 0
        legends = []
        for f in self.fns:
            lab = tex(f["label"], f["color"]) if looks_tex(f["label"]) else txt(f["label"], 28, f["color"], n=24)
            fit(lab, w=3.2, h=0.42)
            sw = Line(ORIGIN, RIGHT * 0.45, color=f["color"], stroke_width=5)
            g = VGroup(sw, lab).arrange(RIGHT, buff=0.2)
            f["legend"] = g
            legends.append(g)
            legend_w = max(legend_w, g.width)
        ax_w = min(9.0, MAXW - (legend_w + 0.6 if legends else 0) - 0.4)
        ax_h = ZONE_TOP - ZONE_BOT - 0.4
        xs = nice_step(self.x1 - self.x0)
        ys = nice_step(self.y1 - self.y0)
        cfg = {"color": DIM, "stroke_width": 2, "include_numbers": True, "font_size": 24, "numbers_to_exclude": [0]}
        try:
            self.axes = Axes(x_range=[self.x0, self.x1, xs], y_range=[self.y0, self.y1, ys], x_length=ax_w,
                             y_length=ax_h, tips=False, axis_config=cfg)
        except Exception:  # tick numbers need LaTeX; draw plain axes if it is missing
            cfg["include_numbers"] = False
            self.axes = Axes(x_range=[self.x0, self.x1, xs], y_range=[self.y0, self.y1, ys], x_length=ax_w,
                             y_length=ax_h, tips=False, axis_config=cfg)
        xl = txt(self.spec.get("x_label", "x"), 24, DIM, n=12)
        yl = txt(self.spec.get("y_label", "y"), 24, DIM, n=12)
        xl.next_to(self.axes.x_axis.get_right(), DOWN + RIGHT * 0.2, buff=0.12)
        yl.next_to(self.axes.y_axis.get_top(), RIGHT, buff=0.15)
        group = VGroup(self.axes, xl, yl)
        if legends:
            lg = VGroup(*legends).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
            lg.next_to(group, RIGHT, buff=0.6).align_to(group, UP)
            group.add(lg)
            self.legend = lg
        group.move_to(np.array([0, (ZONE_TOP + ZONE_BOT) / 2, 0]))
        fit(group, w=MAXW, h=ZONE_TOP - ZONE_BOT)
        self.extra = [xl, yl]
        anims = [Create(self.axes, run_time=1.2), FadeIn(xl), FadeIn(yl)]
        self.drawn = set()
        return anims

    def curve(self, f):
        segs, cur = [], []
        span = self.y1 - self.y0
        for x in np.linspace(self.x0, self.x1, 240):
            try:
                y = f["fn"](x)
            except Exception:
                y = float("nan")
            if math.isfinite(y) and self.y0 - span * 0.02 <= y <= self.y1 + span * 0.02:
                cur.append(self.axes.c2p(x, y))
            else:
                if len(cur) > 1:
                    segs.append(cur)
                cur = []
        if len(cur) > 1:
            segs.append(cur)
        g = VGroup()
        for s in segs:
            m = VMobject(color=f["color"], stroke_width=5)
            m.set_points_smoothly(s) if len(s) > 2 else m.set_points_as_corners(s)
            g.add(m)
        return g

    def op_draw(self, st):
        i = as_int(st.get("f", st.get("target", 0)), 0)
        if not (0 <= i < len(self.fns)) or i in self.drawn:
            return
        f = self.fns[i]
        f["mob"] = self.curve(f)
        self.drawn.add(i)
        self.sc.play(Create(f["mob"]), FadeIn(f["legend"]), run_time=1.3)

    def ensure_drawn(self, i):
        if i not in self.drawn:
            self.op_draw({"f": i})

    def op_dot(self, st):
        i = as_int(st.get("f", 0), 0)
        if not (0 <= i < len(self.fns)):
            return
        self.ensure_drawn(i)
        try:
            x = float(st.get("x"))
            y = self.fns[i]["fn"](x)
        except Exception:
            return
        if not (self.x0 <= x <= self.x1 and self.y0 <= y <= self.y1):
            return
        d = Dot(self.axes.c2p(x, y), radius=0.09, color=HOT)
        self.sc.play(FadeIn(d, scale=0.5), run_time=0.5)
        self.dots.append(d)
        text = clean(st.get("text"), 24)
        if text:
            lab = make_label(text, HOT)
            boxes = [l["mob"] for l in self.labels] + self.extra + [self.sc.title]
            boxes += [f["legend"] for f in self.fns if f["legend"] is not None] + [x for x in self.dots if x is not d]
            lines = [self.axes] + [f["mob"] for f in self.fns if f["mob"] is not None]
            for side in (UL, UR, DR, DL, UP, DOWN, LEFT, RIGHT):
                trial = lab.copy().next_to(d, side, buff=0.1)
                if in_zone(trial) and not any(hits(trial, o, pad=0.06) for o in boxes) \
                        and not any(point_hit(trial[1], o) for o in lines):
                    lab.become(trial)
                    self.labels.append({"mob": lab, "target": None, "text": text})
                    self.sc.play(FadeIn(lab), run_time=0.5)
                    return
            self.sc.say(text)

    def op_area(self, st):
        i = as_int(st.get("f", 0), 0)
        if not (0 <= i < len(self.fns)):
            return
        self.ensure_drawn(i)
        try:
            a, b = float(st.get("from", self.x0)), float(st.get("to", self.x1))
            a, b = max(self.x0, min(a, b)), min(self.x1, max(a, b))
            g = self.axes.plot(self.fns[i]["fn"], x_range=[a, b], color=self.fns[i]["color"])
            area = self.axes.get_area(g, x_range=[a, b], color=self.fns[i]["color"], opacity=0.3)
            self.sc.play(FadeIn(area), run_time=0.8)
        except Exception:
            pass

    def op_highlight(self, st):
        i = as_int(st.get("f", st.get("target", 0)), 0)
        if 0 <= i < len(self.fns) and self.fns[i]["mob"] is not None:
            self.sc.play(Indicate(self.fns[i]["mob"], color=HOT), run_time=0.8)

    def op_label(self, st):
        self.sc.say(st.get("text"))


# ----------------------------------------------------------------------------- bars
class Bars(Visual):
    def __init__(self, sc, spec):
        super().__init__(sc, spec)
        self.items = []
        for it in spec.get("items", [])[:8]:
            try:
                v = float(it.get("value", 0))
            except Exception:
                v = 0
            self.items.append({"label": clean(it.get("label"), 12), "value": v})
        self.hl = set()

    def fmt(self, v):
        return str(int(v)) if abs(v - round(v)) < 1e-9 else f"{v:.2g}" if abs(v) < 10 else f"{v:.0f}"

    def geometry(self):
        n = max(len(self.items), 1)
        slot = min(1.6, MAXW / n)
        bw = slot * 0.62
        base = ZONE_BOT + 0.55
        top_room = ZONE_TOP - 0.45 - base
        vmax = max([abs(it["value"]) for it in self.items] + [1e-6])
        x0 = -slot * (n - 1) / 2
        return slot, bw, base, top_room, vmax, x0

    def bar_for(self, i, v):
        slot, bw, base, top_room, vmax, x0 = self.geometry()
        h = max(0.04, top_room * abs(v) / vmax)
        r = Rectangle(width=bw, height=h, stroke_width=0).set_fill(ACC, 0.9)
        r.move_to(np.array([x0 + i * slot, base + h / 2, 0]))
        return r

    def build(self):
        slot, bw, base, top_room, vmax, x0 = self.geometry()
        self.bars, self.vals, self.cats = [], [], []
        for i, it in enumerate(self.items):
            b = self.bar_for(i, it["value"])
            val = txt(self.fmt(it["value"]), 24, FG)
            fit(val, w=slot * 0.95)
            val.next_to(b, UP, buff=0.12)
            cat = txt(it["label"], 24, DIM)
            fit(cat, w=slot * 0.95, h=0.34)
            cat.next_to(np.array([b.get_center()[0], base, 0]), DOWN, buff=0.15)
            self.bars.append(b); self.vals.append(val); self.cats.append(cat)
        self.axis = Line(np.array([x0 - slot / 2, base, 0]), np.array([-x0 + slot / 2, base, 0]), color=DIM, stroke_width=2)
        return [Create(self.axis), LaggedStart(*[GrowFromEdge(b, DOWN) for b in self.bars], lag_ratio=0.12, run_time=1.2),
                FadeIn(VGroup(*self.cats)), FadeIn(VGroup(*self.vals))]

    def obstacles(self):
        return self.bars + self.vals + self.cats + [self.axis]

    def find(self, t):
        i = as_int(t)
        if i is not None and not any(it["label"] == str(t) for it in self.items):
            return i if 0 <= i < len(self.items) else None
        for j, it in enumerate(self.items):
            if it["label"].lower() == str(t).strip().lower():
                return j
        return None

    def op_highlight(self, st):
        ids = [self.find(t) for t in (st.get("targets") or [st.get("target")])]
        ids = [i for i in ids if i is not None]
        color = COLORS.get(str(st.get("color", "")).lower(), HOT)
        anims = [self.bars[i].animate.set_fill(ACC, 0.9) for i in self.hl - set(ids)]
        anims += [self.bars[i].animate.set_fill(color, 1) for i in ids]
        self.hl = set(ids)
        if anims:
            self.sc.play(*anims, run_time=0.6)

    op_trace = op_highlight

    def op_change(self, st):
        i = self.find(st.get("target"))
        if i is None:
            return
        try:
            v = float(st.get("value", st.get("text")))
        except Exception:
            return
        self.items[i]["value"] = v
        anims = []
        for j, it in enumerate(self.items):  # the scale may change for every bar
            nb = self.bar_for(j, it["value"]).set_fill(self.bars[j].get_fill_color(), self.bars[j].get_fill_opacity())
            nv = txt(self.fmt(it["value"]), 24, FG)
            fit(nv, w=self.geometry()[0] * 0.95)
            nv.next_to(nb, UP, buff=0.12)
            anims += [Transform(self.bars[j], nb), Transform(self.vals[j], nv)]
        self.sc.play(*anims, run_time=0.9)

    def op_swap(self, st):
        ts = st.get("targets") or []
        if len(ts) < 2:
            return
        a, b = self.find(ts[0]), self.find(ts[1])
        if a is None or b is None or a == b:
            return
        dx = self.bars[b].get_center()[0] - self.bars[a].get_center()[0]
        grp_a = VGroup(self.bars[a], self.vals[a], self.cats[a])
        grp_b = VGroup(self.bars[b], self.vals[b], self.cats[b])
        self.sc.play(grp_a.animate.shift(RIGHT * dx), grp_b.animate.shift(LEFT * dx), path_arc=-math.pi / 3, run_time=0.9)
        for lst in (self.bars, self.vals, self.cats, self.items):
            lst[a], lst[b] = lst[b], lst[a]
        self.hl = {({a: b, b: a}.get(i, i)) for i in self.hl}

    def op_label(self, st):
        self.sc.say(st.get("text"))


# ----------------------------------------------------------------------------- reveal lists
class Reveal(Visual):
    """bullets, equation, compare: content shown one piece per step."""

    def __init__(self, sc, spec):
        super().__init__(sc, spec)
        self.kind = spec["kind"]
        self.shown = 0
        self.pieces = []

    def build(self):
        s = self.spec
        zone_h = ZONE_TOP - ZONE_BOT
        center = np.array([0, (ZONE_TOP + ZONE_BOT) / 2, 0])
        if self.kind == "equation":
            lines = [tex(l, size=60) for l in s.get("lines", [])[:4]]
            for l in lines:
                fit(l, w=MAXW - 1, h=0.85)
            g = VGroup(*lines).arrange(DOWN, buff=0.45)
            fit(g, w=MAXW - 1, h=zone_h - 0.2)
            g.move_to(center)
            self.pieces = list(g)
            self.group = g
            return self.reveal_next()
        if self.kind == "compare":
            cols = []
            self.col_points = []
            for side in ("left", "right"):
                c = s.get(side) or {}
                head = txt(c.get("title", ""), 32, FG, weight=BOLD, n=24)
                pts = [txt(p, 26, FG, n=34) for p in (c.get("points") or [])[:4]]
                body = VGroup(head, *pts).arrange(DOWN, buff=0.32, aligned_edge=LEFT)
                head.set_x(body.get_x())
                fit(body, w=5.2)
                card = RoundedRectangle(width=5.8, height=max(body.height + 0.7, 2.0), corner_radius=0.2,
                                        color=LINE, stroke_width=2).set_fill("#1C1C1E", 1)
                body.move_to(card)
                cols.append(VGroup(card, body))
                self.col_points.append(pts)
            g = VGroup(*cols).arrange(RIGHT, buff=0.6, aligned_edge=UP)
            fit(g, w=MAXW, h=zone_h)
            g.move_to(center)
            self.group = g
            # order: alternate left/right points
            order = []
            for i in range(4):
                for pts in self.col_points:
                    if i < len(pts):
                        order.append(pts[i])
            self.pieces = order
            anims = []
            for col in cols:
                card, body = col
                anims += [FadeIn(card), FadeIn(body[0])]
                for p in body[1:]:
                    p.set_opacity(0)
            return anims
        # bullets
        rows = []
        for p in s.get("points", [])[:4]:
            dot = Dot(radius=0.07, color=ACC)
            t = txt(p, 30, FG, n=46)
            rows.append(VGroup(dot, t).arrange(RIGHT, buff=0.3))
        g = VGroup(*rows).arrange(DOWN, buff=0.45, aligned_edge=LEFT)
        fit(g, w=MAXW - 1, h=zone_h - 0.2)
        g.move_to(center)
        self.pieces = list(g)
        self.group = g
        return self.reveal_next()

    def reveal_next(self):
        if self.shown >= len(self.pieces):
            return []
        p = self.pieces[self.shown]
        self.shown += 1
        anims = []
        if self.kind == "equation":
            for q in self.pieces[: self.shown - 1]:
                anims.append(q.animate.set_opacity(0.45))
            return anims + [Write(p)]
        if self.kind == "compare":
            p.set_opacity(1)
            return [FadeIn(p, shift=RIGHT * 0.15)]
        return [FadeIn(p, shift=RIGHT * 0.2)]

    def obstacles(self):
        return [self.group]

    def op_next(self, st):
        anims = self.reveal_next()
        if anims:
            self.sc.play(*anims, run_time=0.9)

    def op_highlight(self, st):
        i = as_int(st.get("target"))
        if i is not None and 0 <= i < self.shown:
            self.sc.play(Indicate(self.pieces[i], color=HOT, scale_factor=1.05), run_time=0.8)
        else:
            self.op_next(st)

    op_label = lambda self, st: self.sc.say(st.get("text"))


KINDS = {"row": Nodes, "stack": Nodes, "cycle": Nodes, "tree": Nodes, "network": Nodes,
         "plot": Plot, "bars": Bars, "equation": Reveal, "compare": Reveal, "bullets": Reveal}


# ----------------------------------------------------------------------------- the scene
class Lesson(Scene):
    def construct(self):
        spec = SPEC  # noqa: F821  (written by main.py)
        self.title = None
        self.note_mob = None
        t = txt(spec.get("title", ""), 40, FG, weight=BOLD, n=44)
        fit(t, w=MAXW - 1, h=0.62)
        t.move_to(UP * TITLE_Y)
        self.title = t

        v = spec.get("visual") or {"kind": "bullets", "points": [spec.get("title", "")]}
        kind = v.get("kind") if v.get("kind") in KINDS else "bullets"
        v["kind"] = kind
        self.vis = KINDS[kind](self, v)
        steps = [s for s in spec.get("steps", []) if isinstance(s, dict)][:10]
        if kind in ("bullets", "equation", "compare") and not any(s.get("op") == "next" for s in steps):
            steps = [{"op": "next"} for _ in range(10)] + steps
        if kind == "plot" and not any(s.get("op") == "draw" for s in steps):
            steps = [{"op": "draw", "f": i} for i in range(len(self.vis.fns))] + steps
        intro = self.vis.build()
        if kind in ("bullets", "equation", "compare"):
            # one "next" per remaining piece is enough
            need = len(self.vis.pieces) - self.vis.shown
            nexts = 0
            kept = []
            for s in steps:
                if s.get("op") == "next":
                    if nexts >= need:
                        continue
                    nexts += 1
                kept.append(s)
            steps = kept

        target = float(spec.get("duration", 12))
        n = max(len(steps), 1)
        busy = 2.0 + n * 1.1
        pause = max(0.35, min(2.2, (target - busy - 1.0) / (n + 1)))

        self.play(Write(t), run_time=0.8)
        self.play(*intro, run_time=1.4)
        self.wait(pause)
        for st in steps:
            if st.get("note"):
                self.say(st["note"], st.get("tex"))
            try:
                self.vis.run(st)
            except Exception as e:  # a bad step never kills the scene
                print("step failed:", st, e)
            self.wait(pause)
        if spec.get("takeaway"):
            self.say(spec["takeaway"])
        left = target - self.renderer.time
        self.wait(max(1.0, left))

    def say(self, text, as_tex=None):
        text = str(text or "").strip()
        if not text:
            return
        use_tex = looks_tex(text) if as_tex is None else bool(as_tex)
        m = tex(text) if use_tex else txt(text, 28, FG, n=70)
        fit(m, w=MAXW - 0.6, h=0.5)
        m.move_to(UP * NOTE_Y)
        # the note line must stay clear of the diagram and above the caption band
        for o in self.vis.everything() if hasattr(self, "vis") else []:
            if hits(m, o, pad=0.1):
                m.next_to(o, DOWN, buff=0.2) if o.get_bottom()[1] > SAFE_BOT + 0.6 else None
        if m.get_bottom()[1] < SAFE_BOT:
            m.shift(UP * (SAFE_BOT - m.get_bottom()[1]))
        if self.note_mob is not None:  # old note fully gone before the new one appears
            self.play(FadeOut(self.note_mob), run_time=0.3)
        self.note_mob = m
        self.play(FadeIn(m, shift=UP * 0.1), run_time=0.5)
