export default function MessageBubble({ role, content, pending, posts, onOpenPost }) {
  const classes = ['message-bubble', role, pending ? 'pending' : ''].filter(Boolean).join(' ')
  return (
    <div className={classes}>
      {content}
      {Array.isArray(posts) && posts.length > 0 && (
        <div className="post-chip-row">
          {posts.map((p, i) => (
            <button key={i} className="post-chip" onClick={() => onOpenPost(i)}>
              Post {i + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}