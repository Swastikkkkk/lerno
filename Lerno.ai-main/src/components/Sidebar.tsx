import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { LogoMark, Wordmark } from "./Brand";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { LogIn, LogOut, PanelLeftClose, PanelLeftOpen, Plus, Search, Trash2 } from "lucide-react";
import { useAuth, displayName } from "@/lib/auth";
import { supabase } from "@/lib/supabase";
import { deleteLesson, listLessons, LESSONS_EVENT, type LessonSummary } from "@/lib/lessons";

function groupByDate(items: LessonSummary[]) {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86400000;
  const groups: [string, LessonSummary[]][] = [["Today", []], ["Yesterday", []], ["Previous 7 days", []], ["Previous 30 days", []], ["Older", []]];
  for (const l of items) {
    const t = new Date(l.created_at).getTime();
    const i = t >= start ? 0 : t >= start - day ? 1 : t >= start - 7 * day ? 2 : t >= start - 30 * day ? 3 : 4;
    groups[i][1].push(l);
  }
  return groups.filter(([, g]) => g.length);
}

const COLLAPSE_KEY = "lerno_sidebar_collapsed";

/** Left rail like ChatGPT: new lesson, your saved lessons by date, account at the bottom. */
export function Sidebar({ open, setOpen }: { open: boolean; setOpen: (o: boolean) => void }) {
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const active = params.get("id");
  const [items, setItems] = useState<LessonSummary[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!user) return setItems([]);
    setBusy(true);
    try { setItems(await listLessons()); } catch { /* offline: keep what we had */ } finally { setBusy(false); }
  }, [user]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    window.addEventListener(LESSONS_EVENT, load);
    return () => window.removeEventListener(LESSONS_EVENT, load);
  }, [load]);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? items.filter((l) => (l.title + " " + l.prompt).toLowerCase().includes(q)) : items;
  }, [items, query]);

  const remove = async (id: string) => {
    if (!user || !confirm("Delete this lesson and its notes?")) return;
    await deleteLesson(id, user.id);
    if (id === active) navigate("/chat");
  };

  return (
    <aside
      className={`fixed inset-y-0 left-0 z-[90] flex w-[264px] flex-col border-r border-white/[0.06] bg-neutral-950 transition-transform duration-200 md:relative md:z-[75] ${open ? "translate-x-0" : "-translate-x-full md:hidden"}`}
    >
      <div className="flex items-center justify-between px-3 pb-2 pt-3">
        <Link to="/" className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-white hover:bg-white/[0.06]">
          <LogoMark size={22} />
          <Wordmark className="text-[15px]" />
        </Link>
        <button onClick={() => setOpen(false)} className="rounded-lg p-2 text-neutral-400 hover:bg-white/[0.06] hover:text-white" aria-label="Close sidebar">
          <PanelLeftClose className="h-5 w-5" />
        </button>
      </div>

      <div className="px-3">
        <button
          onClick={() => { navigate("/chat"); if (window.innerWidth < 768) setOpen(false); }}
          className="flex w-full items-center gap-2 rounded-xl border border-white/10 px-3 py-2.5 text-sm text-white hover:bg-white/[0.06]"
        >
          <Plus className="h-4 w-4" /> New lesson
        </button>
        {user && items.length > 0 && (
          <div className="relative mt-2">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-neutral-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search lessons"
              className="w-full rounded-xl bg-white/[0.04] py-2 pl-9 pr-3 text-sm text-white placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-white/20"
            />
          </div>
        )}
      </div>

      <nav className="mt-3 flex-1 overflow-y-auto px-2 pb-3">
        {!loading && !user && (
          <div className="mx-1 rounded-xl border border-white/[0.06] p-4 text-sm text-neutral-400">
            Sign in to keep every lesson and your notes here.
            <Link to="/login" className="mt-3 flex items-center justify-center gap-2 rounded-lg bg-white py-2 font-medium text-black hover:bg-neutral-200">
              <LogIn className="h-4 w-4" /> Sign in
            </Link>
          </div>
        )}
        {user && !busy && items.length === 0 && <p className="px-3 py-2 text-sm text-neutral-500">Your lessons will show up here.</p>}
        {groupByDate(shown).map(([label, group]) => (
          <div key={label} className="mb-3">
            <p className="px-3 pb-1 pt-2 text-xs font-medium text-neutral-500">{label}</p>
            {group.map((l) => (
              <div key={l.id} className={`group relative flex items-center rounded-lg ${l.id === active ? "bg-white/[0.08]" : "hover:bg-white/[0.04]"}`}>
                <Link
                  to={`/learning?id=${l.id}`}
                  onClick={() => window.innerWidth < 768 && setOpen(false)}
                  className="min-w-0 flex-1 truncate px-3 py-2 text-sm text-neutral-200"
                  title={l.prompt}
                >
                  {l.title || l.prompt}
                </Link>
                <button
                  onClick={() => remove(l.id)}
                  className="mr-1 hidden rounded-md p-1.5 text-neutral-500 hover:bg-white/10 hover:text-white group-hover:block"
                  aria-label="Delete lesson"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        ))}
      </nav>

      {user && (
        <div className="flex items-center gap-3 border-t border-white/[0.06] p-3">
          {user.user_metadata?.avatar_url ? (
            <img src={user.user_metadata.avatar_url as string} alt="" className="h-8 w-8 rounded-full" referrerPolicy="no-referrer" />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-sm font-medium text-white">
              {displayName(user).slice(0, 1).toUpperCase()}
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-white">{displayName(user)}</p>
            <p className="truncate text-xs text-neutral-500">{user.email}</p>
          </div>
          <button onClick={() => supabase.auth.signOut()} className="rounded-lg p-2 text-neutral-400 hover:bg-white/[0.06] hover:text-white" aria-label="Sign out" title="Sign out">
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      )}
    </aside>
  );
}

/** Builder and lesson pages live inside this: sidebar on the left, page on the right. */
export function AppShell({ children }: { children: ReactNode }) {
  const [open, setOpenState] = useState(() => {
    if (typeof window !== "undefined" && window.innerWidth < 768) return false;
    try { return localStorage.getItem(COLLAPSE_KEY) !== "1"; } catch { return true; }
  });
  const setOpen = (o: boolean) => {
    setOpenState(o);
    try { localStorage.setItem(COLLAPSE_KEY, o ? "0" : "1"); } catch { /* private mode */ }
  };
  return (
    <div className="flex h-screen w-full overflow-hidden bg-black">
      <Sidebar open={open} setOpen={setOpen} />
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[80] bg-black/60 md:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setOpen(false)}
          />
        )}
      </AnimatePresence>
      <main className="relative min-w-0 flex-1 overflow-y-auto">
        {!open && (
          <button
            onClick={() => setOpen(true)}
            className="absolute left-3 top-3 z-[70] rounded-lg border border-white/10 bg-neutral-900/80 p-2 text-neutral-300 backdrop-blur hover:text-white"
            aria-label="Open sidebar"
          >
            <PanelLeftOpen className="h-5 w-5" />
          </button>
        )}
        {children}
      </main>
    </div>
  );
}
