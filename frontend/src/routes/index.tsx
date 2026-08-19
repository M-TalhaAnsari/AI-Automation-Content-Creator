import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AnimatePresence, motion } from "motion/react";
import { toast } from "sonner";

import { TooltipProvider } from "@/components/ui/tooltip";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { AppSidebar } from "@/components/aiflick/app-sidebar";
import { WorkspaceHeader } from "@/components/aiflick/workspace-header";
import { ChatWorkspace } from "@/components/aiflick/chat-workspace";
import { ContextPanel } from "@/components/aiflick/context-panel";
import { AuthScreen } from "@/components/aiflick/auth-screen";
import { PostModal } from "@/components/aiflick/post-modal";
import {
  type ChatMessage,
  type GeneratedPost,
  type Session,
  formatTimeAgo,
  normalizeHistoryEntry,
  rawPostToGeneratedPost,
} from "@/components/aiflick/data";
import {
  deleteSession,
  getMe,
  getSession,
  isLoggedIn,
  listSessions,
  logout,
  sendChatAndWait,
  type MeResponse,
} from "@/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "TrendForge — AI Content Workspace" },
      {
        name: "description",
        content:
          "TrendForge turns plain-language ideas into platform-ready social posts, grounded in live signals from GitHub, Reddit, HackerNews and Google Trends.",
      },
      { property: "og:title", content: "TrendForge — AI Content Workspace" },
      {
        property: "og:description",
        content:
          "Chat your idea, get platform-ready posts grounded in live trend data. Edit every post inside the conversation.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Workspace,
});

const POST_PRODUCING_ACTIONS = new Set([
  "run_new_request",
  "generate_more",
  "edit_existing",
  "targeted_refetch",
]);

