import { useEffect, useRef, useState } from 'react'
import MessageBubble from '../MessageBubble'

export default function ChatWindow({ messages, onSend, sending, error, onOpenPost }) {
  const [draft, setDraft] = useState('')
  const listRef = useRef(null)

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight
    }
  }, [messages, sending])

  function handleSubmit(e) {
    e.preventDefault()
    const text = draft.trim()
    if (!text || sending) return
    setDraft('')
    onSend(text)
  }

  return (
    <div className="chat-body">
      {error && <div className="error-banner">{error}</div>}
      <div className="message-list" ref={listRef}>
        {messages.length === 0 && !sending && (
          <p className="empty-state">Start a conversation -- try "generate instagram posts about docker deployment"</p>
        )}
        {messages.map((m, i) => (
          <MessageBubble
            key={i}
            role={m.role}
            content={m.content}
            posts={m.posts}
            onOpenPost={(postIndex) => onOpenPost(i, postIndex)}
          />
        ))}
        {sending && <MessageBubble role="assistant" content="Working on it..." pending />}
      </div>
      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Message TrendForge..."
          disabled={sending}
        />
        <button type="submit" disabled={sending || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  )
}