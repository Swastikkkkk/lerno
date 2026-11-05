import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { PencilLine, Menu, X } from "lucide-react";

const links = [
  { label: "Home", target: "top" },
  { label: "About", target: "about" },
  { label: "Features", target: "features" },
];

/** Floating top bar: logo left, section links centered, Login / Sign up pills on the right. */
export default function NavBar() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  const go = (target: string) => {
    setOpen(false);
    if (target === "top") window.scrollTo({ top: 0, behavior: "smooth" });
    else document.getElementById(target)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="fixed inset-x-0 top-0 z-[100] px-4 pt-4">
      <nav className="mx-auto max-w-6xl rounded-2xl border border-white/[0.06] bg-neutral-950/70 backdrop-blur-md">
        <div className="flex h-16 items-center justify-between px-5 md:px-8">
          <button onClick={() => go("top")} className="flex items-center gap-2.5 text-white">
            <PencilLine className="h-6 w-6" strokeWidth={1.5} />
            <span className="text-[17px] font-semibold tracking-tight">Lerno AI</span>
          </button>

          <div className="hidden md:flex items-center gap-1" onMouseLeave={() => setHovered(null)}>
            {links.map((l) => (
              <button
                key={l.label}
                onClick={() => go(l.target)}
                onMouseEnter={() => setHovered(l.label)}
                className="relative px-4 py-2 text-[15px] font-medium text-neutral-200 hover:text-white transition-colors"
              >
                {hovered === l.label && (
                  <motion.span
                    layoutId="nav-hover"
                    className="absolute inset-0 rounded-full bg-white/[0.07]"
                    transition={{ type: "spring", stiffness: 400, damping: 32 }}
                  />
                )}
                <span className="relative">{l.label}</span>
              </button>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <button
              onClick={() => navigate("/chat")}
              className="rounded-xl border border-white/10 bg-black px-5 py-2 text-[15px] font-medium text-white hover:border-white/30 transition-colors"
            >
              Login
            </button>
            <button
              onClick={() => navigate("/chat")}
              className="rounded-xl bg-white px-5 py-2 text-[15px] font-medium text-black hover:bg-neutral-200 transition-colors"
            >
              Sign up
            </button>
          </div>

          <button onClick={() => setOpen((o) => !o)} className="md:hidden text-neutral-300 hover:text-white" aria-label="Menu">
            {open ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>

        {open && (
          <div className="md:hidden border-t border-white/[0.06] px-5 py-4 flex flex-col gap-1">
            {links.map((l) => (
              <button key={l.label} onClick={() => go(l.target)} className="py-2 text-left text-neutral-200 hover:text-white">
                {l.label}
              </button>
            ))}
            <div className="mt-3 flex gap-3">
              <button onClick={() => navigate("/chat")} className="flex-1 rounded-xl border border-white/10 bg-black py-2 text-white">
                Login
              </button>
              <button onClick={() => navigate("/chat")} className="flex-1 rounded-xl bg-white py-2 font-medium text-black">
                Sign up
              </button>
            </div>
          </div>
        )}
      </nav>
    </div>
  );
}
