import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, Lock, Mail, User } from "lucide-react";
import { SparklesCore } from "@/ui/sparkles";
import { supabase } from "@/lib/supabase";
import { useAuth } from "@/lib/auth";

const GoogleIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 24 24" aria-hidden>
    <path fill="#fff" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
    <path fill="#fff" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
    <path fill="#fff" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
    <path fill="#fff" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
  </svg>
);

const input =
  "w-full rounded-2xl border border-[#333] bg-[#191919]/80 py-3.5 pl-12 pr-4 text-white placeholder-gray-500 transition focus:border-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-600";

/** Email/password and Google sign-in through Supabase, in the original Lerno card design. */
export default function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const signup = mode === "signup";

  useEffect(() => {
    if (user) navigate("/chat", { replace: true });
  }, [user, navigate]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setInfo("");
    if (password.length < 6) return setError("Password needs at least 6 characters.");
    setBusy(true);
    try {
      if (signup) {
        const { data, error } = await supabase.auth.signUp({
          email,
          password,
          options: { data: { full_name: name.trim() }, emailRedirectTo: `${window.location.origin}/chat` },
        });
        if (error) throw error;
        if (!data.session) setInfo("Check your inbox to confirm your email, then sign in.");
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(/invalid login/i.test(msg) ? "Wrong email or password." : msg);
    } finally {
      setBusy(false);
    }
  };

  const google = async () => {
    setError("");
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/chat` },
    });
    if (error) setError(/not enabled|provider/i.test(error.message) ? "Google sign-in isn't switched on yet. Use email for now." : error.message);
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-black p-4">
      <div className="absolute inset-0">
        <SparklesCore id="auth-sparkles" background="transparent" minSize={0.4} maxSize={1.2} particleDensity={80} className="h-full w-full" particleColor="#FFFFFF" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        <div className="absolute inset-0 rounded-3xl border border-[#232323] bg-black/90 shadow-2xl backdrop-blur-sm" />
        <div className="relative p-8">
          <Link to="/" className="mx-auto mb-6 flex w-fit items-center gap-2 text-white">
            <img src="/logo.png" alt="" width={28} height={28} />
            <span className="font-semibold">Lerno AI</span>
          </Link>
          <div className="mb-8 text-center">
            <h1 className="mb-2 text-3xl font-bold text-white">{signup ? "Create your account" : "Welcome back"}</h1>
            <p className="text-gray-400">{signup ? "Your lessons and notes, saved everywhere." : "Pick up where you left off."}</p>
          </div>

          <form onSubmit={submit} className="space-y-5">
            {signup && (
              <div className="relative">
                <User className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-500" />
                <input value={name} onChange={(e) => setName(e.target.value)} className={input} placeholder="Your name" autoComplete="name" />
              </div>
            )}
            <div className="relative">
              <Mail className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-500" />
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={input} placeholder="Email address" autoComplete="email" />
            </div>
            <div className="relative">
              <Lock className="pointer-events-none absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-gray-500" />
              <input
                type={show ? "text" : "password"}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`${input} pr-12`}
                placeholder="Password"
                autoComplete={signup ? "new-password" : "current-password"}
              />
              <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white" aria-label="Show password">
                {show ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>

            {error && <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3 text-sm text-neutral-200">{error}</div>}
            {info && <div className="rounded-xl border border-white/10 bg-white/[0.04] p-3 text-sm text-neutral-200">{info}</div>}

            <button type="submit" disabled={busy} className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white py-3 font-semibold text-black transition hover:bg-neutral-200 disabled:opacity-50">
              {busy ? <span className="h-5 w-5 animate-spin rounded-full border-2 border-black/30 border-t-black" /> : <>{signup ? "Create account" : "Sign in"}<ArrowRight className="h-5 w-5" /></>}
            </button>
          </form>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center"><div className="w-full border-t border-[#232323]" /></div>
            <div className="relative flex justify-center text-sm"><span className="bg-black px-4 text-gray-500">or continue with</span></div>
          </div>

          <button onClick={google} className="flex w-full items-center justify-center gap-3 rounded-2xl bg-[#191919]/80 px-6 py-3.5 text-white transition hover:bg-[#232323]/80">
            <GoogleIcon />
            <span>Continue with Google</span>
          </button>

          <p className="mt-8 text-center text-gray-400">
            {signup ? "Already have an account? " : "Don't have an account? "}
            <Link to={signup ? "/login" : "/signup"} className="text-gray-200 underline hover:text-white">
              {signup ? "Sign in" : "Sign up"}
            </Link>
          </p>
          <p className="mt-3 text-center">
            <Link to="/chat" className="text-sm text-gray-500 hover:text-gray-300">Continue without an account</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
