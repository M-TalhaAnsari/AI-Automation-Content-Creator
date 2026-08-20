import { motion } from "motion/react";
import { Database, Image as ImageIcon, Palette, Sliders, Sparkle } from "lucide-react";

import { SOURCES } from "./data";
import { PLATFORMS } from "./data";

type Props = {
  platform: string;
  postCount: number;
  constraints: string[];
  activeSources: string[];
  visualMood?: string;
  onVisualMoodChange?: (mood: string) => void;
};

const VISUAL_MOODS = [
  { id: "clean-informative", label: "Clean Informative", color: "#00d2ff" },
  { id: "dark-tech", label: "Dark Tech & Cyber", color: "#e94560" },
  { id: "bold-contrast", label: "Bold High Contrast", color: "#ffb703" },
  { id: "minimal-light", label: "Minimalist Editorial", color: "#10b981" },
];

export function ContextPanel({
  platform,
  postCount,
  constraints,
  activeSources,
  visualMood = "clean-informative",
  onVisualMoodChange,
}: Props) {
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

      {/* Visual Direction & Brand Style */}
      <section className="mt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Palette className="size-3.5 text-muted-foreground" />
            <h2 className="label-mono">Visual Styling</h2>
          </div>
          <span className="text-[10px] font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded">
            Modular
          </span>
        </div>
        <div className="mt-3 space-y-1.5">
          {VISUAL_MOODS.map((mood) => {
            const isSelected = visualMood === mood.id;
            return (
              <button
                key={mood.id}
                type="button"
                onClick={() => onVisualMoodChange?.(mood.id)}
                className={`flex w-full items-center justify-between rounded-lg border px-3 py-2 text-left text-xs transition-all ${
                  isSelected
                    ? "border-primary/50 bg-primary/10 text-foreground font-medium"
                    : "border-border/50 bg-surface-raised/30 text-muted-foreground hover:border-border hover:text-foreground"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="size-2 rounded-full"
                    style={{ backgroundColor: mood.color }}
                  />
                  <span>{mood.label}</span>
                </div>
                {isSelected && (
                  <span className="font-mono text-[10px] text-primary">Active</span>
                )}
              </button>
            );
          })}
        </div>
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          Visual prompts and color palettes adapt automatically based on the active style profile.
        </p>
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