function Workspace() {
  const [authChecking, setAuthChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<MeResponse | null>(null);
  const [showAuthScreen, setShowAuthScreen] = useState(false);
  const [authForced, setAuthForced] = useState(false);

  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastSnapshot, setLastSnapshot] = useState<ChatMessage[] | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const [platform, setPlatform] = useState("auto");
  const [postCount, setPostCount] = useState(5);
  const [constraints, setConstraints] = useState<string[]>([]);
  const [activeSources, setActiveSources] = useState<string[]>([
    "GitHub",
    "HackerNews",
    "Reddit",
  ]);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [retryCountdown, setRetryCountdown] = useState(0);
  const [guestMessagesLeft, setGuestMessagesLeft] = useState(3);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const [activePost, setActivePost] = useState<{
    post: GeneratedPost;
    index: number;
  } | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPost, setEditingPost] = useState(false);
  const [regeneratingPostId, setRegeneratingPostId] = useState<string | null>(null);

  // Initialize Authentication State on Load
  useEffect(() => {
    async function checkAuth() {
      if (!isLoggedIn()) {
        setAuthenticated(false);
        setUser(null);
        setAuthChecking(false);
        return;
      }
      try {
        const me = await getMe();
        setUser(me);
        setAuthenticated(true);
      } catch {
        logout();
        setAuthenticated(false);
        setUser(null);
      } finally {
        setAuthChecking(false);
      }
    }
    checkAuth();
  }, []);

  // Fetch Session History when Authenticated
  useEffect(() => {
    if (authenticated) {
      refreshSessions();
    } else {
      setSessions([]);
    }
  }, [authenticated]);

  // Handle Retry Countdown Timer for 429 Rate Limits
  useEffect(() => {
    if (retryCountdown <= 0) {
      if (countdownRef.current) clearInterval(countdownRef.current);
      return;
    }
    countdownRef.current = setInterval(() => {
      setRetryCountdown((s) => {
        if (s <= 1) {
          if (countdownRef.current) clearInterval(countdownRef.current);
          setError("");
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [retryCountdown]);

  async function refreshSessions() {
    if (!isLoggedIn()) return;
    try {
      const items = await listSessions();
      const mapped: Session[] = items.map((item) => ({
        id: item.session_id,
        title: item.title || "Untitled chat",
        updatedLabel: formatTimeAgo(item.last_active_at || item.created_at),
      }));
      setSessions(mapped);
    } catch (err: any) {
      if (err?.status === 401) {
        setAuthenticated(false);
        setUser(null);
        logout();
      }
    }
  }

  const activeTitle =
    sessions.find((s) => s.id === activeSessionId)?.title ?? "New chat";

  function handleViewPost(post: GeneratedPost, index: number) {
    setActivePost({ post, index });
    setModalOpen(true);
  }

  function handleApplyEdit(postId: string, instruction: string) {
    setEditingPost(true);
    const postIndex = activePost?.index ?? 1;
    setModalOpen(false);
    handleSend(`For post ${postIndex}: ${instruction}`);
    setEditingPost(false);
  }

  function handleRegeneratePost(post: GeneratedPost, index = 1) {
    setRegeneratingPostId(post.id);
    handleSend(`Please regenerate post ${index} with fresh signals and hook.`);
    setRegeneratingPostId(null);
  }

  async function handleSend(text?: string) {
    const value = (text ?? input).trim();
    if (!value || sending) return;

    setLastSnapshot(messages);
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", content: value },
    ]);
    setInput("");
    setError("");
    setSending(true);

    if (!authenticated) {
      setGuestMessagesLeft((n) => Math.max(0, n - 1));
    }

    try {
      const chatResult = await sendChatAndWait({
        message: value,
        session_id: activeSessionId,
        platform: platform !== "auto" ? platform : undefined,
        posts: postCount,
      });

      const nextSessionId = chatResult.session_id;
      setActiveSessionId(nextSessionId);

      // Fetch refreshed session details for latest posts, active constraints & sources
      let postsForMessage: GeneratedPost[] | undefined;
      try {
        const sessionView = await getSession(nextSessionId);
        if (sessionView.active_constraints) {
          const formattedConstraints = sessionView.active_constraints
            .map((c) =>
              typeof c === "string" ? c : c.value || `${c.type || ""}: ${c.value || ""}`
            )
            .filter(Boolean);
          setConstraints(formattedConstraints);
        }

        if (sessionView.last_platform && platform === "auto") {
          setPlatform(sessionView.last_platform);
        }

        if (
          POST_PRODUCING_ACTIONS.has(chatResult.action) &&
          sessionView.last_generated_posts &&
          sessionView.last_generated_posts.length > 0
        ) {
          postsForMessage = sessionView.last_generated_posts.map((p, idx) =>
            rawPostToGeneratedPost(p, sessionView.last_platform || platform, idx + 1)
          );

          // Extract active sources used
          const sourcesUsed = new Set<string>();
          postsForMessage.forEach((p) => {
            if (p.sourceLabel) sourcesUsed.add(p.sourceLabel);
          });
          if (sourcesUsed.size > 0) {
            setActiveSources(Array.from(sourcesUsed));
          }
        }
      } catch {
        // Non-fatal — reply text will still render
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: chatResult.reply || "Done.",
          posts: postsForMessage,
        },
      ]);

      if (authenticated) {
        refreshSessions();
      }
    } catch (err: any) {
      if (err?.code === "signup_required") {
        setAuthForced(true);
        setShowAuthScreen(true);
        // Remove optimistic user bubble
        setMessages((prev) => prev.slice(0, -1));
      } else if (err?.status === 429) {
        setError(`Rate limited — please try again in ${err.retryAfterSeconds || 10}s`);
        setRetryCountdown(err.retryAfterSeconds || 10);
      } else {
        setError(err?.detail || err?.message || "Failed to process request");
        if (err?.status === 401) {
          setAuthenticated(false);
          setUser(null);
        }
      }
    } finally {
      setSending(false);
    }
  }

  function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setConstraints([]);
    setLastSnapshot(null);
    setError("");
  }

  async function handleSelectSession(id: string) {
    setError("");
    setActiveSessionId(id);
    setLastSnapshot(null);
    try {
      const sessionView = await getSession(id);
      if (sessionView.last_platform) {
        setPlatform(sessionView.last_platform);
      }

      if (sessionView.active_constraints) {
        const formattedConstraints = sessionView.active_constraints
          .map((c) =>
            typeof c === "string" ? c : c.value || `${c.type || ""}: ${c.value || ""}`
          )
          .filter(Boolean);
        setConstraints(formattedConstraints);
      }

      const generatedPosts = (sessionView.last_generated_posts || []).map((p, idx) =>
        rawPostToGeneratedPost(p, sessionView.last_platform || "instagram", idx + 1)
      );

      if (generatedPosts.length > 0) {
        const sourcesUsed = new Set<string>();
        generatedPosts.forEach((p) => {
          if (p.sourceLabel) sourcesUsed.add(p.sourceLabel);
        });
        if (sourcesUsed.size > 0) {
          setActiveSources(Array.from(sourcesUsed));
        }
      }

      const chatMessages: ChatMessage[] = [];
      const history = sessionView.message_history || [];
      for (const entry of history) {
        const normalized = normalizeHistoryEntry(entry);
        if (normalized) {
          chatMessages.push(normalized);
        }
      }

      if (generatedPosts.length > 0) {
        const lastAssistantIndex = chatMessages.findLastIndex((m) => m.role === "assistant");
        if (lastAssistantIndex !== -1) {
          chatMessages[lastAssistantIndex].posts = generatedPosts;
        } else if (sessionView.last_output) {
          chatMessages.push({
            id: `msg-${Date.now()}`,
            role: "assistant",
            content: sessionView.last_output,
            posts: generatedPosts,
          });
        }
      }

      setMessages(chatMessages);
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to load session history");
    }
  }

  async function handleDeleteSession(id: string) {
    try {
      await deleteSession(id);
      setSessions((prev) => prev.filter((s) => s.id !== id));
      if (id === activeSessionId) {
        handleNewChat();
      }
      toast("Chat deleted");
    } catch (err: any) {
      toast.error(err?.detail || err?.message || "Failed to delete chat session");
    }
  }

  function handleUndo() {
    if (!lastSnapshot) return;
    setMessages(lastSnapshot);
    setLastSnapshot(null);
    handleSend("undo");
    toast("Reverted to the previous state");
  }

  async function handleClearChat() {
    if (activeSessionId) {
      try {
        await deleteSession(activeSessionId);
      } catch {
        // Continue clearing locally
      }
    }
    handleNewChat();
    if (authenticated) {
      refreshSessions();
    }
    toast("Chat cleared");
  }

  function handleLogout() {
    logout();
    setAuthenticated(false);
    setUser(null);
    setSessions([]);
    handleNewChat();
    toast("Logged out");
  }

  function handleAuthenticated() {
    setAuthenticated(true);
    setShowAuthScreen(false);
    setAuthForced(false);
    getMe().then((me) => setUser(me)).catch(() => {});
    refreshSessions();
    toast("Signed in successfully");
  }

  if (authChecking) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-background text-sm text-muted-foreground">
        Loading workspace…
      </div>
    );
  }

  if (showAuthScreen) {
    return (
      <AuthScreen
        forced={authForced}
        onAuthenticated={handleAuthenticated}
        onCancel={() => {
          setShowAuthScreen(false);
          setAuthForced(false);
        }}
      />
    );
  }

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex h-screen w-full overflow-hidden bg-background">
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.aside
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 264, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
              className="hidden shrink-0 overflow-hidden border-r border-border/70 md:block"
            >
              <div className="h-full w-[264px]">
                <AppSidebar
                  sessions={sessions}
                  activeSessionId={activeSessionId}
                  isGuest={!authenticated}
                  guestMessagesLeft={guestMessagesLeft}
                  userEmail={user?.email}
                  onSelectSession={handleSelectSession}
                  onNewChat={handleNewChat}
                  onDeleteSession={handleDeleteSession}
                  onSignIn={() => {
                    setAuthForced(false);
                    setShowAuthScreen(true);
                  }}
                  onLogout={handleLogout}
                  onCollapse={() => setSidebarOpen(false)}
                />
              </div>
            </motion.aside>
          )}
        </AnimatePresence>

        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent
            side="left"
            className="w-[286px] gap-0 border-border/70 bg-sidebar p-0 md:hidden"
          >
            <SheetTitle className="sr-only">Navigation</SheetTitle>
            <AppSidebar
              sessions={sessions}
              activeSessionId={activeSessionId}
              isGuest={!authenticated}
              guestMessagesLeft={guestMessagesLeft}
              userEmail={user?.email}
              onSelectSession={(id) => {
                handleSelectSession(id);
                setMobileNavOpen(false);
              }}
              onNewChat={() => {
                handleNewChat();
                setMobileNavOpen(false);
              }}
              onDeleteSession={handleDeleteSession}
              onSignIn={() => {
                setAuthForced(false);
                setShowAuthScreen(true);
                setMobileNavOpen(false);
              }}
              onLogout={() => {
                handleLogout();
                setMobileNavOpen(false);
              }}
              collapsible={false}
              onCollapse={() => setMobileNavOpen(false)}
            />
          </SheetContent>
        </Sheet>

        <div className="flex min-w-0 flex-1 flex-col">
          <WorkspaceHeader
            sidebarOpen={sidebarOpen}
            onOpenSidebar={() => setSidebarOpen(true)}
            onOpenMobileNav={() => setMobileNavOpen(true)}
            contextOpen={contextOpen}
            onToggleContext={() => setContextOpen((v) => !v)}
            platform={platform}
            onPlatformChange={setPlatform}
            postCount={postCount}
            onPostCountChange={setPostCount}
            constraints={constraints}
            onRemoveConstraint={(value) => {
              setConstraints((prev) => prev.filter((c) => c !== value));
              handleSend(`Please remove the constraint on "${value}".`);
            }}
            onAddConstraint={() =>
              toast("Tell the assistant your rule in chat", {
                description: 'e.g. "avoid emojis from now on"',
              })
            }
            onClearChat={handleClearChat}
            hasActiveSession={messages.length > 0}
            title={activeTitle}
          />

          <div className="flex min-h-0 flex-1">
            <ChatWorkspace
              messages={messages}
              input={input}
              onInputChange={setInput}
              onSend={() => handleSend()}
              sending={sending}
              error={error}
              retryCountdown={retryCountdown}
              canUndo={Boolean(lastSnapshot) && !sending}
              onUndo={handleUndo}
              onDismissError={() => {
                setError("");
                setRetryCountdown(0);
              }}
              onSuggestion={(prompt) => handleSend(prompt)}
              onViewPost={handleViewPost}
              onEditPost={handleViewPost}
              onRegeneratePost={(post, index) => handleRegeneratePost(post, index)}
              regeneratingPostId={regeneratingPostId}
            />

            <AnimatePresence initial={false}>
              {contextOpen && (
                <ContextPanel
                  platform={platform}
                  postCount={postCount}
                  constraints={constraints}
                  activeSources={activeSources}
                />
              )}
            </AnimatePresence>
          </div>
        </div>

        <PostModal
          post={activePost?.post ?? null}
          index={activePost?.index ?? 1}
          open={modalOpen}
          onOpenChange={setModalOpen}
          onApplyEdit={handleApplyEdit}
          onRegenerate={(postId) => {
            if (activePost) handleRegeneratePost(activePost.post, activePost.index);
            else void postId;
          }}
          editing={editingPost}
        />
      </div>
    </TooltipProvider>
  );
}
