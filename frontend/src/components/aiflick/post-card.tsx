import { useState } from "react";
import { motion } from "motion/react";
import { Check, Copy, Eye, Pencil, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { PlatformBadge } from "./platform-badge";
import type { GeneratedPost } from "./data";

type Props = {
  post: GeneratedPost;
  index: number;
  regenerating?: boolean;
  onView: () => void;
  onEdit: () => void;
  onRegenerate: () => void;
};

export function PostCard({
  post,
  index,
  regenerating,
  onView,
  onEdit,
  onRegenerate,
}: Props) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    const text = `${post.hook}\n\n${post.caption}\n\n${post.hashtags.join(" ")}`;
    void navigator.clipboard.writeText(text);
    setCopied(true);
    toast("Post copied to clipboard");
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: index * 0.04, ease: [0.22, 1, 0.36, 1] }}
      className="group relative overflow-hidden rounded-2xl border border-border/70 bg-card/80 p-4 shadow-panel transition-colors hover:border-primary/35"
    >
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <header className="flex items-center gap-2">
        <PlatformBadge platform={post.platform} />
        <span className="label-mono text-muted-foreground">Post {index}</span>
        {post.edits && post.edits.length > 0 && (
          <span className="label-mono text-primary/80">
            · edited {post.edits.length}x
          </span>
        )}
      </header>

      <button
        type="button"
        onClick={onView}
        className="mt-3 block w-full text-left"
        aria-label={`View post ${index}: ${post.title}`}
      >
        <h3 className="text-[15px] leading-snug font-medium text-foreground transition-colors group-hover:text-primary">
          {post.title}
        </h3>
        <p className="mt-1.5 line-clamp-2 text-[13px] leading-relaxed text-muted-foreground">
          {post.hook}
        </p>
      </button>

      <footer className="mt-4 flex items-center justify-between gap-2">
        <Button
          size="sm"
          variant="secondary"
          onClick={onView}
          className="h-8 gap-1.5 rounded-lg px-2.5 text-xs"
        >
          <Eye className="size-3.5" />
          View post
        </Button>

        <div className="flex items-center gap-0.5">
          <IconAction
            label={copied ? "Copied" : "Copy"}
            icon={copied ? Check : Copy}
            onClick={handleCopy}
          />
          <IconAction label="Edit with a prompt" icon={Pencil} onClick={onEdit} />
          <IconAction
            label="Regenerate"
            icon={RefreshCw}
            spinning={regenerating}
            onClick={onRegenerate}
          />
        </div>
      </footer>
    </motion.article>
  );
}

function IconAction({
  label,
  icon: Icon,
  onClick,
  spinning,
}: {
  label: string;
  icon: typeof Copy;
  onClick: () => void;
  spinning?: boolean | undefined;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClick}
          aria-label={label}
          className="size-8 rounded-lg text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          <Icon className={spinning ? "size-3.5 animate-spin" : "size-3.5"} />
        </Button>
      </TooltipTrigger>
      <TooltipContent side="top">{label}</TooltipContent>
    </Tooltip>
  );
}

export function PostCardSkeleton({ index }: { index: number }) {
  return (
    <div
      className="rounded-2xl border border-border/60 bg-card/50 p-4"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      <div className="flex items-center gap-2">
        <div className="h-5 w-20 animate-pulse rounded-md bg-secondary" />
        <div className="h-3 w-12 animate-pulse rounded-full bg-secondary" />
      </div>
      <div className="mt-3 h-3.5 w-3/5 animate-pulse rounded-full bg-secondary" />
      <div className="mt-2 h-3 w-4/5 animate-pulse rounded-full bg-secondary/70" />
      <div className="mt-4 h-8 w-28 animate-pulse rounded-lg bg-secondary/60" />
    </div>
  );
}
