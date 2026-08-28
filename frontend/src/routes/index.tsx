import { useEffect, useMemo, useRef, useState } from "react";
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
import { LandingPage } from "@/components/aiflick/landing-page";
import { SettingsModal } from "@/components/aiflick/settings-modal";
import {
  type ChatMessage,
  type GeneratedPost,
  type Session,
  DEMO_MESSAGES,
  DEMO_SESSIONS,
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
  generateImage,
  generateBatchImages,
  pollImageJob,
  getImageUrl,
  type MeResponse,
} from "@/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AIFlick — AI Social Content Workspace" },
      {
        name: "description",
        content:
          "AIFlick turns plain-language ideas into platform-ready social posts, grounded in live signals from GitHub, Reddit, HackerNews and Google Trends.",
      },
      { property: "og:title", content: "AIFlick — AI Social Content Workspace" },
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
  const [visualMood, setVisualMood] = useState("clean-informative");
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

  const [showLanding, setShowLanding] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [userTier, setUserTier] = useState<string>("free");
  const abortControllerRef = useRef<AbortController | null>(null);

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
        if (me.tier) setUserTier(me.tier);
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

  // Fetch Session History when Authenticated, or show demo sessions if guest
  useEffect(() => {
    if (authenticated) {
      refreshSessions();
    } else {
      setSessions(DEMO_SESSIONS);
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

  const allCurrentPosts = useMemo(() => {
    const list: GeneratedPost[] = [];
    for (const msg of messages) {
      if (msg.posts && msg.posts.length > 0) {
        list.push(...msg.posts);
      }
    }
    return list;
  }, [messages]);

  const currentPostIndex = activePost
    ? allCurrentPosts.findIndex((p) => p.id === activePost.post.id)
    : -1;
  const hasPreviousPost = currentPostIndex > 0;
  const hasNextPost = currentPostIndex !== -1 && currentPostIndex < allCurrentPosts.length - 1;

  function handlePreviousPost() {
    if (hasPreviousPost && allCurrentPosts[currentPostIndex - 1]) {
      const prev = allCurrentPosts[currentPostIndex - 1]!;
      setActivePost({ post: prev, index: currentPostIndex });
    }
  }

  function handleNextPost() {
    if (hasNextPost && allCurrentPosts[currentPostIndex + 1]) {
      const next = allCurrentPosts[currentPostIndex + 1]!;
      setActivePost({ post: next, index: currentPostIndex + 2 });
    }
  }

  function handleViewPost(post: GeneratedPost, index: number) {
    setActivePost({ post, index });
    setModalOpen(true);
  }

  function handleUpdatePost(updatedPost: GeneratedPost) {
    setActivePost((current) =>
      current && current.post.id === updatedPost.id
        ? { ...current, post: updatedPost }
        : current
    );
    setMessages((prev) =>
      prev.map((msg) => {
        if (!msg.posts) return msg;
        return {
          ...msg,
          posts: msg.posts.map((p) => (p.id === updatedPost.id ? updatedPost : p)),
        };
      })
    );
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

  async function handleGenerateImage(post: GeneratedPost, customPrompt?: string, index?: number) {
    if (!activeSessionId) {
      toast.error("Please start a session first");
      return;
    }

    const targetPostNumber = post.number ?? index ?? (activePost?.index ?? 1);

    // Optimistically mark post as generating
    setMessages((prev) =>
      prev.map((msg) => {
        if (!msg.posts) return msg;
        return {
          ...msg,
          posts: msg.posts.map((p) =>
            p.id === post.id ? { ...p, isGeneratingImage: true, imageError: undefined } : p
          ),
        };
      })
    );

    if (activePost && activePost.post.id === post.id) {
      setActivePost({
        ...activePost,
        post: { ...activePost.post, isGeneratingImage: true, imageError: undefined },
      });
    }

    try {
      const job = await generateImage({
        session_id: activeSessionId,
        post_number: targetPostNumber,
        post_data: {
          title: post.title,
          hook: post.hook,
          caption: post.caption,
          hashtags: post.hashtags,
          platform: post.platform,
          source_url: post.sourceUrl,
          source_label: post.sourceLabel,
        },
        platform: post.platform,
        custom_prompt: customPrompt,
      });

      toast.info("Visual generation started in background...", { duration: 3000 });

      // Poll until done
      const status = await pollImageJob(job.job_id);

      const resolvedUrl = getImageUrl(status.asset_id || status.image_url || "", true);

      // Update post state
      setMessages((prev) =>
        prev.map((msg) => {
          if (!msg.posts) return msg;
          return {
            ...msg,
            posts: msg.posts.map((p) =>
              p.id === post.id
                ? {
                    ...p,
                    isGeneratingImage: false,
                    imageUrl: resolvedUrl,
                    imageAssetId: status.asset_id || undefined,
                  }
                : p
            ),
          };
        })
      );

      if (activePost && activePost.post.id === post.id) {
        setActivePost({
          ...activePost,
          post: {
            ...activePost.post,
            isGeneratingImage: false,
            imageUrl: resolvedUrl,
            imageAssetId: status.asset_id || undefined,
          },
        });
      }

      toast.success("Visual generated successfully!");
    } catch (err: any) {
      toast.error(err?.message || "Failed to generate visual");
      setMessages((prev) =>
        prev.map((msg) => {
          if (!msg.posts) return msg;
          return {
            ...msg,
            posts: msg.posts.map((p) =>
              p.id === post.id
                ? { ...p, isGeneratingImage: false, imageError: err?.message || "Failed" }
                : p
            ),
          };
        })
      );
      if (activePost && activePost.post.id === post.id) {
        setActivePost({
          ...activePost,
          post: { ...activePost.post, isGeneratingImage: false },
        });
      }
    }
  }

  async function handleBatchGenerateImages(posts: GeneratedPost[]) {
    if (!activeSessionId) {
      toast.error("Please start a session first");
      return;
    }

    const ungenerated = posts.filter((p) => !p.imageUrl && !p.imageAssetId && !p.isGeneratingImage);
    if (ungenerated.length === 0) {
      toast("All posts already have generated visuals");
      return;
    }

    toast.info(`Generating ${ungenerated.length} visuals in parallel...`);

    // Run concurrently across worker pool
    await Promise.all(
      ungenerated.map((p, idx) => handleGenerateImage(p, undefined, p.number ?? idx + 1))
    );
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

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const chatResult = await sendChatAndWait(
        {
          message: value,
          session_id: activeSessionId,
          platform: platform !== "auto" ? platform : undefined,
          posts: postCount,
        },
        {},
        controller.signal
      );

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
      if (err?.code === "cancelled") {
        return;
      }
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
      abortControllerRef.current = null;
      setSending(false);
    }
  }

  function handleStop() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setSending(false);
    toast("Generation stopped by user");
  }

  function handleNewChat() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
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

    // If it's a demo session, immediately load demo messages without network failure
    if (id === "s1" || id === "s2" || id === "s3" || id === "s4" || id.startsWith("demo-")) {
      setMessages(DEMO_MESSAGES);
      return;
    }

    try {
      const sessionView = await getSession(id);
      if (!sessionView) {
        setMessages([]);
        return;
      }

      if (sessionView.last_platform) {
        setPlatform(sessionView.last_platform);
      }

      if (sessionView.active_constraints && Array.isArray(sessionView.active_constraints)) {
        const formattedConstraints = sessionView.active_constraints
          .map((c) =>
            typeof c === "string" ? c : c?.value || `${c?.type || ""}: ${c?.value || ""}`
          )
          .filter(Boolean);
        setConstraints(formattedConstraints);
      }

      const generatedPosts: GeneratedPost[] = [];
      if (Array.isArray(sessionView.last_generated_posts)) {
        sessionView.last_generated_posts.forEach((p, idx) => {
          if (p && typeof p === "object") {
            try {
              generatedPosts.push(
                rawPostToGeneratedPost(p, sessionView.last_platform || "instagram", idx + 1)
              );
            } catch {
              // Ignore corrupted post
            }
          }
        });
      }

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
      const history = Array.isArray(sessionView.message_history) ? sessionView.message_history : [];
      for (const entry of history) {
        try {
          const normalized = normalizeHistoryEntry(entry);
          if (normalized) {
            chatMessages.push(normalized);
          }
        } catch {
          // Ignore invalid entry
        }
      }

      if (generatedPosts.length > 0) {
        let lastAssistantIndex = -1;
        for (let i = chatMessages.length - 1; i >= 0; i--) {
          if (chatMessages[i]?.role === "assistant") {
            lastAssistantIndex = i;
            break;
          }
        }
        if (lastAssistantIndex !== -1 && chatMessages[lastAssistantIndex]) {
          chatMessages[lastAssistantIndex]!.posts = generatedPosts;
        } else if (sessionView.last_output) {
          chatMessages.push({
            id: `msg-${Date.now()}`,
            role: "assistant",
            content: sessionView.last_output,
            posts: generatedPosts,
          });
        } else {
          chatMessages.push({
            id: `msg-${Date.now()}`,
            role: "assistant",
            content: "Here are your generated posts:",
            posts: generatedPosts,
          });
        }
      }

      setMessages(chatMessages);
    } catch (err: any) {
      toast.error(err?.detail || err?.message || "Failed to load chat history");
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
      {/* ── Landing Page View ── */}
      {showLanding && (
        <LandingPage
          onGetStarted={() => setShowLanding(false)}
          onOpenSignIn={() => {
            setShowLanding(false);
            setAuthForced(false);
            setShowAuthScreen(true);
          }}
        />
      )}

      {/* ── Workspace Studio (hidden when landing is shown) ── */}
      {!showLanding && (
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
                  userName={user?.name}
                  userTier={userTier}
                  onSelectSession={handleSelectSession}
                  onNewChat={handleNewChat}
                  onDeleteSession={handleDeleteSession}
                  onSignIn={() => {
                    setAuthForced(false);
                    setShowAuthScreen(true);
                  }}
                  onLogout={handleLogout}
                  onCollapse={() => setSidebarOpen(false)}
                  onOpenSettings={() => setSettingsOpen(true)}
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
              userName={user?.name}
              userTier={userTier}
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
              onOpenSettings={() => {
                setSettingsOpen(true);
                setMobileNavOpen(false);
              }}
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
            onOpenSettings={() => setSettingsOpen(true)}
            onOpenLanding={() => setShowLanding(true)}
          />

          <div className="flex min-h-0 flex-1">
            <ChatWorkspace
              messages={messages}
              input={input}
              onInputChange={setInput}
              onSend={() => handleSend()}
              onStop={handleStop}
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
              onUpdatePost={handleUpdatePost}
              onRegeneratePost={(post, index) => handleRegeneratePost(post, index)}
              onGenerateImage={(post, index) => handleGenerateImage(post, undefined, index)}
              onBatchGenerateImages={handleBatchGenerateImages}
              regeneratingPostId={regeneratingPostId}
            />

            <AnimatePresence initial={false}>
              {contextOpen && (
                <ContextPanel
                  platform={platform}
                  postCount={postCount}
                  constraints={constraints}
                  activeSources={activeSources}
                  visualMood={visualMood}
                  onVisualMoodChange={setVisualMood}
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
          onUpdatePost={handleUpdatePost}
          onRegenerate={(postId) => {
            if (activePost) handleRegeneratePost(activePost.post, activePost.index);
            else void postId;
          }}
          onGenerateImage={(postId, customPrompt) => {
            if (activePost) handleGenerateImage(activePost.post, customPrompt, activePost.index);
            else void postId;
          }}
          editing={editingPost}
          hasPrevious={hasPreviousPost}
          hasNext={hasNextPost}
          onPrevious={handlePreviousPost}
          onNext={handleNextPost}
          totalPosts={allCurrentPosts.length}
        />
      </div>
      )}

      {/* ── Settings Modal (Always Mounted) ── */}
      <SettingsModal
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        currentTier={userTier}
        onTierChanged={(newTier) => setUserTier(newTier)}
      />
    </TooltipProvider>
  );
}
