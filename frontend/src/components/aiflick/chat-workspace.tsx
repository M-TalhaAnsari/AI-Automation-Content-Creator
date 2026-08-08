import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowUp,
  CornerDownLeft,
  Flame,
  AlertTriangle,
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
  sending: boolean;
  error: string;
  retryCountdown: number;
  canUndo: boolean;
  onUndo: () => void;
  onDismissError: () => void;
  onSuggestion: (prompt: string) => void;
  onViewPost: (post: GeneratedPost, index: number) => void;
  onEditPost: (post: GeneratedPost, index: number) => void;
  onRegeneratePost: (post: GeneratedPost, index: number) => void;
  regeneratingPostId: string | null;
};


export function ChatWorkspace({
  messages,
  input,
  onInputChange,
  onSend,
  sending,
  error,
  retryCountdown,
  canUndo,
  onUndo,
  onDismissError,
  onSuggestion,
  onViewPost,
  onEditPost,
  onRegeneratePost,
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
    <div className="relative flex min-h-0 flex-1 flex-col">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-64 ambient-glow" />

      <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet">
        <div className="mx-auto w-full max-w-3xl px-4 pt-10 pb-6 sm:px-6">
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
                  regeneratingPostId={regeneratingPostId}
                />

              ))}
              {sending && <ThinkingRow />}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-border/70 bg-background/85 backdrop-blur-xl">
        <div className="mx-auto w-full max-w-3xl px-4 py-4 sm:px-6">
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

          <div className="rounded-2xl border border-border/80 bg-surface-raised/60 p-2 shadow-panel transition-colors focus-within:border-primary/50">
            <Textarea
              ref={inputRef}
              value={input}
              onChange={(e) => onInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  onSend();
                }
              }}
              rows={2}
              placeholder="Describe the posts you want — e.g. 5 LinkedIn posts about AI agents"
              className="max-h-40 min-h-0 resize-none border-0 bg-transparent px-2.5 py-2 text-sm shadow-none focus-visible:ring-0 dark:bg-transparent"
            />
            <div className="flex items-center justify-between gap-2 px-1 pt-1">
              <div className="flex min-w-0 items-center gap-2">
                {canUndo && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={onUndo}
                    className="h-7 gap-1.5 px-2 text-xs text-muted-foreground hover:text-foreground"
                  >
                    <Undo2 className="size-3.5" />
                    Undo last
                  </Button>
                )}
                <span className="hidden items-center gap-1 font-mono text-[10px] text-muted-foreground sm:flex">
                  <CornerDownLeft className="size-3" />
                  to send · shift + enter for newline
                </span>
              </div>
              <Button
                size="icon"
                onClick={onSend}
                disabled={sending || input.trim().length === 0}
                aria-label="Send message"
                className="size-8 shrink-0 rounded-lg bg-primary text-primary-foreground hover:bg-primary-hover disabled:opacity-40"
              >
                <ArrowUp className="size-4" />
              </Button>
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
      <span className="grid size-11 place-items-center rounded-2xl bg-primary/12 text-primary ring-1 ring-primary/25">
        <Flame className="size-5" />
      </span>
      <h2 className="mt-5 text-2xl tracking-tight text-foreground sm:text-[28px]">
        What should we make today?
      </h2>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-muted-foreground">
        Describe an idea in plain language. AIFlick pulls live signals from GitHub,
        Reddit, HackerNews, Google Trends and more, then writes posts you can edit right in
        the conversation.
      </p>

      <div className="mt-7 grid gap-2 sm:grid-cols-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt.title}
            type="button"
            onClick={() => onSuggestion(prompt.title)}
            className="group rounded-xl border border-border/70 bg-surface-raised/40 px-3.5 py-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:bg-surface-raised/70"
          >
            <span className="block text-sm leading-snug text-foreground">
              {prompt.title}
            </span>
            <span className="mt-1.5 block font-mono text-[10px] text-muted-foreground">
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
  onRegeneratePost: (post: GeneratedPost, index: number) => void;
  regeneratingPostId: string | null;
};

function MessageRow({
  message,
  onViewPost,
  onEditPost,
  onRegeneratePost,
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
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm leading-relaxed text-primary-foreground shadow-ember">
          {message.content}
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="grid grid-cols-[auto_minmax(0,1fr)] gap-3"
    >
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-secondary text-primary">
        <Flame className="size-3.5" />
      </span>
      <div className="min-w-0">
        <div className="text-sm text-foreground/90">
          <Markdown content={message.content} />
        </div>
        {message.posts && message.posts.length > 0 && (
          <div className="mt-4 grid gap-2.5">
            {message.posts.map((post, i) => (
              <PostCard
                key={post.id}
                post={post}
                index={i + 1}
                regenerating={regeneratingPostId === post.id}
                onView={() => onViewPost(post, i + 1)}
                onEdit={() => onEditPost(post, i + 1)}
                onRegenerate={() => onRegeneratePost(post, i + 1)}
              />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}


function ThinkingRow() {
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)] gap-3">
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-secondary text-primary">
        <Flame className="size-3.5 animate-pulse" />
      </span>
      <div className="min-w-0 space-y-2 pt-1">
        <p className="text-sm text-muted-foreground">
          <span className="animate-pulse">Fetching live signals…</span>
        </p>
        <div className="space-y-1.5">
          {["w-4/5", "w-3/5", "w-2/3"].map((w) => (
            <div
              key={w}
              className={cn("h-2.5 animate-pulse rounded-full bg-secondary", w)}
            />
          ))}
        </div>
        <div className="grid gap-2.5 pt-2">
          {[0, 1].map((i) => (
            <PostCardSkeleton key={i} index={i} />
          ))}
        </div>
      </div>
    </div>

  );
}
