import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { Session, User } from "@supabase/supabase-js";
import { supabase } from "./supabase";

type AuthState = { user: User | null; session: Session | null; loading: boolean };
const Ctx = createContext<AuthState>({ user: null, session: null, loading: true });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, session: null, loading: true });
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) =>
      setState({ session: data.session, user: data.session?.user ?? null, loading: false }));
    const { data: sub } = supabase.auth.onAuthStateChange((_e, session) =>
      setState({ session, user: session?.user ?? null, loading: false }));
    return () => sub.subscription.unsubscribe();
  }, []);
  return <Ctx.Provider value={state}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);

export const displayName = (u: User | null) =>
  (u?.user_metadata?.full_name as string) || (u?.user_metadata?.name as string) || u?.email?.split("@")[0] || "You";
