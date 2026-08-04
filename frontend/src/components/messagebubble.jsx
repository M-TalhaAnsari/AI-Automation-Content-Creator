import React from "react";
export default function MessageBubble({ role, content, pending, posts, onOpenPost }) {
  const classes = ['message-bubble', role, pending ? 'pending' : ''].filter(Boolean).join(' ')
  return (
    <div className={classes}>
      {content}
      {Array.isArray(posts) && posts.length > 0 && (
        <div className="post-entry-list">
          {posts.map((p, i) => (
            <div key={i} className="post-entry">
              <span className="post-entry-title">{p.title || `Post ${i + 1}`}</span>
              <button className="post-entry-btn" onClick={() => onOpenPost(i)}>
                View post
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}