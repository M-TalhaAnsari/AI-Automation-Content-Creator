import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowUp,
  CornerDownLeft,
  Flame,
  AlertTriangle,
  Sparkles,
  Square,
  Undo2,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Markdown } from "./markdown";
import { PostCard, PostCardSkeleton } from "./post-card";
import { SUGGESTED_PROMPTS, type ChatMessage, type GeneratedPost } from "./data";

type Props = {
  messages: ChatMessage[];
  input: string;
  onInputChange: (value: string) => void;
  onSend: () => void;
  onStop?: () => void;
  sending: boolean;
  error: string;
  retryCountdown: number;
  canUndo: boolean;
  onUndo: () => void;
  onDismissError: () => void;
  onSuggestion: (prompt: string) => void;
  onViewPost: (post: GeneratedPost, index: number) => void;
  onEditPost: (post: GeneratedPost, index: number) => void;
  onUpdatePost?: (updatedPost: GeneratedPost) => void;
  onRegeneratePost: (post: GeneratedPost, index: number) => void;
  onGenerateImage?: (post: GeneratedPost, index: number) => void;
  onBatchGenerateImages?: (posts: GeneratedPost[]) => void;
  regeneratingPostId: string | null;
};

export function ChatWorkspace({
  messages,
  input,
  onInputChange,
  onSend,
  onStop,
  sending,
  error,
  retryCountdown,
  canUndo,
  onUndo,
  onDismissError,
  onSuggestion,
  onViewPost,
  onEditPost,
  onUpdatePost,
  onRegeneratePost,
  onGenerateImage,
  onBatchGenerateImages,
  regeneratingPostId,
}: Props) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const isEmpty = messages.length === 0;

  useEffect(() => {
    inputRef.current?.focus();
  }, [sending, messages.length]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, sending]);

  return (
    <div className="relative flex min-h-0 flex-1 flex-col bg-[#07080B] text-foreground selection:bg-primary/30">
      {/* Fluid ambient background glow */}
      <div className="pointer-events-none absolute inset-0 overflow-hidden z-0">
        <div
          className="absolute -top-[10%] left-1/2 -translate-x-1/2 w-[850px] h-[450px] rounded-full blur-[140px] opacity-25"
          style={{
            background:
              "radial-gradient(ellipse at center, rgba(249, 115, 22, 0.4), rgba(56, 189, 248, 0.25), transparent 70%)",
          }}
        />
        <div
          className="absolute bottom-0 right-0 w-[500px] h-[350px] rounded-full blur-[150px] opacity-15"
          style={{
            background:
              "radial-gradient(circle, rgba(168, 85, 247, 0.3), rgba(14, 165, 233, 0.2), transparent 70%)",
          }}
        />
      </div>

      <div className="relative z-10 min-h-0 flex-1 overflow-y-auto scroll-quiet">
        <div className="mx-auto w-full max-w-5xl px-4 pt-10 pb-6 sm:px-6">
          {isEmpty ? (
            <EmptyState onSuggestion={onSuggestion} />
          ) : (
            <div className="space-y-8">
              {messages.map((message) => (
                <MessageRow
                  key={message.id}
                  message={message}
                  onViewPost={onViewPost}
                  onEditPost={onEditPost}
                  onRegeneratePost={onRegeneratePost}
                  onGenerateImage={onGenerateImage}
                  onBatchGenerateImages={onBatchGenerateImages}
                  regeneratingPostId={regeneratingPostId}
                />
              ))}
              {sending && <ThinkingRow />}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="relative z-10 border-t border-white/10 bg-black/70 backdrop-blur-2xl">
        <div className="mx-auto w-full max-w-5xl px-4 py-4 sm:px-6">
          <AnimatePresence initial={false}>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                className="mb-3 grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2.5"
              >
                <AlertTriangle className="size-4 shrink-0 text-destructive" />
                <p className="min-w-0 text-xs text-foreground">
                  {error}
                  {retryCountdown > 0 && (
                    <span className="font-mono text-muted-foreground">
                      {" "}
                      · retry in {retryCountdown}s
                    </span>
                  )}
                </p>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onDismissError}
                  className="h-7 shrink-0 px-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  Dismiss
                </Button>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="rounded-2xl border border-white/15 bg-white/[0.04] p-2.5 shadow-2xl backdrop-blur-xl transition-all focus-within:border-primary/60 focus-within:bg-white/[0.06]">
            <Textarea
              ref={inputRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  if (!sending && input.trim().length > 0) onSend();
                }
              }}
              rows={2}
              placeholder="Describe the content you want to create — e.g. 5 viral LinkedIn carousel slides about AI coding agents"
              className="max-h-44 min-h-0 resize-none border-0 bg-transparent px-3 py-2 text-sm text-white placeholder:text-slate-500 shadow-none focus-visible:ring-0 leading-relaxed"
            />
            <div className="flex items-center justify-between gap-2 px-1 pt-1.5 border-t border-white/5">
              <div className="flex min-w-0 items-center gap-2">
                {canUndo && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onUndo}
                    className="h-7 gap-1.5 px-2.5 text-xs text-slate-400 hover:text-white"
                  >
                    <Undo2 className="size-3.5" />
                    Undo last
                  </Button>
                )}
                <span className="hidden items-center gap-1 font-mono text-[10px] text-slate-500 sm:flex">
                  <CornerDownLeft className="size-3" />
                  to send · shift + enter for newline
                </span>
              </div>

              <div className="flex items-center gap-2">
                {sending ? (
                  <Button
                    size="sm"
                    onClick={onStop}
                    variant="destructive"
                    className="h-8 gap-1.5 rounded-xl px-3.5 text-xs font-bold shadow-md bg-destructive/90 hover:bg-destructive text-white animate-pulse"
                    title="Stop generation"
                  >
                    <Square className="size-3 fill-current" /> Stop
                  </Button>
                ) : (
                  <Button
                    size="icon"
                    onClick={onSend}
                    disabled={input.trim().length === 0}
                    aria-label="Send message"
                    className="size-8 shrink-0 rounded-xl bg-primary text-black font-bold hover:bg-primary-hover shadow-ember disabled:opacity-30 transition-all"
                  >
                    <ArrowUp className="size-4" />
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onSuggestion }: { onSuggestion: (prompt: string) => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="pt-10 pb-4"
    >
      <div className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-primary to-amber-400 shadow-ember ring-1 ring-primary/40">
        <span className="text-base font-black text-black">△</span>
      </div>
      <h2 className="mt-5 text-2xl tracking-tight text-white sm:text-[30px] font-bold">
        What should we create today?
      </h2>
      <p className="mt-2 max-w-lg text-sm leading-relaxed text-slate-400">
        Describe an idea in plain language. AIFlick pulls live signals from GitHub,
        Reddit, HackerNews, YouTube, and Google Trends, then composes viral posts and studio visuals
        you can edit directly in the workspace.
      </p>

      <div className="mt-8 grid gap-2.5 sm:grid-cols-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt.title}
            type="button"
            onClick={() => onSuggestion(prompt.title)}
            className="group rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-left backdrop-blur-md transition-all hover:-translate-y-0.5 hover:border-primary/50 hover:bg-white/[0.06] shadow-sm"
          >
            <span className="block text-sm font-medium leading-snug text-white group-hover:text-primary transition-colors">
              {prompt.title}
            </span>
            <span className="mt-2 block font-mono text-[11px] text-slate-400">
              {prompt.hint}
            </span>
          </button>
        ))}
      </div>
    </motion.div>
  );
}

