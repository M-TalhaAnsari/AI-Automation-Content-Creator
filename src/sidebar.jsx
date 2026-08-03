export default function Sidebar({ sessions, activeSessionId, onSelect, onNewChat, isOpen, onClose, onLogout }) {
  return (
    <>
      <div className={'sidebar-backdrop' + (isOpen ? ' open' : '')} onClick={onClose} />
      <div className={'sidebar' + (isOpen ? ' open' : '')}>
        <div className="sidebar-header">
          <h1>TrendForge</h1>
        </div>
        <button
          className="new-chat-btn"
          onClick={() => {
            onNewChat()
            onClose?.()
          }}
        >
          + New chat
        </button>
        {sessions.map((s) => (
          <div
            key={s.session_id}
            className={'session-item' + (s.session_id === activeSessionId ? ' active' : '')}
            onClick={() => {
              onSelect(s.session_id)
              onClose?.()
            }}
          >
            <span className="title">{s.title || 'Untitled chat'}</span>
          </div>
        ))}
        {sessions.length === 0 && <p className="sidebar-empty">No chats yet</p>}
        <div className="sidebar-footer">
          <button className="logout-btn" onClick={onLogout}>
            Log out
          </button>
        </div>
      </div>
    </>
  )
}