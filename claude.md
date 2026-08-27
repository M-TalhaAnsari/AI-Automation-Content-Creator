# CLAUDE.md — AIFlick Codebase Context

This file gives Claude Code (and any AI agent) a complete technical map of the AIFlick repository so it can work effectively without re-reading the entire codebase every session.

---

## Project Identity

- **Product name**: AIFlick (rebranded from TrendForge)
- **Root directory**: `trendforge/` (the git repo root is named trendforge)
- **Brand color**: `hsl(38, 95%, 55%)` — amber/gold primary (`#F5A623` family)
- **Logo**: Geometric triangle glyph `△`, rendered as SVG in `frontend/public/favicon.svg`

---

## Running the Project

### Backend (Python 3.12)

```bash
# From repo root
cp .env.example .env          # fill in keys
docker compose up redis postgres -d
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt
uvicorn api.web.app:app --reload --port 8000
python -m api.web.image_worker                   # separate terminal
```

### Frontend (Node 20)

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

### Build check (run before every commit)

```bash
cd frontend && npm run build
```

Exit code 1 from PowerShell `2>&1` redirect is a PS warning only — a clean build shows `✓ built in Xs` for all three phases (client, SSR, Nitro).

---

## Environment Variables (minimum to run)

```
GEMINI_API_KEY=...            # Required — primary LLM + Imagen
GROQ_API_KEY=...              # Required — fallback LLM
DATABASE_URL=postgresql://trendforge:trendforge@localhost:5432/trendforge
REDIS_URL=redis://localhost:6379/0
IMAGE_PROVIDER=pollinations   # Free — no key needed
```

All optional keys are in `.env.example`.

---

## Backend Architecture

### Entry Points

| Command | File | Purpose |
|:--------|:-----|:--------|
| `uvicorn api.web.app:app` | `api/web/app.py` | FastAPI HTTP server |
| `python -m api.web.worker` | `api/web/worker.py` | RQ worker — chat pipeline jobs |
| `python -m api.web.image_worker` | `api/web/image_worker.py` | RQ worker — image generation jobs |

### API Routes

| Prefix | File | Notes |
|:-------|:-----|:------|
| `/api/auth` | `api/web/auth.py` | JWT login, register, refresh |
| `/api/sessions` | `api/web/routes/sessions.py` | Create / list chat sessions |
| `/api/chat` | `api/web/routes/chat.py` | Send message, get response |
| `/api/images` | `api/web/image_routes.py` | Generate, poll, serve images |
| `/api/users/me` | `api/web/routes/users.py` | User profile, settings, tier |
| `/api/memory` | `api/web/routes/memory.py` | User memory CRUD |

### LangGraph Pipeline (`generation/`)

The chat pipeline is a LangGraph state machine. Nodes in order:

1. `understanding/` — Intent detection (educate / inspire / showcase / news / review)
2. `research/` — Multi-source data fetch (GitHub, Reddit, YouTube, HN, Tavily, etc.)
3. `generation/content_generator.py` — Gemini / Groq LLM call → structured JSON posts
4. `generation/prompt_composer.py` — Builds the viral prompt with platform strategy

**Critical rule in `prompt_composer.py`** — Rule 5 forbids markdown headers (`#`, `##`, `###`) and AI cliché filler inside `title`, `hook`, and `summary` fields.

**Backend sanitizer in `content_generator.py`** — `_clean_text()` strips accidental markdown from all generated fields before returning JSON.

### Image Generation (`imaging/`)

Adapters for:
- `PolllinationsProvider` — FREE, FLUX models, default
- `HuggingFaceProvider` — Free HF Inference API
- `ImagenProvider` — Google Imagen 3/4 (requires `GEMINI_API_KEY`)
- `MockProvider` — Offline testing

Image jobs are enqueued to Redis via RQ and processed by `image_worker.py`. Status polling via `/api/images/{job_id}/status`.

### Auth (`api/web/auth.py`, `api/web/security/`)