type RowProps = {
  message: ChatMessage;
  onViewPost: (post: GeneratedPost, index: number) => void;
  onEditPost: (post: GeneratedPost, index: number) => void;
  onUpdatePost?: (updatedPost: GeneratedPost) => void;
  onRegeneratePost: (post: GeneratedPost, index: number) => void;
  onGenerateImage?: (post: GeneratedPost, index: number) => void;
  onBatchGenerateImages?: (posts: GeneratedPost[]) => void;
  regeneratingPostId: string | null;
};

function MessageRow({
  message,
  onViewPost,
  onEditPost,
  onUpdatePost,
  onRegeneratePost,
  onGenerateImage,
  onBatchGenerateImages,
  regeneratingPostId,
}: RowProps) {
  if (message.role === "user") {
    return (
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="flex justify-end"
      >
        <div className="max-w-[85%] rounded-3xl rounded-br-md bg-primary px-5 py-3 text-sm font-medium leading-relaxed text-black shadow-ember">
          {message.content}
        </div>
      </motion.div>
    );
  }

  const hasPosts = message.posts && message.posts.length > 0;
  const anyPostMissingImage = hasPosts && message.posts?.some((p) => !p.imageUrl && !p.imageAssetId);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="grid grid-cols-[auto_minmax(0,1fr)] gap-3.5"
    >
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-amber-400 shadow-ember ring-1 ring-primary/40">
        <span className="text-[11px] font-black text-black">△</span>
      </div>
      <div className="min-w-0">
        <div className="text-[15px] leading-relaxed text-slate-200">
          <Markdown content={message.content} />
        </div>
        {hasPosts && (
          <div className="mt-5 space-y-3.5">
            {/* Batch Action Bar */}
            {onBatchGenerateImages && (
              <div className="flex items-center justify-between gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-2.5 backdrop-blur-md">
                <span className="text-xs text-slate-400 font-mono">
                  ✨ {message.posts?.length} platform-ready posts generated
                </span>
                {anyPostMissingImage && (
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onBatchGenerateImages(message.posts!)}
                    className="h-8 gap-1.5 rounded-xl px-3 text-xs font-semibold text-primary hover:bg-primary/10 hover:text-white"
                  >
                    <Sparkles className="size-3.5" />
                    Generate All Visuals
                  </Button>
                )}
              </div>
            )}

            <div className="grid gap-3.5 grid-cols-2">
              {message.posts!.map((post, i) => (
                <PostCard
                  key={post.id}
                  post={post}
                  index={i + 1}
                  regenerating={regeneratingPostId === post.id}
                  onView={() => onViewPost(post, i + 1)}
                  onEdit={() => onEditPost(post, i + 1)}
                  onUpdatePost={onUpdatePost}
                  onRegenerate={() => onRegeneratePost(post, i + 1)}
                  onGenerateImage={onGenerateImage ? () => onGenerateImage(post, i + 1) : undefined}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  );
}

function ThinkingRow() {
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-3.5">
      <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-amber-400 shadow-ember ring-1 ring-primary/40 animate-pulse">
        <span className="text-[11px] font-black text-black">△</span>
      </div>
      <div className="min-w-0 space-y-2.5 pt-1">
        <p className="text-sm text-primary font-mono font-medium">
          <span className="animate-pulse">Fetching live signals and composing posts…</span>
        </p>
        <div className="space-y-1.5">
          {["w-4/5", "w-3/5", "w-2/3"].map((w) => (
            <div
              key={w}
              className={cn("h-2.5 animate-pulse rounded-full bg-white/10", w)}
            />
          ))}
        </div>
        <div className="grid gap-3 pt-2 sm:grid-cols-2">
          {[0, 1].map((i) => (
            <PostCardSkeleton key={i} index={i} />
          ))}
        </div>
      </div>
    </div>
  );
}
