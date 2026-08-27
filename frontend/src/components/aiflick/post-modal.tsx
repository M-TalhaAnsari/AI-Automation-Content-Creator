import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Check,
  Copy,
  ExternalLink,
  Loader2,
  RefreshCw,
  Sparkles,
  Edit3,
  Send,
  Plus,
  Trash2,
  Save,
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

type Props = {
  post: GeneratedPost | null;
  index: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplyEdit: (postId: string, instruction: string) => void;
  onUpdatePost?: (updatedPost: GeneratedPost) => void;
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
  onUpdatePost,
  onRegenerate,
  onGenerateImage,
  editing,
}: Props) {
  const [instruction, setInstruction] = useState("");
  const [visualPrompt, setVisualPrompt] = useState("");
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"studio" | "text">("studio");

  // Local editable fields
  const [editableTitle, setEditableTitle] = useState("");
  const [editableHook, setEditableHook] = useState("");
  const [editableBullets, setEditableBullets] = useState<string[]>([]);
  const [editableCaption, setEditableCaption] = useState("");

  useEffect(() => {
    if (open && post) {
      setInstruction("");
      setVisualPrompt("");
      setEditableTitle(post.title || "");
      setEditableHook(post.hook || "");
      
      const bullets = Array.isArray(post.summary) && post.summary.length > 0
        ? post.summary
        : typeof post.summary === "string"
        ? (post.summary as string).split("\n").filter(Boolean)
        : [
            "1. Core Problem & Architecture",
            "2. Step-by-Step Implementation",
            "3. Key Takeaways & Results",
          ];
      setEditableBullets(bullets);
      setEditableCaption(post.caption || "");
    }
  }, [open, post?.id]);

  if (!post) return null;

  const displayImgUrl = post.imageUrl
    ? getImageUrl(post.imageUrl, true)
    : post.imageAssetId
    ? getImageUrl(post.imageAssetId, true)
    : null;

  // Real-time synchronization helper
  function updateField(fields: Partial<GeneratedPost>) {
    if (!post || !onUpdatePost) return;
    const updated: GeneratedPost = {
      ...post,
      ...fields,
    };
    onUpdatePost(updated);
  }

  function handleTitleChange(val: string) {
    setEditableTitle(val);
    updateField({ title: val });
  }

  function handleHookChange(val: string) {
    setEditableHook(val);
    updateField({ hook: val });
  }

  function handleBulletChange(idx: number, val: string) {
    const updated = [...editableBullets];
    updated[idx] = val;
    setEditableBullets(updated);
    updateField({ summary: updated });
  }

  function handleAddBullet() {
    const updated = [...editableBullets, `${editableBullets.length + 1}. Key takeaway`];
    setEditableBullets(updated);
    updateField({ summary: updated });
  }

  function handleRemoveBullet(idx: number) {
    const updated = editableBullets.filter((_, i) => i !== idx);
    setEditableBullets(updated);
    updateField({ summary: updated });
  }

  function handleCaptionChange(val: string) {
    setEditableCaption(val);
    updateField({ caption: val });
  }

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
    toast.info("Generating AI background art in background...");
  }

  function handleCopy() {
    if (!post) return;
    void navigator.clipboard.writeText(
      `${editableHook || post.hook}\n\n${editableCaption || post.caption}\n\n${post.hashtags.join(" ")}`
    );
    setCopied(true);
    toast.success("Post copy and caption copied to clipboard!");
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex h-[96vh] flex-col gap-0 overflow-hidden rounded-3xl border-white/15 bg-[#0D111A]/95 p-0 shadow-2xl backdrop-blur-2xl sm:max-w-6xl text-foreground"
      >
        {/* Modal Header */}
        <DialogHeader className="space-y-2 border-b border-white/10 px-6 pt-4 pb-3 text-left">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <PlatformBadge platform={post.platform} />
              <span className="font-mono text-xs text-primary font-bold">Post {index}</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 font-mono text-[10px] text-emerald-400">
                <Check className="size-3" /> Live Real-Time Sync
              </span>
            </div>

            {/* View Mode Switcher */}
            <div className="flex items-center gap-1 rounded-2xl bg-white/5 p-1 border border-white/10">
              <button
                type="button"
                onClick={() => setActiveTab("studio")}
                className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all ${
                  activeTab === "studio"
                    ? "bg-white text-black shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Sparkles className="size-3.5 text-primary" /> Visual Studio & Canvas
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("text")}
                className={`flex items-center gap-1.5 rounded-xl px-3.5 py-1.5 text-xs font-bold transition-all ${
                  activeTab === "text"
                    ? "bg-white text-black shadow-md"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                <Edit3 className="size-3.5" /> Full Copy & Description
              </button>
            </div>
          </div>

          <DialogTitle className="text-xl font-bold tracking-tight text-white sm:text-2xl">
            {editableTitle || post.title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Post Studio for editing visuals, typography, hooks, descriptions and hashtags.
          </DialogDescription>
        </DialogHeader>

        {/* Modal Body */}
        <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet px-6 py-5">
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
                {/* Left 7 Columns: Fabric Canvas Studio */}
                <div className="lg:col-span-7 space-y-4">
                  <SocialPostCanvas
                    backgroundImageUrl={displayImgUrl}
                    title={editableTitle}
                    hook={editableHook}
                    summary={editableBullets}
                    platform={post.platform}
                    authorHandle="@aiflick"
                    onRegenerateBg={() => submitVisualGeneration()}
                    isGeneratingBg={post.isGeneratingImage}
                    onTitleChange={(v) => handleTitleChange(v)}
                    onHookChange={(v) => handleHookChange(v)}
                    onSummaryChange={(bullets) => {
                      setEditableBullets(bullets);
                      updateField({ summary: bullets });
                    }}
                  />
                </div>

                {/* Right 5 Columns: Large Editable Fields & AI Assistant */}
                <div className="lg:col-span-5 flex flex-col gap-5 border-t lg:border-t-0 lg:border-l border-white/10 pt-4 lg:pt-0 lg:pl-6">
                  {/* Quick AI Content Assistant */}
                  <div className="rounded-2xl border border-primary/40 bg-primary/5 p-4 space-y-3 shadow-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-primary flex items-center gap-1.5 uppercase font-mono">
                        <Sparkles className="size-3.5" /> AI Content Assistant
                      </span>
                      <span className="text-[11px] text-slate-400">1-click rewrite</span>
                    </div>

                    <div className="flex flex-wrap gap-1.5">
                      {QUICK_TEXT_PROMPTS.map((prompt) => (
                        <button
                          key={prompt}
                          type="button"
                          disabled={editing}
                          onClick={() => setInstruction(prompt)}
                          className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300 hover:border-primary/50 hover:text-white transition-colors disabled:opacity-40"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-2">
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
                        placeholder="e.g. Make headline punchier, format in 3 clear steps..."
                        className="h-10 text-xs bg-black/40 border-white/15 text-white placeholder:text-slate-500 rounded-xl"
                      />
                      <Button
                        size="sm"
                        onClick={submitTextPrompt}
                        disabled={editing || !instruction.trim()}
                        className="h-10 px-3.5 text-xs bg-primary text-black font-bold hover:bg-primary-hover shrink-0 rounded-xl shadow-ember"
                      >
                        {editing ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-3.5" />}
                      </Button>
                    </div>
                  </div>

                  {/* Spacious Live Editable Text Inputs */}
                  <div className="space-y-4 flex-1">
                    {/* Headline Box */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                        Slide Headline
                      </label>
                      <Input
                        value={editableTitle}
                        onChange={(e) => handleTitleChange(e.target.value)}
                        placeholder="Main on-screen headline"
                        className="h-12 text-sm font-bold bg-white/5 border-white/15 text-white rounded-xl focus:border-primary"
                      />
                    </div>

                    {/* Subtext / Hook Box */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                        Subtext / Hook (On-Screen)
                      </label>
                      <Input
                        value={editableHook}
                        onChange={(e) => handleHookChange(e.target.value)}
                        placeholder="Subtitle hook"
                        className="h-12 text-sm bg-white/5 border-white/15 text-white rounded-xl focus:border-primary"
                      />
                    </div>

                    {/* Bullet Points Box */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                          Key Points (Card Bullets)
                        </label>
                        <button
                          type="button"
                          onClick={handleAddBullet}
                          className="inline-flex items-center gap-1 text-[11px] font-mono text-primary hover:underline"
                        >
                          <Plus className="size-3" /> Add Point
                        </button>
                      </div>
                      <div className="space-y-2">
                        {editableBullets.map((bullet, bIdx) => (
                          <div key={bIdx} className="flex items-center gap-2">
                            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-primary/20 text-[11px] font-mono text-primary font-bold">
                              {bIdx + 1}
                            </span>
                            <Input
                              value={bullet}
                              onChange={(e) => handleBulletChange(bIdx, e.target.value)}
                              className="h-10 text-xs bg-white/5 border-white/15 text-white rounded-xl"
                            />
                            {editableBullets.length > 1 && (
                              <button
                                type="button"
                                onClick={() => handleRemoveBullet(bIdx)}
                                className="grid size-8 shrink-0 place-items-center rounded-lg text-slate-500 hover:text-destructive hover:bg-destructive/10"
                                title="Remove point"
                              >
                                <Trash2 className="size-3.5" />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Caption / Description Box */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-mono text-slate-300 font-bold uppercase tracking-wider">
                        Full Caption / Description (Rich Content)
                      </label>
                      <Textarea
                        value={editableCaption}
                        onChange={(e) => handleCaptionChange(e.target.value)}
                        rows={8}
                        placeholder="Write the full in-depth post caption..."
                        className="text-sm leading-relaxed bg-white/5 border-white/15 text-slate-200 rounded-2xl resize-none p-3.5 focus:border-primary"
                      />
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              /* TAB 2: Full Copy View */
              <motion.div
                key="tab-text"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.15 }}
                className="max-w-3xl mx-auto space-y-6"
              >
                {displayImgUrl && (
                  <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-black/50">
                    <img src={displayImgUrl} alt={post.title} className="max-h-64 w-full object-cover" />
                  </div>
                )}

                <div className="space-y-2">
                  <span className="font-mono text-xs text-primary uppercase font-bold">Headline</span>
                  <p className="text-xl font-bold text-white">{editableTitle || post.title}</p>
                </div>

                <div className="space-y-2">
                  <span className="font-mono text-xs text-primary uppercase font-bold">Hook</span>
                  <p className="text-base font-semibold text-slate-200">{editableHook || post.hook}</p>
                </div>

                <div className="space-y-2">
                  <span className="font-mono text-xs text-primary uppercase font-bold">Caption & Description</span>
                  <div className="space-y-3 text-sm leading-relaxed text-slate-200 whitespace-pre-line bg-white/5 p-5 rounded-2xl border border-white/10 font-sans">
                    {editableCaption || post.caption}
                  </div>
                </div>

                <div className="space-y-2">
                  <span className="font-mono text-xs text-primary uppercase font-bold">Hashtags</span>
                  <div className="flex flex-wrap gap-2">
                    {post.hashtags.map((tag) => (
                      <span
                        key={tag}
                        className="rounded-lg bg-white/5 border border-white/10 px-3 py-1 font-mono text-xs text-primary"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>

                {post.sourceUrl && (
                  <div className="space-y-1 pt-2 border-t border-white/10">
                    <span className="font-mono text-xs text-slate-400">Grounding Source</span>
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
        <div className="border-t border-white/10 bg-black/60 px-6 py-4 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onRegenerate(post.id)}
            disabled={editing}
            className="h-9 gap-1.5 text-xs text-slate-400 hover:text-white rounded-xl"
          >
            <RefreshCw className="size-3.5" /> Regenerate Post
          </Button>

          <div className="flex items-center gap-2.5">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              className="h-9 gap-1.5 text-xs rounded-xl border-white/15 bg-white/5 text-white hover:bg-white/10"
            >
              {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
              {copied ? "Copied!" : "Copy Post Text"}
            </Button>
            <Button
              size="sm"
              onClick={() => {
                toast.success("Post updated successfully!");
                onOpenChange(false);
              }}
              className="h-9 px-5 text-xs font-bold bg-primary text-black rounded-xl hover:bg-primary-hover shadow-ember"
            >
              Save & Close
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
