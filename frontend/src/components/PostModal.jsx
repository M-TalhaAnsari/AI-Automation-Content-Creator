import React from "react";
import { useState } from 'react'

export default function PostModal({ post, postNumber, onClose, onSubmitEdit, submitting }) {
  const [instruction, setInstruction] = useState('')

  if (!post) return null

  function handleSubmit(e) {
    e.preventDefault()
    const text = instruction.trim()
    if (!text) return
    onSubmitEdit(text)
    setInstruction('')
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span>Post {postNumber}</span>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>
        <div className="modal-body">
          {post.title && <p className="modal-title">{post.title}</p>}
          {post.hook && (
            <p className="modal-field">
              <strong>Hook:</strong> {post.hook}
            </p>
          )}
          {Array.isArray(post.summary) && post.summary.length > 0 && (
            <ul className="modal-summary">
              {post.summary.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          )}
          {post.caption && (
            <p className="modal-field">
              <strong>Caption:</strong> {post.caption}
            </p>
          )}
          {Array.isArray(post.hashtags) && post.hashtags.length > 0 && (
            <p className="modal-hashtags">{post.hashtags.join(' ')}</p>
          )}
          {post.link && (
            <a className="modal-link" href={post.link} target="_blank" rel="noreferrer">
              {post.link}
            </a>
          )}
        </div>
        <form className="modal-edit-row" onSubmit={handleSubmit}>
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Describe a change to this post..."
            disabled={submitting}
          />
          <button type="submit" disabled={submitting || !instruction.trim()}>
            Apply
          </button>
        </form>
      </div>
    </div>
  )
}