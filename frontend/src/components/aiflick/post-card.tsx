import { useState } from "react";
import { motion } from "motion/react";
import { Check, Copy, Eye, Image as ImageIcon, Loader2, Pencil, RefreshCw, Sparkles } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { PlatformBadge } from "./platform-badge";
import { getImageUrl } from "@/api";
import type { GeneratedPost } from "./data";

type Props = {
  post: GeneratedPost;
  index: number;
  regenerating?: boolean;
  onView: () => void;
  onEdit: () => void;
  onRegenerate: () => void;
  onGenerateImage?: () => void;
};

export function PostCard({
  post,
  index,
  regenerating,
  onView,
  onEdit,
  onRegenerate,
  onGenerateImage,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [imgError, setImgError] = useState(false);

  const displayImgUrl = post.imageUrl || (post.imageAssetId ? getImageUrl(post.imageAssetId) : null);

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
      className="group relative overflow-hidden rounded-2xl border border-border/70 bg-card/80 p-4 shadow-panel transition-colors hover:border-primary/35 flex flex-col justify-between"
    >
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div>
        <header className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <PlatformBadge platform={post.platform} />
            <span className="label-mono text-muted-foreground">Post {index}</span>
            {post.edits && post.edits.length > 0 && (
              <span className="label-mono text-primary/80">
                · edited {post.edits.length}x
              </span>
            )}
          </div>
          {displayImgUrl && (
            <span className="inline-flex items-center gap-1 rounded-md bg-primary/10 px-1.5 py-0.5 text-[10px] font-mono text-primary ring-1 ring-primary/20">
              <Sparkles className="size-2.5" /> Visual Ready
            </span>
          )}
        </header>

        {/* Thumbnail / Generating Preview Area */}
        {post.isGeneratingImage ? (
          <div className="mt-3 relative flex h-36 w-full flex-col items-center justify-center rounded-xl border border-primary/30 bg-primary/5 p-3 text-center">
            <Loader2 className="size-5 animate-spin text-primary" />
            <span className="mt-2 font-mono text-xs text-primary font-medium">Generating visual...</span>
            <span className="text-[11px] text-muted-foreground">FLUX / Imagen pipeline active</span>
          </div>
        ) : displayImgUrl && !imgError ? (
          <button
            type="button"
            onClick={onView}
            className="mt-3 group/img relative aspect-video w-full overflow-hidden rounded-xl border border-border/60 bg-background/80"
          >
            <img
              src={displayImgUrl}
              alt={post.title}
              onError={() => setImgError(true)}
              className="h-full w-full object-cover transition-transform duration-300 group-hover/img:scale-105"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-background/30 opacity-0 backdrop-blur-[1px] transition-opacity group-hover/img:opacity-100 flex items-center justify-center">
              <span className="rounded-lg bg-background/90 px-2 py-1 text-[11px] font-medium text-foreground shadow-sm">
                View Full Visual
              </span>
            </div>
          </button>
        ) : null}

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
      </div>

      <footer className="mt-4 flex items-center justify-between gap-2 border-t border-border/40 pt-3">
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            variant="secondary"
            onClick={onView}
            className="h-8 gap-1.5 rounded-lg px-2.5 text-xs"
          >
            <Eye className="size-3.5" />
            View
          </Button>

          {onGenerateImage && (
            <Button
              size="sm"
              variant={displayImgUrl ? "ghost" : "outline"}
              onClick={onGenerateImage}
              disabled={post.isGeneratingImage}
              className={`h-8 gap-1.5 rounded-lg px-2.5 text-xs ${
                !displayImgUrl ? "border-primary/40 bg-primary/5 text-primary hover:bg-primary/10" : ""
              }`}
            >
              {post.isGeneratingImage ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : displayImgUrl ? (
                <ImageIcon className="size-3.5" />
              ) : (
                <Sparkles className="size-3.5" />
              )}
              {displayImgUrl ? "Regen Visual" : "Generate Visual"}
            </Button>
          )}
        </div>

        <div className="flex items-center gap-0.5">
          <IconAction
            label={copied ? "Copied" : "Copy text"}
            icon={copied ? Check : Copy}
            onClick={handleCopy}
          />
          <IconAction label="Edit with a prompt" icon={Pencil} onClick={onEdit} />
          <IconAction
            label="Regenerate post"
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
