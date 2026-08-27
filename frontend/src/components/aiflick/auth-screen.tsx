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
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[420px] ambient-glow" />

      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-sm rounded-2xl border border-border/80 bg-surface p-6 shadow-float"
      >
        {!forced && (
          <button
            type="button"
            onClick={onCancel}
            aria-label="Close"
            className="absolute top-4 right-4 grid size-7 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <X className="size-4" />
          </button>
        )}

        <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground">
          <Flame className="size-4.5" />
        </span>
        <h1 className="mt-4 text-xl tracking-tight text-foreground font-bold">
          {mode === "login" ? "Welcome back" : "Create your workspace"}
        </h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          {forced
            ? "You have used your free messages -- sign in to keep going."
            : "Your chats, brand presets and generated visual studio posts stay saved."}
        </p>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-4 flex items-start gap-2 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-xs text-destructive"
            >
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        <form className="mt-6 space-y-3.5" onSubmit={handleSubmit}>
          {mode === "signup" && (
            <div className="space-y-1.5">
              <Label htmlFor="name" className="label-mono">
                Your Name
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
                className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="email" className="label-mono">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              required
              disabled={loading}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@company.com"
              className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="password" className="label-mono">
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
              className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
            />
          </div>

          <Button
            type="submit"
            disabled={loading}
            className="h-10 w-full rounded-xl bg-primary text-primary-foreground shadow-ember hover:bg-primary-hover font-semibold"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <Loader2 className="size-4 animate-spin" />
                {mode === "login" ? "Logging in..." : "Creating account..."}
              </span>
            ) : mode === "login" ? (
              "Log in"
            ) : (
              "Create account"
            )}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
          <button
            type="button"
            disabled={loading}
            onClick={() => handleSwitchMode(mode === "login" ? "signup" : "login")}
            className="font-medium text-primary hover:text-primary-hover disabled:opacity-50"
          >
            {mode === "login" ? "Sign up" : "Log in"}
          </button>
        </p>

        {!forced && (
          <button
            type="button"
            disabled={loading}
            onClick={onCancel}
            className="mt-3 w-full text-center text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            Continue as guest
          </button>
        )}
      </motion.div>
    </div>
  );
}
