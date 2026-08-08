import { useState } from "react";
import { motion } from "motion/react";
import { Flame, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = {
  forced: boolean;
  onAuthenticated: () => void;
  onCancel: () => void;
};

export function AuthScreen({ forced, onAuthenticated, onCancel }: Props) {
  const [mode, setMode] = useState<"login" | "signup">("login");

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
        <h1 className="mt-4 text-xl tracking-tight text-foreground">
          {mode === "login" ? "Welcome back" : "Create your workspace"}
        </h1>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
          {forced
            ? "You've used your free messages — sign in to keep going."
            : "Your chats and generated posts stay saved to your account."}
        </p>

        <form
          className="mt-6 space-y-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            onAuthenticated();
          }}
        >
          <div className="space-y-1.5">
            <Label htmlFor="email" className="label-mono">
              Email
            </Label>
            <Input
              id="email"
              type="email"
              required
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
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="••••••••"
              className="h-10 rounded-xl border-border/80 bg-surface-raised/60"
            />
          </div>
          <Button
            type="submit"
            className="h-10 w-full rounded-xl bg-primary text-primary-foreground shadow-ember hover:bg-primary-hover"
          >
            {mode === "login" ? "Log in" : "Create account"}
          </Button>
        </form>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          {mode === "login" ? "No account yet?" : "Already have an account?"}{" "}
          <button
            type="button"
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            className="font-medium text-primary hover:text-primary-hover"
          >
            {mode === "login" ? "Sign up" : "Log in"}
          </button>
        </p>

        {!forced && (
          <button
            type="button"
            onClick={onCancel}
            className="mt-3 w-full text-center text-xs text-muted-foreground hover:text-foreground"
          >
            Continue as guest
          </button>
        )}
      </motion.div>
    </div>
  );
}
