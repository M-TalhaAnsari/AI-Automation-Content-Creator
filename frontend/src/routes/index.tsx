import { useState } from "react";
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
  DEMO_MESSAGES,
  DEMO_SESSIONS,
  type ChatMessage,
  type GeneratedPost,
  type Session,
} from "@/components/aiflick/data";


export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AIFlick — AI content workspace" },
      {
        name: "description",
        content:
          "AIFlick turns a plain-language idea into platform-ready social posts, grounded in live signals from GitHub, Reddit, HackerNews and Google Trends.",
      },
      { property: "og:title", content: "AIFlick — AI content workspace" },
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

function Workspace() {
  const [authenticated, setAuthenticated] = useState(true);
  const [showAuthScreen, setShowAuthScreen] = useState(false);
  const [authForced, setAuthForced] = useState(false);

  const [sessions, setSessions] = useState<Session[]>(DEMO_SESSIONS);
  const [activeSessionId, setActiveSessionId] = useState<string | null>("s1");
  const [messages, setMessages] = useState<ChatMessage[]>(DEMO_MESSAGES);
  const [lastSnapshot, setLastSnapshot] = useState<ChatMessage[] | null>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [contextOpen, setContextOpen] = useState(true);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const [platform, setPlatform] = useState("auto");
  const [postCount, setPostCount] = useState(5);
  const [constraints, setConstraints] = useState(["no emojis", "technical tone"]);

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [retryCountdown, setRetryCountdown] = useState(0);
  const [guestMessagesLeft, setGuestMessagesLeft] = useState(3);

  const [activePost, setActivePost] = useState<{
    post: GeneratedPost;
    index: number;
  } | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPost, setEditingPost] = useState(false);
  const [regeneratingPostId, setRegeneratingPostId] = useState<string | null>(null);

  const activeTitle =
    sessions.find((s) => s.id === activeSessionId)?.title ?? "New chat";

  function updatePost(postId: string, updater: (post: GeneratedPost) => GeneratedPost) {
    setMessages((prev) =>
      prev.map((message) =>
        message.posts
          ? {
              ...message,
              posts: message.posts.map((p) => (p.id === postId ? updater(p) : p)),
            }
          : message,
      ),
    );
    setActivePost((current) =>
      current && current.post.id === postId
        ? { ...current, post: updater(current.post) }
        : current,
    );
  }

  function handleViewPost(post: GeneratedPost, index: number) {
    setActivePost({ post, index });
    setModalOpen(true);
  }

  function handleApplyEdit(postId: string, instruction: string) {
    setLastSnapshot(messages);
    setEditingPost(true);
    window.setTimeout(() => {
      updatePost(postId, (post) => ({
        ...post,
        hook:
          instruction.toLowerCase().includes("short") && post.hook.length > 48
            ? `${post.hook.slice(0, 46).trimEnd()}.`
            : post.hook,
        edits: [
          ...(post.edits ?? []),
          { id: crypto.randomUUID(), instruction, atLabel: "just now" },
        ],
      }));
      setEditingPost(false);
      toast("Post updated", { description: `“${instruction}”` });
    }, 1100);
  }

  function handleRegeneratePost(post: GeneratedPost) {
    setLastSnapshot(messages);
    setRegeneratingPostId(post.id);
    window.setTimeout(() => {
      updatePost(post.id, (p) => ({
        ...p,
        edits: [
          ...(p.edits ?? []),
          { id: crypto.randomUUID(), instruction: "regenerated", atLabel: "just now" },
        ],
      }));
      setRegeneratingPostId(null);
      toast("Regenerated with fresh signals");
    }, 1200);
  }


  function handleSend(text?: string) {
    const value = (text ?? input).trim();
    if (!value || sending) return;

    setLastSnapshot(messages);
    setMessages((prev) => [
      ...prev,
      { id: crypto.randomUUID(), role: "user", content: value },
    ]);
    setInput("");
    setError("");
    setSending(true);

    if (!authenticated) setGuestMessagesLeft((n) => Math.max(0, n - 1));

    window.setTimeout(() => {
      setSending(false);
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content:
            "Here's what I found. I pulled live items from **GitHub** and **HackerNews**, ranked them, and drafted the posts below. Ask me to change any of them and I'll rewrite in place.",
          posts: (DEMO_MESSAGES[1]?.posts ?? []).map((p) => ({
            ...p,
            id: crypto.randomUUID(),
            platform: platform === "auto" ? p.platform : platform,
            edits: [],
          })),
        },

      ]);
    }, 1400);
  }

  function handleNewChat() {
    setActiveSessionId(null);
    setMessages([]);
    setLastSnapshot(null);
    setError("");
  }

  function handleSelectSession(id: string) {
    setActiveSessionId(id);
    setMessages(id === "s1" ? DEMO_MESSAGES : []);
    setLastSnapshot(null);
    setError("");
  }

  function handleDeleteSession(id: string) {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (id === activeSessionId) handleNewChat();
    toast("Chat deleted");
  }

  function handleUndo() {
    if (!lastSnapshot) return;
    setMessages(lastSnapshot);
    setLastSnapshot(null);
    toast("Reverted to the previous state");
  }

  function handleClearChat() {
    setMessages([]);
    setLastSnapshot(null);
    toast("Chat cleared");
  }

  if (showAuthScreen) {
    return (
      <AuthScreen
        forced={authForced}
        onAuthenticated={() => {
          setAuthenticated(true);
          setShowAuthScreen(false);
          setAuthForced(false);
        }}
        onCancel={() => setShowAuthScreen(false)}
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
                  onSelectSession={handleSelectSession}
                  onNewChat={handleNewChat}
                  onDeleteSession={handleDeleteSession}
                  onSignIn={() => {
                    setAuthForced(false);
                    setShowAuthScreen(true);
                  }}
                  onLogout={() => {
                    setAuthenticated(false);
                    setSessions([]);
                    handleNewChat();
                  }}
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
                setAuthenticated(false);
                setSessions([]);
                handleNewChat();
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
              onRegeneratePost={(post) => handleRegeneratePost(post)}
              regeneratingPostId={regeneratingPostId}
            />

            <AnimatePresence initial={false}>
              {contextOpen && (
                <ContextPanel
                  platform={platform}
                  postCount={postCount}
                  constraints={constraints}
                  activeSources={["GitHub", "HackerNews", "Reddit"]}
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
            if (activePost) handleRegeneratePost(activePost.post);
            else void postId;
          }}
          editing={editingPost}
        />
      </div>

    </TooltipProvider>
  );
}
