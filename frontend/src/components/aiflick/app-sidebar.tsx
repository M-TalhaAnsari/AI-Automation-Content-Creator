import { Link } from "@tanstack/react-router";
import { motion } from "motion/react";
import {
  MessageSquarePlus,
  Search,
  Settings,
  MoreHorizontal,
  Trash2,
  PanelLeftClose,
  Flame,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Session } from "./data";

type Props = {
  sessions: Session[];
  activeSessionId: string | null;
  isGuest: boolean;
  guestMessagesLeft: number;
  userEmail?: string | null;
  userName?: string | null;
  userTier?: string | null;
  collapsible?: boolean;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  onSignIn: () => void;
  onLogout: () => void;
  onCollapse: () => void;
};

export function AppSidebar({
  sessions,
  activeSessionId,
  isGuest,
  guestMessagesLeft,
  userEmail,
  userName,
  userTier,
  collapsible = true,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  onSignIn,
  onLogout,
  onCollapse,
}: Props) {
  return (
    <div className="flex h-full flex-col gap-4 bg-sidebar px-3 pt-4 pb-3">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2 px-1">
        <Link to="/" className="flex min-w-0 items-center gap-2.5">
          <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
            <Flame className="size-4" />
          </span>
          <span className="truncate font-mono text-sm tracking-tight text-foreground">
            AIFlick
          </span>
        </Link>
        {collapsible && (
          <Button
            variant="ghost"
            size="icon"
            onClick={onCollapse}
            aria-label="Collapse sidebar"
            className="size-8 shrink-0 text-muted-foreground hover:text-foreground"
          >
            <PanelLeftClose className="size-4" />
          </Button>
        )}

      </div>

      <div className="space-y-2">
        <Button
          onClick={onNewChat}
          className="w-full justify-start gap-2 rounded-xl bg-primary text-primary-foreground shadow-ember hover:bg-primary-hover"
        >
          <MessageSquarePlus className="size-4" />
          New chat
        </Button>
        <button
          type="button"
          className="flex w-full items-center gap-2 rounded-xl border border-border/70 bg-surface-raised/40 px-3 py-2 text-left text-sm text-muted-foreground transition-colors hover:border-border-strong hover:text-foreground"
        >
          <Search className="size-4 shrink-0" />
          <span className="min-w-0 flex-1 truncate">Search chats</span>
          <kbd className="shrink-0 rounded-md border border-border/70 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            ⌘K
          </kbd>
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto scroll-quiet">
        <p className="label-mono px-2 pb-2">History</p>
        {isGuest ? (
          <p className="rounded-xl border border-dashed border-border/70 px-3 py-6 text-center text-xs leading-relaxed text-muted-foreground">
            Guest chats aren't saved.
            <br />
            Sign in to keep your history.
          </p>
        ) : (
          <ul className="space-y-0.5">
            {sessions.map((session) => {
              const active = session.id === activeSessionId;
              return (
                <li key={session.id} className="group/item relative">
                  <button
                    type="button"
                    onClick={() => onSelectSession(session.id)}
                    className={cn(
                      "w-full rounded-lg px-2.5 py-2 pr-9 text-left text-sm transition-colors",
                      active
                        ? "bg-sidebar-accent text-foreground"
                        : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground",
                    )}
                  >
                    <span className="block truncate">{session.title}</span>
                    <span className="mt-0.5 block truncate font-mono text-[10px] text-muted-foreground/80">
                      {session.updatedLabel}
                    </span>
                  </button>
                  {active && (
                    <motion.span
                      layoutId="session-marker"
                      className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-primary"
                    />
                  )}
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`Options for ${session.title}`}
                        className="absolute top-1.5 right-1 size-7 text-muted-foreground opacity-0 transition-opacity group-hover/item:opacity-100 focus-visible:opacity-100"
                      >
                        <MoreHorizontal className="size-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-40">
                      <DropdownMenuItem
                        onClick={() => onDeleteSession(session.id)}
                        className="text-destructive focus:text-destructive"
                      >
                        <Trash2 className="size-4" />
                        Delete chat
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="space-y-2 border-t border-border/70 pt-3">
        {isGuest ? (
          <div className="rounded-xl bg-surface-raised/60 px-3 py-2.5">
            <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-2">
              <p className="min-w-0 truncate font-mono text-[11px] text-muted-foreground">
                Guest · {guestMessagesLeft} left
              </p>
              <button
                type="button"
                onClick={onSignIn}
                className="shrink-0 text-xs font-medium text-primary hover:text-primary-hover"
              >
                Sign in
              </button>
            </div>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-border/70">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${(guestMessagesLeft / 3) * 100}%` }}
              />
            </div>
          </div>
        ) : (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2.5 rounded-xl px-2 py-2 text-left transition-colors hover:bg-sidebar-accent/60"
              >
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-secondary font-mono text-xs text-foreground uppercase">
                  {userEmail ? userEmail.slice(0, 2) : "TF"}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm text-foreground">
                    {userName || userEmail || "Workspace"}
                  </span>
                  <span className="block truncate font-mono text-[10px] text-primary/90 font-medium">
                    {userTier === "agency"
                      ? "Agency Studio"
                      : userTier === "creator"
                      ? "Creator Pro"
                      : "Free Explorer"}
                  </span>
                </span>
                <Settings className="size-4 shrink-0 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" side="top" className="w-52">
              <DropdownMenuItem disabled>
                <Settings className="size-4" />
                Settings
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={onLogout}>Log out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
      </div>
    </div>
  );
}