- JWT HS256, 15-min access + 7-day refresh tokens
- bcrypt password hashing
- User tiers: `explorer` | `creator` | `pro`
- Rate limits via SlowAPI in `api/web/rate_limit.py`

---

## Frontend Architecture

### File Structure

```
frontend/src/
├── routes/
│   ├── __root.tsx          # Root layout — favicon, meta, fonts
│   └── index.tsx           # Main workspace — all state lives here
├── components/
│   └── aiflick/
│       ├── data.ts                     # GeneratedPost type, cleanHumanCopy()
│       ├── landing-page.tsx            # Marketing landing page
│       ├── auth-screen.tsx             # Login/signup modal
│       ├── app-sidebar.tsx             # Left sidebar nav
│       ├── workspace-header.tsx        # Top bar
│       ├── chat-workspace.tsx          # Chat feed + input + stop button
│       ├── post-card.tsx               # Per-post card in chat feed (inline edit)
│       ├── post-modal.tsx              # Full post studio modal
│       ├── social-post-canvas.tsx      # Fabric.js canvas — direct text editing
│       ├── platform-badge.tsx          # IG / LinkedIn / TikTok badges
│       ├── settings-modal.tsx          # User settings + memory
│       └── context-panel.tsx           # Sidebar context controls
├── api/
│   ├── client.ts                       # Fetch wrapper, abort signal, error types
│   └── chat.ts                         # sendChat(), sendChatAndWait(), generateImage()
└── hooks/                              # Custom React hooks
```

### State Model (`index.tsx`)

```typescript
// Core state
const [messages, setMessages] = useState<ChatMessage[]>([]);
const [activePost, setActivePost] = useState<{ post: GeneratedPost; index: number } | null>(null);
const [modalOpen, setModalOpen] = useState(false);
const [sending, setSending] = useState(false);
const abortControllerRef = useRef<AbortController | null>(null);

// Key handlers
handleSend(prompt?)       // Submit message, manage abort, update messages
handleStop()              // Abort in-flight generation
handleUpdatePost(post)    // Real-time sync — updates messages state + activePost
handleViewPost(post, idx) // Open modal
handleGenerateImage(post) // Enqueue image job, poll until done
handleBatchGenerateImages // Generate all posts without images
```

### GeneratedPost Type (`data.ts`)

```typescript
interface GeneratedPost {
  id: string;
  number: number;
  title: string;
  hook: string;
  summary: string[];        // bullet points for on-screen card
  caption: string;          // rich description / full post text
  hashtags: string[];
  platform: string;
  sourceUrl?: string;
  imageUrl?: string;        // served AI-generated background
  imageAssetId?: string;
  isGeneratingImage?: boolean;
  latencyMs?: number;
}
```

`cleanHumanCopy(text)` strips `#`, `##`, `###`, `**bold**`, `__underline__`, and backtick code spans.

### Canvas Architecture (`social-post-canvas.tsx`)

**Critical**: The canvas does NOT rebuild on every text prop change. It uses:

1. **Named object refs** — `titleObjRef`, `hookObjRef`, `bulletObjRefs` store Fabric.js `Textbox` instances
2. **Lightweight update effects** — 3 separate `useEffect`s update the objects in-place via `obj.set("text", ...)` + `canvas.renderAll()`
3. **`text:changed` callbacks** — when user types on canvas directly, callbacks propagate back up via `onTitleChange`, `onHookChange`, `onSummaryChange`
4. **Full rebuild only on**: dimension change, theme change, bg source change, card opacity change, watermark toggle, background image URL change

**Double-click to edit**: `mouse:dblclick` event calls `target.enterEditing()` for instant inline editing.

**No text shadows**: Removed `fabric.Shadow` from titleFab — was causing a "ghost text" duplication artifact.

### Post Card Inline Edit (`post-card.tsx`)

