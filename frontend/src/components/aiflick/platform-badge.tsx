import type { LucideIcon } from "lucide-react";
import { Instagram, Linkedin, Youtube, MessageCircle, Sparkle, Twitter } from "lucide-react";

import { cn } from "@/lib/utils";

const MAP: Record<string, { label: string; icon: LucideIcon }> = {
  instagram: { label: "Instagram", icon: Instagram },
  linkedin: { label: "LinkedIn", icon: Linkedin },
  x: { label: "X", icon: Twitter },
  youtube: { label: "YouTube", icon: Youtube },
  reddit: { label: "Reddit", icon: MessageCircle },
  auto: { label: "Auto", icon: Sparkle },
};

export function PlatformBadge({
  platform,
  className,
}: {
  platform: string;
  className?: string;
}) {
  const meta = MAP[platform] ?? { label: "Auto", icon: Sparkle };
  const Icon = meta.icon;


  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md bg-secondary/80 px-2 py-1 text-[11px] font-medium text-foreground/80 ring-1 ring-border/60",
        className,
      )}
    >
      <Icon className="size-3 text-primary" />
      {meta.label}
    </span>
  );
}
