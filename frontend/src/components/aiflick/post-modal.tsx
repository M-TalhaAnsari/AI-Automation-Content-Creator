import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowUp,
  Check,
  Copy,
  Download,
  ExternalLink,
  History,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { PlatformBadge } from "./platform-badge";
import { getImageUrl } from "@/api";
import type { GeneratedPost } from "./data";

const QUICK_EDITS = [
  "Make the hook punchier",
  "Shorten the caption",
  "More technical",
  "Swap the hashtags",
];

const QUICK_VISUAL_PROMPTS = [
  "Minimalist dark mode tech card",
  "High-contrast architecture diagram",
  "Clean typographic layout with vibrant accent",
  "Photorealistic developer setup",
];

type Props = {
  post: GeneratedPost | null;
  index: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplyEdit: (postId: string, instruction: string) => void;
  onRegenerate: (postId: string) => void;
  onGenerateImage?: (postId: string, customPrompt?: string) => void;
  editing: boolean;
};

export function PostModal({
  post,
  index,
  open,
  onOpenChange,
  onApplyEdit,
  onRegenerate,
  onGenerateImage,
  editing,
}: Props) {
  const [instruction, setInstruction] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [showVisualPromptInput, setShowVisualPromptInput] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"content" | "visual">("content");

  useEffect(() => {
    if (open) {
      setInstruction("");
      setVisualPrompt("");
      setShowVisualPromptInput(false);
      // Default to visual tab if image exists and user opened modal
      if (post?.imageUrl || post?.imageAssetId) {
        setActiveTab("content");
      }
    }
  }, [open, post?.id]);

  if (!post) return null;

  const displayImgUrl = post.imageUrl || (post.imageAssetId ? getImageUrl(post.imageAssetId) : null);

  function submitTextEdit() {
    const value = instruction.trim();
    if (!value || !post) return;
    onApplyEdit(post.id, value);
    setInstruction("");
  }

  function submitVisualGeneration() {
    if (!post || !onGenerateImage) return;
    const prompt = visualPrompt.trim() || undefined;
    onGenerateImage(post.id, prompt);
    setVisualPrompt("");
    setShowVisualPromptInput(false);
    toast("Image generation queued...");
  }

  function handleCopy() {
    if (!post) return;
    void navigator.clipboard.writeText(
      `${post.hook}\n\n${post.caption}\n\n${post.hashtags.join(" ")}`,
    );
    setCopied(true);
    toast("Post copied to clipboard");
    window.setTimeout(() => setCopied(false), 1600);
  }

  function handleDownloadImage() {
    if (!displayImgUrl) return;
    const a = document.createElement("a");
    a.href = displayImgUrl;
    a.download = `trendforge-${post?.platform || "post"}-${post?.number || index}.png`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast("Image download started");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[92vh] flex-col gap-0 overflow-hidden rounded-2xl border-border/70 bg-surface-raised/95 p-0 shadow-panel backdrop-blur-xl sm:max-h-[90vh] sm:max-w-3xl"
      >
        <DialogHeader className="space-y-3 border-b border-border/60 px-4 pt-5 pb-4 text-left sm:px-6 sm:pt-6 sm:pb-5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <PlatformBadge platform={post.platform} />
              <span className="label-mono text-muted-foreground">Post {index}</span>
            </div>
            {/* View Tab Switcher */}
            <div className="flex items-center gap-1 rounded-lg bg-secondary/60 p-0.5 border border-border/50">
              <button
                type="button"
                onClick={() => setActiveTab("content")}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  activeTab === "content"
                    ? "bg-background text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Post Text
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("visual")}
                className={`flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  activeTab === "visual"
                    ? "bg-background text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Sparkles className="size-3 text-primary" />
                Visual Asset
                {displayImgUrl && <span className="size-1.5 rounded-full bg-primary" />}
              </button>
            </div>
          </div>
          <DialogTitle className="pr-8 text-lg leading-snug tracking-tight sm:text-xl">
            {post.title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Full generated post with hook, caption, hashtags, source, and visual assets.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet px-4 py-5 sm:px-6">
          <AnimatePresence mode="wait" initial={false}>
            {activeTab === "content" ? (
              <motion.div
                key="tab-content"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18 }}
                className="space-y-5"
              >
                {/* Visual Banner Preview if available */}
                {displayImgUrl && (
                  <div className="relative overflow-hidden rounded-xl border border-border/60 bg-background/50">
                    <img
                      src={displayImgUrl}
                      alt={post.title}
                      className="max-h-56 w-full object-cover"
                    />
                    <div className="absolute top-2 right-2 flex items-center gap-1.5">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setActiveTab("visual")}
                        className="h-7 gap-1 rounded-lg bg-background/85 px-2 text-xs backdrop-blur-md hover:bg-background"
                      >
                        <Sparkles className="size-3 text-primary" /> View Visual Tab
                      </Button>
                    </div>
                  </div>
                )}

                <Field label="Hook">
                  <p className="text-[15px] leading-relaxed font-medium text-foreground">
                    {post.hook}
                  </p>
                </Field>

                <Field label="Caption">
                  <div className="space-y-3 text-sm leading-relaxed text-foreground/85">
                    {post.caption.split("\n\n").map((para, i) => (
                      <p key={i}>{para}</p>
                    ))}
                  </div>
                </Field>

                <Field label="Hashtags">
                  <div className="flex flex-wrap gap-1.5">
                    {post.hashtags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md bg-secondary/70 px-2 py-1 font-mono text-[11px] text-primary/90 ring-1 ring-border/50"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </Field>

                <Field label="Source">
                  <a
                    href={post.sourceUrl}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex items-center gap-1.5 text-sm text-primary underline-offset-4 hover:underline"
                  >
                    {post.sourceLabel}
                    <ExternalLink className="size-3.5" />
                  </a>
                </Field>
              </motion.div>
            ) : (
              <motion.div
                key="tab-visual"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.18 }}
                className="space-y-5"
              >
                {post.isGeneratingImage ? (
                  <div className="flex flex-col items-center justify-center rounded-2xl border border-primary/40 bg-primary/5 p-12 text-center">
                    <Loader2 className="size-8 animate-spin text-primary" />
                    <h4 className="mt-4 text-base font-medium text-foreground">
                      Rendering Image Asset...
                    </h4>
                    <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                      Our modular background worker is extracting structured visual briefs and executing with the active provider (FLUX / Imagen).
                    </p>
                  </div>
                ) : displayImgUrl ? (
                  <div className="space-y-4">
                    <div className="relative overflow-hidden rounded-2xl border border-border/70 bg-background/80 shadow-md">
                      <img
                        src={displayImgUrl}
                        alt={post.title}
                        className="w-full object-contain max-h-[480px] mx-auto"
                      />
                    </div>
                    <div className="flex items-center justify-between gap-2 rounded-xl bg-secondary/40 p-3 border border-border/50">
                      <div className="space-y-0.5">
                        <span className="text-xs font-medium text-foreground">Generated Visual Asset</span>
                        <p className="text-[11px] font-mono text-muted-foreground">
                          Platform: {post.platform} · Mode: text_to_image
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={handleDownloadImage}
                          className="h-8 gap-1.5 text-xs"
                        >
                          <Download className="size-3.5" /> Download PNG
                        </Button>
                        {onGenerateImage && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => setShowVisualPromptInput(!showVisualPromptInput)}
                            className="h-8 gap-1.5 text-xs"
                          >
                            <RefreshCw className="size-3.5" /> Regenerate Visual
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border/80 bg-secondary/20 p-10 text-center">
                    <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <ImageIcon className="size-6" />
                    </div>
                    <h4 className="mt-3 text-sm font-medium text-foreground">
                      No Visual Generated Yet
                    </h4>
                    <p className="mt-1 max-w-xs text-xs text-muted-foreground">
                      Generate an AI visual tailored specifically for {post.platform} using brand layouts and high-signal prompt synthesis.
                    </p>
                    {onGenerateImage && (
                      <Button
                        size="sm"
                        onClick={() => submitVisualGeneration()}
                        className="mt-4 gap-1.5 bg-primary text-primary-foreground hover:bg-primary-hover"
                      >
                        <Sparkles className="size-3.5" /> Generate Visual Now
                      </Button>
                    )}
                  </div>
                )}

                {/* Custom Visual Prompt Override Section */}
                {(showVisualPromptInput || !displayImgUrl) && onGenerateImage && !post.isGeneratingImage && (
                  <div className="rounded-xl border border-border/70 bg-surface-raised/60 p-3 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="label-mono text-muted-foreground">Custom Visual Prompt (Optional)</span>
                      <span className="text-[11px] text-muted-foreground">Overrides auto-prompt builder</span>
                    </div>

                    <div className="flex flex-wrap gap-1.5">
                      {QUICK_VISUAL_PROMPTS.map((p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setVisualPrompt(p)}
                          className="rounded-full border border-border/70 px-2.5 py-0.5 text-[10px] text-muted-foreground hover:border-primary/40 hover:text-foreground"
                        >
                          {p}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={visualPrompt}
                        onChange={(e) => setVisualPrompt(e.target.value)}
                        placeholder="e.g. Minimal dark card with neon cyan terminal and Python architecture diagram"
                        className="h-8 flex-1 rounded-lg border border-border/70 bg-background/60 px-2.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary/50 focus:outline-none"
                      />
                      <Button
                        size="sm"
                        onClick={submitVisualGeneration}
                        className="h-8 gap-1.5 text-xs bg-primary text-primary-foreground hover:bg-primary-hover"
                      >
                        <Sparkles className="size-3" /> Generate
                      </Button>
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {activeTab === "content" && post.edits && post.edits.length > 0 && (
            <>
              <Separator className="my-5 bg-border/60" />
              <div className="space-y-2">
                <span className="label-mono flex items-center gap-1.5 text-muted-foreground">
                  <History className="size-3" />
                  Edit history
                </span>
                <ul className="space-y-1.5">
                  {post.edits.map((edit) => (
                    <li
                      key={edit.id}
                      className="flex items-baseline justify-between gap-3 rounded-lg bg-secondary/40 px-3 py-2 text-[13px] text-foreground/80"
                    >
                      <span className="min-w-0">“{edit.instruction}”</span>
                      <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                        {edit.atLabel}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </div>

        {/* Text Edit Footer */}
        {activeTab === "content" && (
          <div className="border-t border-border/60 bg-background/60 px-4 py-4 sm:px-6">
            <span className="label-mono text-muted-foreground">Edit this post</span>

            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {QUICK_EDITS.map((quick) => (
                <button
                  key={quick}
                  type="button"
                  disabled={editing}
                  onClick={() => setInstruction(quick)}
                  className="rounded-full border border-border/70 px-2.5 py-1 text-[11px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground disabled:opacity-50"
                >
                  {quick}
                </button>
              ))}
            </div>

            <div className="mt-3 rounded-xl border border-border/70 bg-surface-raised/60 p-2 transition-colors focus-within:border-primary/50">
              <Textarea
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submitTextEdit();
                  }
                }}
                rows={2}
                disabled={editing}
                placeholder="Describe the change — e.g. make the hook shorter and drop the last hashtag"
                className="max-h-28 min-h-0 resize-none border-0 bg-transparent px-2 py-1.5 text-sm shadow-none focus-visible:ring-0 dark:bg-transparent"
              />
              <div className="flex items-center justify-between gap-2 px-1">
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={editing}
                  onClick={() => onRegenerate(post.id)}
                  className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <RefreshCw className="size-3.5" />
                  Regenerate
                </Button>
                <div className="flex items-center gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCopy}
                    className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                  >
                    {copied ? (
                      <Check className="size-3.5" />
                    ) : (
                      <Copy className="size-3.5" />
                    )}
                    {copied ? "Copied" : "Copy"}
                  </Button>
                  <Button
                    size="icon"
                    onClick={submitTextEdit}
                    disabled={editing || instruction.trim().length === 0}
                    aria-label="Apply edit"
                    className="size-8 rounded-lg bg-primary text-primary-foreground hover:bg-primary-hover disabled:opacity-40"
                  >
                    {editing ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <ArrowUp className="size-4" />
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1.5">
      <span className="label-mono block text-muted-foreground">{label}</span>
      {children}
    </section>
  );
}