- Click on the title/hook area → shows Quick Edit form inline in the card
- Enter key → saves; Escape → cancels
- `useEffect` syncs `inlineTitle`/`inlineHook` from `post.title`/`post.hook` whenever parent updates them
- Saves via `onUpdatePost(updatedPost)` → `handleUpdatePost` in index.tsx

### Post Modal (`post-modal.tsx`)

Two tabs:
1. **Visual Studio & Canvas** — Fabric.js canvas left (7/12 cols) + sidebar inputs right (5/12 cols)
2. **Full Copy & Description** — plain text view of all content

Every input uses immediate real-time sync via `updateField({ ...fields })` which calls `onUpdatePost`.

### API Client (`api/client.ts`, `api/chat.ts`)

- `sendChat(sessionId, message, signal?)` — POST `/api/chat/...`
- `sendChatAndWait(...)` — poll until complete
- `generateImage(postId, prompt?)` — enqueue image job
- `AbortController` signal passed through for Stop Generation

### Stop Generation

1. User clicks ■ Stop button in chat input
2. `handleStop()` calls `abortControllerRef.current.abort()`
3. Signal passed to `sendChat()` → fetch cancelled
4. Toast: "Generation stopped"
5. `setSending(false)` restores input

---

## User-Visible Brand Rules

- **Brand name**: AIFlick (never TrendForge in UI)
- **Logo**: Triangle `△` with AIFlick text
- **Favicon**: `/favicon.svg` — iridescent geometric glyph
- **Logo click**: `window.location.reload()` — always
- **Watermark**: "Created with AIFlick • @handle"
- **Creator badges**: "Tech Creators", "Indie Hackers", "AI Engineers", "SaaS Founders", "Growth Marketers", "Newsletter Authors", "Solopreneurs"
- **No OWASP/technical security marketing** in user-facing copy

---

## Content Generation Rules (Prompt + Backend)

**In `prompt_composer.py` Rule 5**:
- NEVER use `#`, `##`, `###` or `**bold**` inside `title`, `hook`, or `summary`
- NEVER use AI clichés ("In today's fast-paced...", "Let's delve in", "Game changer")

**In `content_generator.py` `_clean_text()`**:
- Strips leading `#+ ` from titles
- Strips `**text**` bold markers
- Applied to: `title`, `hook`, `summary[]`

**In `data.ts` `cleanHumanCopy()`**:
- Client-side safety net — strips the same markdown artifacts before rendering

---

## Known Build Behavior

- `npm run build` exits with PowerShell code 1 due to `2>&1` redirect — this is NOT a real error
- Actual build success is indicated by `✓ built in Xs` for all 3 phases
- Chunk size warnings about fabric.mjs (4.8MB) are expected — Fabric.js is large

---

## Deployment Checklist

1. Copy `.env.example` → `.env`, fill all required keys
2. Set `POSTGRES_PASSWORD` in `.env`
3. Run `docker compose up --build -d`
4. Run frontend `npm run build` → deploy `.output/` to Cloudflare Workers
5. Set `CORS_ORIGINS` in backend to include your frontend domain
6. Set `VITE_API_URL` (or equivalent) in frontend build to point to your API domain

---

## Adding New Features

### New research source

1. Create `research/my_source.py` — implement `fetch(topic: str) -> list[dict]`
2. Register in `research/registry.py`
3. Add toggle `ENABLE_MY_SOURCE=true` in `.env.example` and `Config/config.py`

### New LLM provider

1. Add adapter in `llm/` implementing the standard `call_*` interface
2. Add to `content_generator.py` try/except chain

### New image provider

1. Implement provider class in `imaging/providers/`
2. Register in `imaging/registry.py`
3. Add `IMAGE_PROVIDER=my_provider` to `.env.example`

### New platform (e.g. Threads)

1. Create `generation/platforms/threads_platform.py`
2. Register in `generation/platforms/registry.py`
3. Add platform badge in `frontend/src/components/aiflick/platform-badge.tsx`
