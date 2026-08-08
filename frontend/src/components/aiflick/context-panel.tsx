import { motion } from "motion/react";
import { Database, Sliders, Sparkle } from "lucide-react";

import { SOURCES } from "./data";
import { PLATFORMS } from "./data";

type Props = {
  platform: string;
  postCount: number;
  constraints: string[];
  activeSources: string[];
};

export function ContextPanel({ platform, postCount, constraints, activeSources }: Props) {
  const platformLabel =
    PLATFORMS.find((p) => p.value === platform)?.label ?? "Auto-detect";

  return (
    <motion.aside
      initial={{ opacity: 0, x: 12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 12 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className="hidden h-full w-[300px] shrink-0 overflow-y-auto border-l border-border/70 bg-sidebar px-4 py-5 scroll-quiet lg:block"
    >
      <section>
        <div className="flex items-center gap-2">
          <Sliders className="size-3.5 text-muted-foreground" />
          <h2 className="label-mono">Run settings</h2>
        </div>
        <dl className="mt-3 space-y-2 text-sm">
          <div className="flex items-center justify-between rounded-lg bg-surface-raised/50 px-3 py-2">
            <dt className="text-muted-foreground">Platform</dt>
            <dd className="text-foreground">{platformLabel}</dd>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-surface-raised/50 px-3 py-2">
            <dt className="text-muted-foreground">Posts per run</dt>
            <dd className="font-mono text-foreground">{postCount}</dd>
          </div>
        </dl>
      </section>

      <section className="mt-6">
        <div className="flex items-center gap-2">
          <Sparkle className="size-3.5 text-muted-foreground" />
          <h2 className="label-mono">Active constraints</h2>
        </div>
        {constraints.length === 0 ? (
          <p className="mt-3 text-xs leading-relaxed text-muted-foreground">
            None yet. Tell the assistant things like "avoid emojis" and they'll persist
            across this session.
          </p>
        ) : (
          <ul className="mt-3 space-y-1.5">
            {constraints.map((c) => (
              <li
                key={c}
                className="rounded-lg border border-border/60 bg-surface-raised/40 px-3 py-1.5 text-xs text-foreground"
              >
                {c}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-6">
        <div className="flex items-center gap-2">
          <Database className="size-3.5 text-muted-foreground" />
          <h2 className="label-mono">Sources</h2>
        </div>
        <ul className="mt-3 space-y-1">
          {SOURCES.map((source) => {
            const used = activeSources.includes(source);
            return (
              <li
                key={source}
                className="flex items-center justify-between px-1 py-1.5 text-xs"
              >
                <span className={used ? "text-foreground" : "text-muted-foreground"}>
                  {source}
                </span>
                <span
                  className={
                    used
                      ? "size-1.5 rounded-full bg-success"
                      : "size-1.5 rounded-full bg-border-strong"
                  }
                  aria-label={used ? "used in last run" : "idle"}
                />
              </li>
            );
          })}
        </ul>
      </section>
    </motion.aside>
  );
}
