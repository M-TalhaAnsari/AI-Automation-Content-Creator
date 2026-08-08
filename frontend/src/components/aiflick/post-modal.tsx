import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  ArrowUp,
  Check,
  Copy,
  ExternalLink,
  History,
  Loader2,
  RefreshCw,
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
import type { GeneratedPost } from "./data";

const QUICK_EDITS = [
  "Make the hook punchier",
  "Shorten the caption",
  "More technical",
  "Swap the hashtags",
];

type Props = {
  post: GeneratedPost | null;
  index: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onApplyEdit: (postId: string, instruction: string) => void;
  onRegenerate: (postId: string) => void;
  editing: boolean;
};

export function PostModal({
  post,
  index,
  open,
  onOpenChange,
  onApplyEdit,
  onRegenerate,
  editing,
}: Props) {
  const [instruction, setInstruction] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (open) setInstruction("");
  }, [open, post?.id]);

  if (!post) return null;

  function submit() {
    const value = instruction.trim();
    if (!value || !post) return;
    onApplyEdit(post.id, value);
    setInstruction("");
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

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="flex max-h-[92vh] flex-col gap-0 overflow-hidden rounded-2xl border-border/70 bg-surface-raised/95 p-0 shadow-panel backdrop-blur-xl sm:max-h-[88vh] sm:max-w-2xl"
      >
        <DialogHeader className="space-y-3 border-b border-border/60 px-4 pt-5 pb-4 text-left sm:px-6 sm:pt-6 sm:pb-5">
          <div className="flex items-center gap-2">
            <PlatformBadge platform={post.platform} />
            <span className="label-mono text-muted-foreground">Post {index}</span>
          </div>
          <DialogTitle className="pr-8 text-lg leading-snug tracking-tight sm:text-xl">
            {post.title}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Full generated post with hook, caption, hashtags and source. Edit it by
            describing the change.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet px-4 py-5 sm:px-6">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={`${post.id}-${post.edits?.length ?? 0}`}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }}
              className="space-y-5"
            >
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
          </AnimatePresence>

          {post.edits && post.edits.length > 0 && (
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
                  submit();
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
                  onClick={submit}
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
