import { useEffect, useState } from "react";
import { motion } from "motion/react";
import {
  Check,
  Copy,
  Eye,
  Image as ImageIcon,
  Loader2,
  Pencil,
  RefreshCw,
  Sparkles,
  Edit2,
  Save,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
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
  onUpdatePost?: (updated: GeneratedPost) => void;
  onRegenerate: () => void;
  onGenerateImage?: () => void;
};

export function PostCard({
  post,
  index,
  regenerating,
  onView,
  onEdit,
  onUpdatePost,
  onRegenerate,
  onGenerateImage,
}: Props) {
  const [copied, setCopied] = useState(false);
  const [imgError, setImgError] = useState(false);
  const [isInlineEditing, setIsInlineEditing] = useState(false);

  // Local editing states
  const [inlineTitle, setInlineTitle] = useState(post.title);
  const [inlineHook, setInlineHook] = useState(post.hook);

  useEffect(() => {
    setInlineTitle(post.title);
    setInlineHook(post.hook);
  }, [post.title, post.hook]);

  const displayImgUrl = post.imageUrl
    ? getImageUrl(post.imageUrl)
    : post.imageAssetId
    ? getImageUrl(post.imageAssetId)
    : null;

  function handleCopy() {
    const text = `${post.hook}\n\n${post.caption}\n\n${post.hashtags.join(" ")}`;
    void navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("Post copied to clipboard");
    window.setTimeout(() => setCopied(false), 1600);
  }

  function handleSaveInline() {
    if (onUpdatePost) {
      onUpdatePost({
        ...post,
        title: inlineTitle.trim() || post.title,
        hook: inlineHook.trim() || post.hook,
      });
    }
    setIsInlineEditing(false);
    toast.success("Post updated!");
  }

  function handleCancelInline() {
    setInlineTitle(post.title);
    setInlineHook(post.hook);
    setIsInlineEditing(false);
  }

  return (
    <motion.article
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: index * 0.04, ease: [0.22, 1, 0.36, 1] }}
      className="group relative overflow-hidden rounded-3xl border border-white/10 bg-[#0E131F]/90 p-5 shadow-2xl backdrop-blur-xl transition-all hover:border-primary/40 flex flex-col justify-between"
    >
      <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-linear-to-r from-transparent via-primary/50 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />

      <div>
        <header className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <PlatformBadge platform={post.platform} />
            <span className="font-mono text-xs text-primary font-bold">Post {index}</span>
          </div>
          {displayImgUrl && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
              <Sparkles className="size-2.5" /> Visual Ready
            </span>
          )}
        </header>

        {/* Thumbnail / Generating Preview Area */}
        {post.isGeneratingImage ? (
          <div className="mt-3 relative flex h-36 w-full flex-col items-center justify-center rounded-2xl border border-primary/40 bg-primary/5 p-3 text-center">
            <Loader2 className="size-5 animate-spin text-primary" />
            <span className="mt-2 font-mono text-xs text-primary font-bold">Generating background art...</span>
            <span className="text-[11px] text-slate-400">FLUX / Imagen pipeline active</span>
          </div>
        ) : displayImgUrl && !imgError ? (
          <button
            type="button"
            onClick={onView}
            className="mt-3 group/img relative aspect-video w-full overflow-hidden rounded-2xl border border-white/10 bg-black/50"
          >
            <img
              src={displayImgUrl}
              alt={post.title}
              onError={() => setImgError(true)}
              className="h-full w-full object-cover transition-transform duration-300 group-hover/img:scale-105"
              loading="lazy"
            />
            <div className="absolute inset-0 bg-black/40 opacity-0 backdrop-blur-[1px] transition-opacity group-hover/img:opacity-100 flex items-center justify-center">
              <span className="rounded-xl bg-white/90 px-3 py-1.5 text-xs font-bold text-black shadow-md">
                Open in Studio →
              </span>
            </div>
          </button>
        ) : null}

        {/* Post Text: Inline Editable or View Mode */}
        {isInlineEditing ? (
          <div className="mt-3 space-y-2 rounded-2xl border border-primary/40 bg-white/5 p-3">
            <div className="space-y-1">
              <label className="text-[10px] font-mono uppercase text-slate-400 font-bold">Headline</label>
              <Input
                value={inlineTitle}
                onChange={(e) => setInlineTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveInline();
                  if (e.key === "Escape") handleCancelInline();
                }}
                className="h-9 text-xs font-bold bg-black/40 text-white rounded-lg border-white/15"
                placeholder="Slide headline"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-mono uppercase text-slate-400 font-bold">Hook</label>
              <Input
                value={inlineHook}
                onChange={(e) => setInlineHook(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleSaveInline();
                  if (e.key === "Escape") handleCancelInline();
                }}
                className="h-9 text-xs bg-black/40 text-white rounded-lg border-white/15"
                placeholder="Subtitle hook"
              />
            </div>
            <div className="flex items-center justify-end gap-1.5 pt-1">
              <Button size="sm" variant="ghost" onClick={handleCancelInline} className="h-7 text-xs text-slate-400">
                <X className="size-3 mr-1" /> Cancel
              </Button>
              <Button size="sm" onClick={handleSaveInline} className="h-7 text-xs bg-primary text-black font-bold">
                <Save className="size-3 mr-1" /> Save
              </Button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => setIsInlineEditing(true)}
            className="mt-3.5 block w-full text-left cursor-pointer group/text rounded-xl p-1 -m-1 transition-colors hover:bg-white/[0.03]"
            title="Click to edit text directly"
          >
            <div className="flex items-start justify-between gap-1">
              <h3 className="text-[15px] font-bold leading-snug text-white transition-colors group-hover/text:text-primary">
                {post.title}
              </h3>
              <Edit2 className="size-3 text-slate-500 opacity-0 group-hover/text:opacity-100 transition-opacity shrink-0 mt-1" />
            </div>
            <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-300">
              {post.hook}
            </p>
          </div>
        )}
      </div>

      <footer className="mt-5 flex items-center justify-between gap-2 border-t border-white/10 pt-3.5">
        <div className="flex items-center gap-1.5">
          <Button
            size="sm"
            onClick={onView}
            className="h-8 gap-1.5 rounded-xl bg-white/10 border border-white/15 px-3 text-xs font-semibold text-white hover:bg-white/20 transition-all shadow-sm"
          >
            <Sparkles className="size-3.5 text-primary" />
            Visual Studio
          </Button>

          {onGenerateImage && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onGenerateImage}
              disabled={post.isGeneratingImage}
              className={`h-8 gap-1.5 rounded-xl px-2.5 text-xs text-slate-300 hover:text-white ${
                !displayImgUrl ? "border border-primary/40 bg-primary/10 text-primary hover:bg-primary/20" : ""
              }`}
            >
              {post.isGeneratingImage ? (
                <Loader2 className="size-3.5 animate-spin" />
              ) : displayImgUrl ? (
                <ImageIcon className="size-3.5" />
              ) : (
                <Sparkles className="size-3.5 text-primary" />
              )}
              {displayImgUrl ? "Regen BG" : "Generate BG"}
            </Button>
          )}
        </div>

        <div className="flex items-center gap-0.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsInlineEditing((prev) => !prev)}
                aria-label="Quick edit inline"
                className="size-8 rounded-lg text-slate-400 hover:bg-white/10 hover:text-white"
              >
                <Pencil className="size-3.5" />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Quick Edit</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleCopy}
                aria-label="Copy text"
                className="size-8 rounded-lg text-slate-400 hover:bg-white/10 hover:text-white"
              >
                {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">{copied ? "Copied" : "Copy text"}</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onRegenerate}
                aria-label="Regenerate post"
                className="size-8 rounded-lg text-slate-400 hover:bg-white/10 hover:text-white"
              >
                <RefreshCw className={regenerating ? "size-3.5 animate-spin text-primary" : "size-3.5"} />
              </Button>
            </TooltipTrigger>
            <TooltipContent side="top">Regenerate post</TooltipContent>
          </Tooltip>
        </div>
      </footer>
    </motion.article>
  );
}

export function PostCardSkeleton({ index }: { index: number }) {
  return (
    <div
      className="rounded-3xl border border-white/10 bg-white/[0.03] p-5 backdrop-blur-md"
      style={{ animationDelay: `${index * 90}ms` }}
    >
      <div className="flex items-center gap-2">
        <div className="h-5 w-20 animate-pulse rounded-md bg-white/10" />
        <div className="h-3 w-12 animate-pulse rounded-full bg-white/10" />
      </div>
      <div className="mt-3 h-3.5 w-3/5 animate-pulse rounded-full bg-white/10" />
      <div className="mt-2 h-3 w-4/5 animate-pulse rounded-full bg-white/5" />
      <div className="mt-4 h-8 w-28 animate-pulse rounded-xl bg-white/10" />
    </div>
  );
}
