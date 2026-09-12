import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { AlertCircle, Flame, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login, signup, getGoogleLoginUrl } from "@/api";

type Props = {
  forced: boolean;
  onAuthenticated: () => void;
  onCancel: () => void;
};

export function AuthScreen({ forced, onAuthenticated, onCancel }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGoogleSignIn() {
    if (googleLoading || loading) return;
    setError(null);
    setGoogleLoading(true);
    try {
      const url = await getGoogleLoginUrl();
      window.location.href = url;
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to initialize Google Sign-In");
      setGoogleLoading(false);
    }
  }


  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (loading) return;

    setError(null);
    setLoading(true);

    try {
      if (mode === "login") {
        await login({ email: email.trim(), password });
      } else {
        await signup({ name: name.trim(), email: email.trim(), password });
      }
      onAuthenticated();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Authentication failed. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  function handleSwitchMode(newMode: "login" | "signup") {
    setMode(newMode);
    setError(null);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/75 p-4 sm:p-6 backdrop-blur-xl">
      {/* Fluid ambient background glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div
          className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[450px] rounded-full blur-[140px] opacity-35"
          style={{
            background: "radial-gradient(circle, rgba(249, 115, 22, 0.4), rgba(56, 189, 248, 0.25), transparent 70%)",
          }}
        />
      </div>

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 16 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 16 }}
        transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-xl rounded-3xl border border-white/15 bg-[#0D111A]/95 p-8 sm:p-10 shadow-2xl backdrop-blur-2xl"
      >
        {!forced && (
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close modal"
            className="absolute top-6 right-6 grid size-9 place-items-center rounded-xl border border-white/10 bg-white/5 text-muted-foreground transition-colors hover:bg-white/10 hover:text-white"
          >
            <X className="size-4" />
          </button>
        )}

        <div className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary to-amber-400 shadow-ember ring-1 ring-primary/40">
            <span className="text-base font-black text-black">△</span>
          </div>
          <div>
            <span className="text-xs font-mono font-bold uppercase tracking-widest text-primary">
              AIFlick Workspace
            </span>
            <h1 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
              {mode === "login" ? "Welcome back" : "Create creator workspace"}
            </h1>
          </div>
        </div>

        <p className="mt-3 text-sm leading-relaxed text-slate-400">
          {forced
            ? "You have used your free messages — sign in to continue generating viral posts and studio visuals."
            : "Save your session history, brand memory presets, and high-converting visual graphics."}
        </p>

        {/* Mode Switcher Tabs */}
        <div className="mt-6 grid grid-cols-2 gap-1.5 rounded-2xl border border-white/10 bg-white/5 p-1.5">
          <button
            type="button"
            onClick={() => handleSwitchMode("login")}
            className={`rounded-xl py-2 text-xs font-bold transition-all ${
              mode === "login"
                ? "bg-white text-black shadow-md"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Log In
          </button>
          <button
            type="button"
            onClick={() => handleSwitchMode("signup")}
            className={`rounded-xl py-2 text-xs font-bold transition-all ${
              mode === "signup"
                ? "bg-white text-black shadow-md"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Create Free Account
          </button>
        </div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-4 flex items-start gap-2.5 rounded-2xl border border-destructive/40 bg-destructive/10 p-3.5 text-xs text-destructive"
            >
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Google OAuth 2.0 Instant Login */}
        <div className="mt-5 space-y-3">
          <button
            type="button"
            disabled={loading || googleLoading}
            onClick={handleGoogleSignIn}
            className="flex h-12 w-full items-center justify-center gap-3 rounded-xl border border-white/20 bg-white/5 px-4 text-sm font-semibold text-white transition-all hover:bg-white/10 active:scale-[0.98] disabled:opacity-50"
          >
            {googleLoading ? (
              <Loader2 className="size-4 animate-spin text-white" />
            ) : (
              <svg className="size-5 shrink-0" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                />
              </svg>
            )}
            <span>
              {googleLoading
                ? "Connecting to Google..."
                : mode === "login"
                ? "Sign in with Google"
                : "Sign up with Google"}
            </span>
          </button>

          <div className="relative my-2 w-full">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/10" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#0D111A] px-3 font-mono text-[11px] text-slate-400">
                or continue with email
              </span>
            </div>
          </div>
        </div>

        <form className="mt-4 space-y-4" onSubmit={handleSubmit}>

          {mode === "signup" && (
            <div className="space-y-1.5">
              <Label htmlFor="name" className="label-mono text-xs text-slate-300">
                Your Name / Brand
              </Label>
              <Input
                id="name"
                type="text"
                required
                disabled={loading}
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                placeholder="e.g. Alex Rivera"
                className="h-12 rounded-xl border-white/15 bg-white/5 text-sm text-white placeholder:text-slate-500 focus:border-primary"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="email" className="label-mono text-xs text-slate-300">
              Email Address
            </Label>
            <Input
              id="email"
              type="email"
              required
              disabled={loading}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@creator.com"
              className="h-12 rounded-xl border-white/15 bg-white/5 text-sm text-white placeholder:text-slate-500 focus:border-primary"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password" className="label-mono text-xs text-slate-300">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              required
              disabled={loading}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="••••••••"
              className="h-12 rounded-xl border-white/15 bg-white/5 text-sm text-white placeholder:text-slate-500 focus:border-primary"
            />
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="h-12 w-full rounded-xl bg-primary text-black font-bold shadow-ember hover:bg-primary-hover transition-all text-sm mt-2"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                {mode === "login" ? "Signing in..." : "Creating workspace..."}
              </span>
            ) : mode === "login" ? (
              "Sign In to AIFlick"
            ) : (
              "Get Started Free"
            )}
          </Button>
        </form>

        <div className="mt-6 flex items-center justify-between border-t border-white/10 pt-4 text-xs text-slate-400">
          <span>{mode === "login" ? "New to AIFlick?" : "Have an account?"}</span>
          <button
            type="button"
            disabled={loading}
            onClick={() => handleSwitchMode(mode === "login" ? "signup" : "login")}
            className="font-bold text-primary hover:underline disabled:opacity-50"
          >
            {mode === "login" ? "Create Free Account" : "Sign in here"}
          </button>
        </div>

        {!forced && (
          <button
            type="button"
            disabled={loading}
            onClick={onCancel}
            className="mt-3 w-full text-center text-xs text-slate-500 hover:text-slate-300 transition-colors"
          >
            Continue as guest
          </button>
        )}
      </motion.div>
    </div>
  );
}
