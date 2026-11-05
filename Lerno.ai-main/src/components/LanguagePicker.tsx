import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Languages, X } from "lucide-react";
import { LANGS, LANG_EVENT, getLang, setLang } from "@/lib/api";

/** Pill that shows the current language and opens a dialog to pick another one. */
export default function LanguagePicker({ className = "" }: { className?: string }) {
  const [open, setOpen] = useState(false);
  const [lang, setLangState] = useState(getLang());

  useEffect(() => {
    const on = (e: Event) => setLangState((e as CustomEvent<string>).detail);
    window.addEventListener(LANG_EVENT, on);
    return () => window.removeEventListener(LANG_EVENT, on);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const current = LANGS.find((l) => l.code === lang) ?? LANGS[0];

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`flex items-center gap-2 rounded-full border border-white/10 bg-neutral-900 px-4 py-2 text-sm text-neutral-200 hover:border-white/25 hover:text-white transition-colors ${className}`}
      >
        <Languages className="h-4 w-4" strokeWidth={1.75} />
        {current.native}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              className="w-full max-w-xl rounded-2xl border border-white/10 bg-neutral-950 p-6 text-white shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold">Choose your language</h3>
                  <p className="mt-1 text-sm text-neutral-400">Narration, quiz and tutor switch to this language.</p>
                </div>
                <button onClick={() => setOpen(false)} className="text-neutral-400 hover:text-white" aria-label="Close">
                  <X className="h-5 w-5" />
                </button>
              </div>
              <div className="mt-5 grid max-h-[60vh] grid-cols-2 gap-2 overflow-y-auto sm:grid-cols-3">
                {LANGS.map((l) => {
                  const active = l.code === lang;
                  return (
                    <button
                      key={l.code}
                      onClick={() => {
                        setLang(l.code);
                        setOpen(false);
                      }}
                      className={`flex items-center justify-between rounded-xl border px-4 py-3 text-left transition-colors ${
                        active ? "border-white/40 bg-white/10" : "border-white/[0.08] bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.05]"
                      }`}
                    >
                      <span>
                        <span className="block text-[15px] font-medium">{l.native}</span>
                        <span className="block text-xs text-neutral-500">{l.name}</span>
                      </span>
                      {active && <Check className="h-4 w-4 text-white" />}
                    </button>
                  );
                })}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
