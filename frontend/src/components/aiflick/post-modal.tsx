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
  Edit3,
  Sliders,
  Send,
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
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { PlatformBadge } from "./platform-badge";
import { SocialPostCanvas } from "./social-post-canvas";
import { getImageUrl } from "@/api";
import type { GeneratedPost } from "./data";

const QUICK_TEXT_PROMPTS = [
  "Convert caption to bullet points",
  "Make on-screen text punchier & shorter",
  "Add high-conversion curiosity hook",
  "Format as 5-step carousel breakdown",
  "Make it conversational & casual",
];

const QUICK_VISUAL_PROMPTS = [
  "Minimalist dark obsidian tech card",
  "Clean geometric blueprint with glowing cyan accents",
  "Futuristic 3D isometric abstract render",
  "Cinematic studio lighting with soft bokeh",
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
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"studio" | "text">("studio");

  // Local editable fields for live synchronization
  const [editableTitle, setEditableTitle] = useState("");
  const [editableHook, setEditableHook] = useState("");
  const [editableCaption, setEditableCaption] = useState("");

  useEffect(() => {
    if (open && post) {
      setInstruction("");
      setVisualPrompt("");
      setEditableTitle(post.title || "");
      setEditableHook(post.hook || "");
      setEditableCaption(post.caption || "");
    }
  }, [open, post?.id, post?.title, post?.hook, post?.caption]);

  if (!post) return null;

  const displayImgUrl = post.imageUrl || (post.imageAssetId ? getImageUrl(post.imageAssetId, true) : null);

  function submitTextPrompt() {
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
    toast.info("Generating AI background in background...");
  }

  function handleCopy() {
    if (!post) return;
    void navigator.clipboard.writeText(
      `${editableHook || post.hook}\n\n${editableCaption || post.caption}\n\n${post.hashtags.join(" ")}`
    );
    setCopied(true);
    toast.success("Full post copied to clipboard!");
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex h-[96vh] flex-col gap-0 overflow-hidden rounded-2xl border-border/70 bg-surface-raised/95 p-0 shadow-2xl backdrop-blur-2xl sm:max-w-6xl"
      >
        {/* Modal Header */}
        <DialogHeader className="space-y-2 border-b border-border/60 px-5 pt-4 pb-3 text-left sm:px-6">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <PlatformBadge platform={post.platform} />
              <span className="label-mono text-xs text-muted-foreground font-semibold">Post {index}</span>
              {post.latencyMs && (
                <span className="rounded-full bg-secondary/80 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                  ⚡ {(post.latencyMs / 1000).toFixed(1)}s
                </span>
              )}
            </div>

            {/* View Mode Switcher */}
            <div className="flex items-center gap-1 rounded-xl bg-secondary/60 p-1 border border-border/50">
              <button
                type="button"
                onClick={() => setActiveTab("studio")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  activeTab === "studio"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Sparkles className="size-3.5 text-primary" /> Visual Studio & Canvas
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("text")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                  activeTab === "text"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Edit3 className="size-3.5" /> Full Copy & Description
              </button>
            </div>
          </div>

          <DialogTitle className="text-lg font-bold tracking-tight sm:text-xl text-foreground">
            {editableTitle || post.title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Post Studio for editing visuals, typography, hooks, descriptions and hashtags.
          </DialogDescription>
        </DialogHeader>

        {/* Modal Body */}
        <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet px-5 py-4 sm:px-6">
          <AnimatePresence mode="wait" initial={false}>
            {activeTab === "studio" ? (
              <motion.div
                key="tab-studio"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="grid grid-cols-1 lg:grid-cols-12 gap-6"
              >
                {/* Left 8 Columns: Fabric Canvas Studio */}
                <div className="lg:col-span-8 space-y-4">
                  <SocialPostCanvas
                    backgroundImageUrl={displayImgUrl}
                    title={editableTitle || post.title}
                    hook={editableHook || post.hook}
                    summary={post.summary || post.caption}
                    platform={post.platform}
                    authorHandle="@aiflick"
                    onRegenerateBg={() => submitVisualGeneration()}
                    isGeneratingBg={post.isGeneratingImage}
                  />
                </div>

                {/* Right 4 Columns: Editable Content & AI Text Rewriter */}
                <div className="lg:col-span-4 flex flex-col gap-4 border-t lg:border-t-0 lg:border-l border-border/60 pt-4 lg:pt-0 lg:pl-6">
                  {/* Quick AI Rewriter Prompt Bar */}
                  <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 space-y-2.5">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-primary flex items-center gap-1.5">
                        <Sparkles className="size-3.5" /> AI Content Assistant
                      </span>
                      <span className="text-[10px] text-muted-foreground">Rewrite post in 1-click</span>
                    </div>

                    <div className="flex flex-wrap gap-1">
                      {QUICK_TEXT_PROMPTS.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          disabled={editing}
                          onClick={() => setInstruction(prompt)}
                          className="rounded-full border border-border/70 bg-background/80 px-2 py-0.5 text-[10px] text-muted-foreground hover:border-primary/50 hover:text-foreground transition-colors disabled:opacity-40"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Input
                        value={instruction}
                        onChange={(e) => setInstruction(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" && !e.shiftKey) {
                            e.preventDefault();
                            submitTextPrompt();
                          }
                        }}
                        disabled={editing}
                        placeholder="e.g. Turn into 4 concise bullet points..."
                        className="h-8 text-xs bg-background/90"
                      />
                      <Button
                        size="sm"
                        onClick={submitTextPrompt}
                        disabled={editing || !instruction.trim()}
                        className="h-8 px-2.5 text-xs bg-primary text-primary-foreground hover:bg-primary-hover shrink-0"
                      >
                        {editing ? <Loader2 className="size-3.5 animate-spin" /> : <Send className="size-3" />}
                      </Button>
                    </div>
                  </div>

                  {/* Live Editable Text Fields */}
                  <div className="space-y-3 flex-1">
                    <div className="space-y-1">
                      <label className="text-[11px] font-mono text-muted-foreground font-semibold uppercase">
                        Slide Headline
                      </label>
                      <Input
                        value={editableTitle}
                        onChange={(e) => setEditableTitle(e.target.value)}
                        className="h-8 text-xs font-medium"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-[11px] font-mono text-muted-foreground font-semibold uppercase">
                        Subtext / Hook
                      </label>
                      <Input
                        value={editableHook}
                        onChange={(e) => setEditableHook(e.target.value)}
                        className="h-8 text-xs"
                      />
                    </div>

                    <div className="space-y-1 flex-1">
                      <label className="text-[11px] font-mono text-muted-foreground font-semibold uppercase">
                        Caption / Description (Formatted)
                      </label>
                      <Textarea
                        value={editableCaption}
                        onChange={(e) => setEditableCaption(e.target.value)}
                        rows={6}
                        className="text-xs leading-relaxed resize-none"
                      />
                    </div>
                  </div>

                  {/* AI Visual Prompt Override */}
                  {onGenerateImage && (
                    <div className="rounded-xl border border-border/70 bg-surface-raised/60 p-3 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono text-muted-foreground font-semibold uppercase">
                          Custom Background Art Prompt
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <Input
                          value={visualPrompt}
                          onChange={(e) => setVisualPrompt(e.target.value)}
                          placeholder="e.g. Neon cyber grid on dark obsidian..."
                          className="h-7 text-xs bg-background/80"
                        />
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={submitVisualGeneration}
                          disabled={post.isGeneratingImage}
                          className="h-7 px-2 text-[11px] shrink-0"
                        >
                          <Sparkles className="size-3 text-primary mr-1" />
                          {post.isGeneratingImage ? "Gen..." : "Gen Art"}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="tab-text"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="max-w-3xl mx-auto space-y-5"
              >
                {displayImgUrl && (
                  <div className="relative overflow-hidden rounded-xl border border-border/60 bg-background/50">
                    <img src={displayImgUrl} alt={post.title} className="max-h-60 w-full object-cover" />
                  </div>
                )}

                <div className="space-y-1.5">
                  <span className="label-mono block text-muted-foreground">Hook</span>
                  <p className="text-base font-semibold text-foreground">{editableHook || post.hook}</p>
                </div>

                <div className="space-y-1.5">
                  <span className="label-mono block text-muted-foreground">Caption & Description</span>
                  <div className="space-y-2.5 text-sm leading-relaxed text-foreground/90 whitespace-pre-line bg-secondary/30 p-4 rounded-xl border border-border/50 font-sans">
                    {editableCaption || post.caption}
                  </div>
                </div>

                <div className="space-y-1.5">
                  <span className="label-mono block text-muted-foreground">Hashtags</span>
                  <div className="flex flex-wrap gap-1.5">
                    {post.hashtags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-md bg-secondary/70 px-2 py-1 font-mono text-xs text-primary ring-1 ring-border/50"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {post.sourceUrl && (
                  <div className="space-y-1">
                    <span className="label-mono block text-muted-foreground">Source Reference</span>
                    <a
                      href={post.sourceUrl}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="inline-flex items-center gap-1.5 text-sm text-primary underline-offset-4 hover:underline"
                    >
                      {post.sourceLabel || post.sourceUrl}
                      <ExternalLink className="size-3.5" />
                    </a>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Modal Footer */}
        <div className="border-t border-border/60 bg-background/80 px-5 py-3 sm:px-6 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRegenerate(post.id)}
            disabled={editing}
            className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className="size-3.5" /> Regenerate Post
          </Button>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="h-8 gap-1.5 text-xs"
            >
              {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
              {copied ? "Copied!" : "Copy Post Text"}
            </Button>
            <Button
              size="sm"
              onClick={() => onOpenChange(false)}
              className="h-8 px-4 text-xs font-semibold bg-primary text-primary-foreground"
            >
              Done
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
