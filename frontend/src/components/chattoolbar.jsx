import { useState } from 'react'

const PLATFORMS = ['instagram', 'youtube', 'linkedin', 'tiktok']

export default function ChatToolbar({
  platform,
  onPlatformChange,
  posts,
  onPostsChange,
  constraints,
  onAddConstraint,
  onRemoveConstraint,
  onClearChat,
  hasActiveSession,
}) {
  const [constraintType, setConstraintType] = useState('exclude')
  const [constraintValue, setConstraintValue] = useState('')

  function handleAdd(e) {
    e.preventDefault()
    const value = constraintValue.trim()
    if (!value) return
    onAddConstraint(constraintType, value)
    setConstraintValue('')
  }

  return (
    <div className="chat-toolbar">
      <select value={platform} onChange={(e) => onPlatformChange(e.target.value)}>
        <option value="">Platform (auto)</option>
        {PLATFORMS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>

      <input
        type="number"
        className="posts-input"
        min={1}
        max={20}
        value={posts}
        onChange={(e) => onPostsChange(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
        aria-label="Number of posts"
      />

      <div className="toolbar-divider" />

      {constraints.map((c, i) => (
        <span className="constraint-chip" key={i}>
          {c.type}: {c.value}
          <span className="remove-x" onClick={() => onRemoveConstraint(c.value)}>
            &times;
          </span>
        </span>
      ))}

      <form className="add-constraint-form" onSubmit={handleAdd}>
        <select value={constraintType} onChange={(e) => setConstraintType(e.target.value)}>
          <option value="exclude">Exclude</option>
          <option value="prefer">Prefer</option>
        </select>
        <input
          value={constraintValue}
          onChange={(e) => setConstraintValue(e.target.value)}
          placeholder="e.g. clickbait tone"
        />
        <button type="submit">Add</button>
      </form>

      <button className="clear-chat-btn" onClick={onClearChat} disabled={!hasActiveSession}>
        Clear chat
      </button>
    </div>
  )
}