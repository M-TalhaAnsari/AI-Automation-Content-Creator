import {
  PanelLeftOpen,
  PanelRight,
  Hash,
  Layers,
  Trash2,
  Plus,
  X,
  Menu,
} from "lucide-react";


import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { PLATFORMS, POST_COUNTS } from "./data";

type Props = {
  sidebarOpen: boolean;
  onOpenSidebar: () => void;
  onOpenMobileNav: () => void;
  contextOpen: boolean;
  onToggleContext: () => void;
  platform: string;
  onPlatformChange: (value: string) => void;
  postCount: number;
  onPostCountChange: (value: number) => void;
  constraints: string[];
  onRemoveConstraint: (value: string) => void;
  onAddConstraint: () => void;
  onClearChat: () => void;
  hasActiveSession: boolean;
  title: string;
};

export function WorkspaceHeader({
  sidebarOpen,
  onOpenSidebar,
  onOpenMobileNav,
  contextOpen,
  onToggleContext,
  platform,
  onPlatformChange,
  postCount,
  onPostCountChange,
  constraints,
  onRemoveConstraint,
  onAddConstraint,
  onClearChat,
  hasActiveSession,
  title,
}: Props) {
  return (
    <header className="sticky top-0 z-20 border-b border-border/70 bg-background/85 backdrop-blur-xl">
      <div className="flex items-center gap-2 px-3 py-2.5 sm:gap-3 sm:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <Button
            variant="ghost"
            size="icon"
            onClick={onOpenMobileNav}
            aria-label="Open menu"
            className="size-8 shrink-0 text-muted-foreground hover:text-foreground md:hidden"
          >
            <Menu className="size-4" />
          </Button>
          {!sidebarOpen && (
            <Button
              variant="ghost"
              size="icon"
              onClick={onOpenSidebar}
              aria-label="Open sidebar"
              className="hidden size-8 shrink-0 text-muted-foreground hover:text-foreground md:inline-flex"
            >
              <PanelLeftOpen className="size-4" />
            </Button>
          )}
          <h1 className="truncate text-sm font-medium tracking-tight text-foreground">
            {title}
          </h1>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">

          <Select value={platform} onValueChange={onPlatformChange}>
            <SelectTrigger
              aria-label="Platform"
              className="h-8 w-auto gap-1.5 rounded-lg border-border/70 bg-surface-raised/50 px-2.5 text-xs data-[placeholder]:text-muted-foreground"
            >
              <Layers className="size-3.5 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PLATFORMS.map((p) => (
                <SelectItem key={p.value} value={p.value} className="text-xs">
                  {p.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select
            value={String(postCount)}
            onValueChange={(v) => onPostCountChange(Number(v))}
          >
            <SelectTrigger
              aria-label="Number of posts"
              className="h-8 w-auto gap-1.5 rounded-lg border-border/70 bg-surface-raised/50 px-2.5 text-xs"
            >
              <Hash className="size-3.5 text-muted-foreground" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {POST_COUNTS.map((n) => (
                <SelectItem key={n} value={String(n)} className="text-xs">
                  {n} posts
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <span className="mx-0.5 hidden h-5 w-px bg-border/70 sm:block" />

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClearChat}
                disabled={!hasActiveSession}
                aria-label="Clear chat"
                className="size-8 text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Clear chat</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggleContext}
                aria-label="Toggle context panel"
                aria-pressed={contextOpen}
                className={cn(
                  "hidden size-8 text-muted-foreground hover:text-foreground lg:inline-flex",
                  contextOpen && "bg-secondary text-foreground",
                )}
              >
                <PanelRight className="size-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Context panel</TooltipContent>
          </Tooltip>
        </div>
      </div>

      <div className="flex items-center gap-1.5 overflow-x-auto border-t border-border/50 px-3 py-2 scroll-quiet sm:flex-wrap sm:px-6">
        <span className="label-mono shrink-0 pr-1">Constraints</span>
        {constraints.map((c) => (
          <span
            key={c}
            className="group inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border/70 bg-surface-raised/60 py-1 pr-1 pl-2.5 text-xs text-foreground"
          >
            {c}
            <button
              type="button"
              onClick={() => onRemoveConstraint(c)}
              aria-label={`Remove constraint ${c}`}
              className="grid size-4 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-secondary hover:text-destructive"
            >
              <X className="size-3" />
            </button>
          </span>
        ))}
        <button
          type="button"
          onClick={onAddConstraint}
          className="inline-flex shrink-0 items-center gap-1 rounded-full border border-dashed border-border/70 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/60 hover:text-primary"
        >
          <Plus className="size-3" />
          Add
        </button>
      </div>
    </header>
  );
}
