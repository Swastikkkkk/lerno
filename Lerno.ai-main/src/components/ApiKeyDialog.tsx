import { useEffect, useState } from "react";
import { getKey, setKey, KEY_EVENT } from "@/lib/api";

/** Asks the visitor for their own free Gemini key. Opens on demand or when the API says a key is needed. */
export default function ApiKeyDialog() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");

  useEffect(() => {
    const onNeed = (e: Event) => {
      setReason((e as CustomEvent<string>).detail || "");
      setValue(getKey());
      setOpen(true);
    };
    window.addEventListener(KEY_EVENT, onNeed);
    return () => window.removeEventListener(KEY_EVENT, onNeed);
  }, []);

  const hasKey = Boolean(getKey());

  return (
    <>
      <button
        onClick={() => {
          setReason("");
          setValue(getKey());
          setOpen(true);
        }}
        className="fixed bottom-4 right-4 z-[120] rounded-full border border-white/15 bg-neutral-900/90 px-4 py-2 text-xs text-white/70 backdrop-blur hover:text-white"
      >
        {hasKey ? "Gemini key saved" : "Add Gemini key"}
      </button>

      {open && (
        <div className="fixed inset-0 z-[130] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm" onClick={() => setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-neutral-950 p-6 text-white shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold">Use your own Gemini key</h3>
            <p className="mt-2 text-sm text-white/60">
              Lerno runs on Google Gemini. Keys are free: create one in{" "}
              <a className="text-white underline underline-offset-2" href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer">
                Google AI Studio
              </a>{" "}
              and paste it here. It stays in this browser and is only sent with your own requests.
            </p>
            {reason && <p className="mt-3 rounded-lg bg-white/5 px-3 py-2 text-sm text-amber-200/90">{reason}</p>}
            <input
              autoFocus
              type="password"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              placeholder="AIza..."
              className="mt-4 w-full rounded-lg border border-white/15 bg-black px-3 py-2.5 text-sm outline-none focus:border-white/40"
            />
            <div className="mt-4 flex justify-end gap-2">
              {hasKey && (
                <button
                  className="rounded-full px-4 py-2 text-sm text-white/60 hover:text-white"
                  onClick={() => {
                    setKey("");
                    setValue("");
                  }}
                >
                  Remove
                </button>
              )}
              <button
                className="rounded-full bg-white px-5 py-2 text-sm font-medium text-black disabled:opacity-40"
                disabled={!value.trim()}
                onClick={() => {
                  setKey(value.trim());
                  setOpen(false);
                }}
              >
                Save key
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
