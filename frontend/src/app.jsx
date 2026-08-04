import { useEffect, useRef, useState } from 'react'
import * as api from './api/client'
import AuthScreen from './components/AuthScreen'
import Sidebar from './components/Sidebar'
import ChatWindow from './components/ChatWindow'
import ChatToolbar from './components/ChatToolbar'
import PostModal from './components/PostModal'
import './styles.css'

// Confirmed against conversation/orchestrator.py: message_history entries
// are {role: "user"|"assistant"|"tool", content, ...}. "tool" entries are
// internal dispatch bookkeeping ("dispatched:action_name") -- never shown.
function normalizeHistoryEntry(entry) {
  if (!entry || typeof entry !== 'object') return null
  if (entry.role === 'tool') return null
  if (!entry.content) return null
  return { role: entry.role === 'user' ? 'user' : 'assistant', content: entry.content }
}

const POST_PRODUCING_ACTIONS = ['run_new_request', 'edit_existing', 'targeted_refetch']

export default function App() {
  const [authChecking, setAuthChecking] = useState(true)
  const [authenticated, setAuthenticated] = useState(false)
  // Phase 8: guests can chat before ever logging in. showAuthScreen is a
  // separate flag from `authenticated` -- it's true either because the
  // trial limit was hit (forced, no dismiss) or because the guest chose
  // to log in early (dismissible via "Continue as guest").
  const [showAuthScreen, setShowAuthScreen] = useState(false)
  const [authScreenForced, setAuthScreenForced] = useState(false)
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [selectedPost, setSelectedPost] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [retryCountdown, setRetryCountdown] = useState(0)
  const [platform, setPlatform] = useState('')
  const [posts, setPosts] = useState(5)
  const [constraints, setConstraints] = useState([])
  const countdownRef = useRef(null)

  useEffect(() => {
    async function checkAuth() {
      if (!api.isLoggedIn()) {
        setAuthChecking(false)
        return
      }
      try {
        await api.getMe()
        setAuthenticated(true)
      } catch {
        api.logout()
      } finally {
        setAuthChecking(false)
      }
    }
    checkAuth()
  }, [])

  useEffect(() => {
    if (authenticated) refreshSessions()
  }, [authenticated])

  useEffect(() => {
    if (retryCountdown <= 0) {
      clearInterval(countdownRef.current)
      return
    }
    countdownRef.current = setInterval(() => {
      setRetryCountdown((s) => {
        if (s <= 1) {
          clearInterval(countdownRef.current)
          setError('')
          return 0
        }
        return s - 1
      })
    }, 1000)
    return () => clearInterval(countdownRef.current)
  }, [retryCountdown > 0])

  async function refreshSessions() {
    try {
      const data = await api.listSessions()
      setSessions(data)
    } catch (e) {
      if (e.status === 401) setAuthenticated(false)
    }
  }

  function handleNewChat() {
    setActiveSessionId(null)
    setMessages([])
    setConstraints([])
    setError('')
  }

  async function handleSelectSession(sessionId) {
    setError('')
    setActiveSessionId(sessionId)
    try {
      const data = await api.getSession(sessionId)
      const history = (data.message_history || []).map(normalizeHistoryEntry).filter(Boolean)
      if (data.last_output) {
        const last = history[history.length - 1]
        if (!last || last.role !== 'assistant' || last.content !== data.last_output) {
          history.push({ role: 'assistant', content: data.last_output })
        }
      }
      if (history.length > 0 && data.last_generated_posts?.length > 0) {
        history[history.length - 1].posts = data.last_generated_posts
      }
      setMessages(history)
      setConstraints(data.active_constraints || [])
    } catch (e) {
      setError(e.message)
    }
  }

  async function handleSend(text) {
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setSending(true)
    setError('')
    try {
      const result = await api.sendChatAndWait({
        message: text,
        sessionId: activeSessionId,
        platform: platform || undefined,
        posts,
      })
      setActiveSessionId(result.session_id)

      let postsForMessage
      try {
        const session = await api.getSession(result.session_id)
        setConstraints(session.active_constraints || [])
        if (POST_PRODUCING_ACTIONS.includes(result.action)) {
          postsForMessage = session.last_generated_posts
        }
      } catch {
        // Non-fatal -- the reply text still shows even if this refresh fails.
      }

      setMessages((prev) => [...prev, { role: 'assistant', content: result.reply || '(no reply)', posts: postsForMessage }])
      if (authenticated) refreshSessions()
    } catch (e) {
      if (e.code === 'signup_required') {
        setAuthScreenForced(true)
        setShowAuthScreen(true)
        // Drop the optimistic user bubble -- this message never actually
        // ran, no point leaving it in the transcript as if it did.
        setMessages((prev) => prev.slice(0, -1))
      } else if (e.status === 429) {
        setError(`Rate limited -- try again in ${e.retryAfterSeconds}s`)
        setRetryCountdown(e.retryAfterSeconds)
      } else {
        setError(e.message)
        if (e.status === 401) setAuthenticated(false)
      }
    } finally {
      setSending(false)
    }
  }

  function handleOpenPost(messageIndex, postIndex) {
    const post = messages[messageIndex]?.posts?.[postIndex]
    if (!post) return
    setSelectedPost({ postNumber: postIndex + 1, post })
  }

  function handleSubmitEdit(instructionText) {
    if (!selectedPost) return
    const text = `For post ${selectedPost.postNumber}: ${instructionText}`
    setSelectedPost(null)
    handleSend(text)
  }

  function handleAddConstraint(type, value) {
    handleSend(`Please ${type} "${value}" from now on.`)
  }

  function handleRemoveConstraint(value) {
    handleSend(`Please remove the constraint on "${value}".`)
  }

  async function handleClearChat() {
    if (!activeSessionId) return
    try {
      await api.deleteSession(activeSessionId)
    } catch (e) {
      setError(e.message)
      return
    }
    handleNewChat()
    if (authenticated) refreshSessions()
  }

  function handleLogout() {
    api.logout()
    setAuthenticated(false)
    setSessions([])
    setMessages([])
    setActiveSessionId(null)
  }

  function handleAuthenticated() {
    setAuthenticated(true)
    setShowAuthScreen(false)
    setAuthScreenForced(false)
    // A guest's trial conversation lived under their anon id -- claiming
    // it into the new account isn't built yet (deferred per the Phase 8
    // plan), so the safest move is a clean slate under the real identity
    // rather than silently losing half a conversation without saying so.
    setActiveSessionId(null)
    setMessages([])
  }

  if (authChecking) {
    return <div className="auth-loading">Checking session...</div>
  }

  if (showAuthScreen) {
    return (
      <AuthScreen
        onAuthenticated={handleAuthenticated}
        message={authScreenForced ? "You've used your free messages -- sign up or log in to keep going." : undefined}
        onCancel={authScreenForced ? undefined : () => setShowAuthScreen(false)}
      />
    )
  }

  return (
    <div className="app-shell">
      <div className="topbar">
        <button className="topbar-menu-btn" onClick={() => setSidebarOpen(true)}>
          Menu
        </button>
        <span className="topbar-title">TrendForge</span>
      </div>
      {authenticated ? (
        <Sidebar
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelect={handleSelectSession}
          onNewChat={handleNewChat}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onLogout={handleLogout}
        />
      ) : (
        <div className={'sidebar' + (sidebarOpen ? ' open' : '')}>
          <div className="sidebar-header">
            <h1>TrendForge</h1>
          </div>
          <p className="sidebar-empty">Guest mode -- chat history isn't saved.</p>
          <div className="sidebar-footer">
            <button className="logout-btn" onClick={() => setShowAuthScreen(true)}>
              Log in
            </button>
          </div>
        </div>
      )}
      <div className="chat-column">
        <ChatToolbar
          platform={platform}
          onPlatformChange={setPlatform}
          posts={posts}
          onPostsChange={setPosts}
          constraints={constraints}
          onAddConstraint={handleAddConstraint}
          onRemoveConstraint={handleRemoveConstraint}
          onClearChat={handleClearChat}
          hasActiveSession={Boolean(activeSessionId)}
        />
        <ChatWindow
          messages={messages}
          onSend={handleSend}
          sending={sending || retryCountdown > 0}
          error={error}
          onOpenPost={handleOpenPost}
        />
      </div>
      <PostModal
        post={selectedPost?.post}
        postNumber={selectedPost?.postNumber}
        onClose={() => setSelectedPost(null)}
        onSubmitEdit={handleSubmitEdit}
        submitting={sending}
      />
    </div>
  )
}