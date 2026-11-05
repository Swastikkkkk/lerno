import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Captions, CaptionsOff, Maximize, Minimize, Pause, Play, RotateCcw, Settings, Volume2, VolumeX } from "lucide-react";

type Props = {
  src: string | null;               // Manim scene video
  audio: HTMLAudioElement | null;   // Murf narration (null while loading or when the browser voice is used)
  captions: string;                 // narration text in the chosen language
  emptyText?: string;
};

const SPEEDS = [0.75, 1, 1.25, 1.5, 2];
const fmt = (s: number) => {
  if (!isFinite(s) || s < 0) s = 0;
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
};

/** Split narration into caption lines of a readable length. */
function toLines(text: string): string[] {
  const parts = text.replace(/\s+/g, " ").trim().split(/(?<=[.!?।。？！])\s+/).filter(Boolean);
  const out: string[] = [];
  for (const p of parts) {
    if (p.length <= 90) { out.push(p); continue; }
    const words = p.split(" ");
    let cur = "";
    for (const w of words) {
      if ((cur + " " + w).trim().length > 80) { out.push(cur.trim()); cur = ""; }
      cur += " " + w;
    }
    if (cur.trim()) out.push(cur.trim());
  }
  return out.length ? out : [text];
}

/** YouTube-style player: the scene video and the narration share one set of controls. */
export default function LessonPlayer({ src, audio, captions, emptyText }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [dur, setDur] = useState(0);
  const [muted, setMuted] = useState(false);
  const [volume, setVolume] = useState(1);
  const [cc, setCc] = useState(true);
  const [speed, setSpeed] = useState(1);
  const [speedOpen, setSpeedOpen] = useState(false);
  const [full, setFull] = useState(false);
  const [idle, setIdle] = useState(false);
  const idleTimer = useRef<number>();

  const lines = useMemo(() => toLines(captions || ""), [captions]);
  // caption timing: spread lines over the narration by character count
  const bounds = useMemo(() => {
    const total = lines.reduce((n, l) => n + l.length, 0) || 1;
    let acc = 0;
    return lines.map((l) => (acc += l.length) / total);
  }, [lines]);

  // the timeline follows the narration when there is one, otherwise the video
  const clock = (): HTMLMediaElement | null => audio ?? video.current;

  // keep state in sync with whatever is actually playing
  useEffect(() => {
    const el = clock();
    if (!el) return;
    const tick = () => { setT(el.currentTime); setDur(el.duration || 0); };
    const onPlay = () => setPlaying(true);
    const onPause = () => setPlaying(false);
    const onEnd = () => { setPlaying(false); video.current?.pause(); };
    tick();
    setPlaying(!el.paused);
    el.addEventListener("timeupdate", tick);
    el.addEventListener("loadedmetadata", tick);
    el.addEventListener("durationchange", tick);
    el.addEventListener("play", onPlay);
    el.addEventListener("pause", onPause);
    el.addEventListener("ended", onEnd);
    return () => {
      el.removeEventListener("timeupdate", tick);
      el.removeEventListener("loadedmetadata", tick);
      el.removeEventListener("durationchange", tick);
      el.removeEventListener("play", onPlay);
      el.removeEventListener("pause", onPause);
      el.removeEventListener("ended", onEnd);
    };
  }, [audio, src]); // eslint-disable-line react-hooks/exhaustive-deps

  // apply volume / speed to both elements
  useEffect(() => {
    if (audio) { audio.volume = volume; audio.muted = muted; audio.playbackRate = speed; }
    if (video.current) video.current.playbackRate = speed;
  }, [audio, volume, muted, speed]);

  // video follows narration play state
  useEffect(() => {
    const v = video.current;
    if (!v) return;
    if (playing) v.play().catch(() => {});
    else v.pause();
  }, [playing, src]);

  const toggle = useCallback(() => {
    const el = clock();
    if (audio) {
      if (audio.paused) {
        if (audio.ended || (audio.duration && audio.currentTime >= audio.duration - 0.05)) audio.currentTime = 0;
        audio.play().catch(() => {});
      } else audio.pause();
    } else if (el) {
      el.paused ? el.play().catch(() => {}) : el.pause();
    } else if ("speechSynthesis" in window) {
      // browser-voice fallback
      if (speechSynthesis.paused) { speechSynthesis.resume(); setPlaying(true); }
      else if (speechSynthesis.speaking) { speechSynthesis.pause(); setPlaying(false); }
    }
  }, [audio]); // eslint-disable-line react-hooks/exhaustive-deps

  const seek = (frac: number) => {
    const el = clock();
    if (!el || !el.duration) return;
    el.currentTime = Math.max(0, Math.min(el.duration, frac * el.duration));
    const v = video.current;
    if (audio && v && v.duration) v.currentTime = el.currentTime % v.duration;
    setT(el.currentTime);
  };

  const restart = () => { seek(0); const el = clock(); el?.play().catch(() => {}); };

  const toggleFull = () => {
    if (!document.fullscreenElement) wrap.current?.requestFullscreen?.();
    else document.exitFullscreen?.();
  };
  useEffect(() => {
    const on = () => setFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", on);
    return () => document.removeEventListener("fullscreenchange", on);
  }, []);

  const poke = () => {
    setIdle(false);
    window.clearTimeout(idleTimer.current);
    idleTimer.current = window.setTimeout(() => setIdle(true), 2500);
  };

  const onKey = (e: React.KeyboardEvent) => {
    const k = e.key.toLowerCase();
    if (k === " " || k === "k") { e.preventDefault(); toggle(); }
    else if (k === "m") setMuted((m) => !m);
    else if (k === "c") setCc((c) => !c);
    else if (k === "f") toggleFull();
    else if (k === "arrowright") seek((t + 5) / (dur || 1));
    else if (k === "arrowleft") seek((t - 5) / (dur || 1));
    poke();
  };

  const frac = dur ? t / dur : 0;
  const lineIdx = Math.min(lines.length - 1, bounds.findIndex((b) => frac <= b + 1e-6));
  const caption = audio ? lines[Math.max(0, lineIdx)] : lines[0];
  const showControls = !playing || !idle || speedOpen;

  return (
    <div
      ref={wrap}
      tabIndex={0}
      onKeyDown={onKey}
      onMouseMove={poke}
      onMouseLeave={() => setIdle(true)}
      className={`relative h-full w-full overflow-hidden rounded-lg bg-black outline-none select-none ${playing && idle && !speedOpen ? "cursor-none" : ""}`}
    >
      {src ? (
        <video
          ref={video}
          key={src}
          src={src}
          muted
          loop={!!audio}
          playsInline
          autoPlay
          onClick={toggle}
          className="h-full w-full object-contain"
        />
      ) : (
        <div onClick={toggle} className="flex h-full w-full items-center justify-center px-8 text-center text-white/60">
          {emptyText}
        </div>
      )}

      {/* captions */}
      {cc && caption && (
        <div className={`pointer-events-none absolute inset-x-0 flex justify-center px-6 transition-all duration-200 ${showControls ? "bottom-16" : "bottom-6"}`}>
          <span className="max-w-[90%] rounded-md bg-black/75 px-3 py-1.5 text-center text-[15px] leading-snug text-white md:text-base">
            {caption}
          </span>
        </div>
      )}

      {/* big play button when paused */}
      <AnimatePresence>
        {!playing && (
          <motion.button
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            onClick={toggle}
            className="absolute left-1/2 top-1/2 flex h-16 w-16 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm hover:bg-black/75"
            aria-label="Play"
          >
            <Play className="ml-1 h-7 w-7" fill="currentColor" />
          </motion.button>
        )}
      </AnimatePresence>

      {/* control bar */}
      <div className={`absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/40 to-transparent px-3 pb-2 pt-8 transition-opacity duration-200 ${showControls ? "opacity-100" : "opacity-0"}`}>
        <div
          className="group/seek relative mb-2 h-1 cursor-pointer rounded-full bg-white/25 hover:h-1.5 transition-all"
          onClick={(e) => { const r = e.currentTarget.getBoundingClientRect(); seek((e.clientX - r.left) / r.width); }}
        >
          <div className="absolute inset-y-0 left-0 rounded-full bg-white" style={{ width: `${frac * 100}%` }} />
          <div className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white opacity-0 group-hover/seek:opacity-100" style={{ left: `${frac * 100}%` }} />
        </div>

        <div className="flex items-center gap-1 text-white">
          <button onClick={toggle} className="rounded-md p-2 hover:bg-white/10" aria-label={playing ? "Pause" : "Play"}>
            {playing ? <Pause className="h-5 w-5" fill="currentColor" /> : <Play className="h-5 w-5" fill="currentColor" />}
          </button>
          <button onClick={restart} className="rounded-md p-2 hover:bg-white/10" aria-label="Restart">
            <RotateCcw className="h-[18px] w-[18px]" />
          </button>
          <div className="group/vol flex items-center">
            <button onClick={() => setMuted((m) => !m)} className="rounded-md p-2 hover:bg-white/10" aria-label={muted ? "Unmute" : "Mute"}>
              {muted || volume === 0 ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
            </button>
            <input
              type="range" min={0} max={1} step={0.05}
              value={muted ? 0 : volume}
              onChange={(e) => { setVolume(+e.target.value); setMuted(+e.target.value === 0); }}
              className="w-0 accent-white opacity-0 transition-all duration-200 group-hover/vol:w-20 group-hover/vol:opacity-100"
              aria-label="Volume"
            />
          </div>
          <span className="ml-2 text-xs tabular-nums text-white/80">{fmt(t)} / {fmt(dur)}</span>

          <div className="ml-auto flex items-center gap-1">
            <button onClick={() => setCc((c) => !c)} className={`rounded-md p-2 hover:bg-white/10 ${cc ? "text-white" : "text-white/60"}`} aria-label="Captions">
              {cc ? <Captions className="h-5 w-5" /> : <CaptionsOff className="h-5 w-5" />}
            </button>
            <div className="relative">
              <button onClick={() => setSpeedOpen((o) => !o)} className="flex items-center gap-1 rounded-md p-2 text-xs hover:bg-white/10" aria-label="Speed">
                <Settings className="h-[18px] w-[18px]" />
                {speed !== 1 && <span className="tabular-nums">{speed}x</span>}
              </button>
              {speedOpen && (
                <div className="absolute bottom-11 right-0 w-28 rounded-lg border border-white/10 bg-neutral-900/95 p-1 backdrop-blur">
                  <p className="px-2 py-1 text-[11px] uppercase tracking-wide text-white/40">Speed</p>
                  {SPEEDS.map((s) => (
                    <button
                      key={s}
                      onClick={() => { setSpeed(s); setSpeedOpen(false); }}
                      className={`block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-white/10 ${s === speed ? "text-white" : "text-white/70"}`}
                    >
                      {s === 1 ? "Normal" : `${s}x`}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button onClick={toggleFull} className="rounded-md p-2 hover:bg-white/10" aria-label="Fullscreen">
              {full ? <Minimize className="h-5 w-5" /> : <Maximize className="h-5 w-5" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
