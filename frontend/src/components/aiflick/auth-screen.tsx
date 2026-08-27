import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { AlertCircle, Flame, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login, signup } from "@/api";

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
  const [error, setError] = useState<string | null>(null);

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

        <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
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
