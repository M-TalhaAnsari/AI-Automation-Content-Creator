# TrendForge — Multi-Agent Trend Intelligence & Content Generation

> **TrendForge** is an AI-powered pipeline that transforms raw content ideas into high-performing, platform-ready social media posts backed by real-time web research, automated quality validation, and interactive conversational editing.

---

## 1. System Overview

TrendForge takes a user's natural-language content prompt (e.g., *"5 LinkedIn posts on the latest Python 3.13 features"*), gathers real-time data from multi-source APIs (GitHub, Google Trends, HackerNews, Tavily, YouTube, PapersWithCode), selects the highest-signal insights, and crafts structured, platform-optimized posts.

### Core Capabilities
- **Multi-Source Real-Time Research**: Queries multiple platforms concurrently or by category matching.
- **LangGraph Retry Loops**: Two-tier evaluation gates (fetch quality floor & post structure/item-kind validation) that loop back and retry until quality thresholds are satisfied.
- **Unified LLM Gateway**: Centralized API gateway (`llm/client.py`) with Pydantic schema validation and automatic fallback between Google Gemini and Groq (LLaMA-3).
- **Conversational Refinement**: Direct-dispatch conversational actions for incremental additions (`generate_more`), targeting revisions (`edit_existing`, `targeted_refetch`), and rollbacks (`undo`).
- **Production Backend**: FastAPI / ASGI web app with JWT authentication, Redis session store, PostgreSQL persistence, and RQ background job queues.

---

## 2. System-Level Data Flow

```
User message (HTTP POST /chat or CLI)
        │
        ▼
api/web/app.py (FastAPI, JWT Auth, Rate Limiting)
        │
        ├─ INLINE Actions (add_constraint, remove_constraint, clarify)
        │   └── orchestration/conversation_agent.py → conversation/actions.py
        │
        └─ ASYNC / SLOW Actions (run_new_request, generate_more, edit_existing, targeted_refetch)
            └── RQ Background Job (api/web/jobs.py)
                    │
                    ▼
            orchestration/dispatch.py
                    │
            ┌───────┴───────────────────────────────┐
            ▼                                       ▼
     run_new_request                         Interactive Actions
     (pipeline/generate.py)                  (generate_more, edit_existing,
            │                                 targeted_refetch, undo)
            ▼
 ╔═════════════════════════════════════════════════════════════════════╗
 ║                     LangGraph Execution Engine                      ║
 ║                                                                     ║
 ║   [parse] ──► [route] ──► [fetch] ──► [evaluate_fetch]              ║
 ║                              ▲               │                      ║
 ║                              └── (Retry) ────┤                      ║
 ║                                              ▼ (Proceed)            ║
 ║   [format] ◄── [evaluate_generation] ◄── [generate]                 ║
 ║       │                │                     ▲                      ║
 ║      END               └── (Retry) ──────────┘                      ║
 ╚═════════════════════════════════════════════════════════════════════╝
            │
            ▼
  memory/session_store & memory/redis_session_store
            │
            ▼
    Structured Post Output & Frontend Response
```

---

## 3. Module Reference

### `core/`
**Purpose:** Shared infrastructure. Zero imports from any other TrendForge module.

| File | What it does |
|---|---|
| `state.py` | `TrendForgeState` TypedDict, `create_initial_state()`, `add_log()`, `add_error()`, `add_tokens()`, `get_total_tokens()` |
| `token_tracker.py` | `TokenTracker` — generates the token usage report in the CLI output |

**How to extend:** Never. This is infrastructure only. New state fields go here; new modules do not.

---

### `config/`
**Purpose:** Single source of truth for all settings, keys, and constants.

| Key export | What it is |
|---|---|
| `CONFIG` | `TrendForgeConfig` singleton — `CONFIG.models`, `CONFIG.sources`, `CONFIG.system` |
| `PLATFORM_SETTINGS` | Per-platform tone/format/hashtag rules (read by `workflow/gates.py` for caption length validation) |
| `SUPPORTED_PLATFORMS` | `["instagram","youtube","linkedin","tiktok","facebook"]` |
| `SOURCE_MAP` | `category -> [source names]` — used by `research/routing/` |

**How to extend:** Add a new platform → `PLATFORM_SETTINGS` + `SUPPORTED_PLATFORMS`. Add a new API key → `SourceConfig` dataclass. Do not split this file until it exceeds ~200 lines.

---

### `understanding/`
**Purpose:** Converts raw user text → structured `TrendForgeState` fields.

| File | What it does |
|---|---|
| `prompt_parser.py` | Entry point. Calls cleaner then extractor. |
| `prompt_cleaner.py` | Rule-based: detects platform, post count, special requests. 0 tokens. |
| `intent_extractor.py` | Groq LLM call. Sets `core_topic`, `content_intent`, `platform`, `item_kind`, `search_queries`. |

**Key output fields set here:**
- `core_topic` — the actual subject, stripped of meta-words
- `content_intent` — `showcase|educate|news|inspire|review`
- `platform` — `instagram|youtube|linkedin|tiktok|facebook`
- `post_count` — integer
- `search_queries` — list of 1-3 search strings for the fetchers
- `item_kind` — e.g. "a named API or protocol" (used by workflow/gates.py Tier-2 check)

**How to extend:** New intent category → add to `CATEGORY_DEFAULT_INTENT` dict in `intent_extractor.py` and to the LLM prompt's rule list. New platform → add to `SUPPORTED_PLATFORMS` in `config/` and to the LLM prompt's platform enum.

**When asking an AI for help:** Share `understanding/` + `core/state.py` only.

---

### `research/`
**Purpose:** All live data fetching and source routing. Nothing in this module generates content.

```
research/
├── fetchers/
│   ├── fetcher_orchestrator.py   ← entry point, dispatches to per-source fetchers
│   ├── github_fetcher.py
│   ├── hackernews_fetcher.py
│   ├── youtube_fetcher.py
│   ├── google_trends_fetcher.py
│   ├── paperswithcode_fetcher.py
│   ├── tavily_fetcher.py
│   └── fetching_reddit/
│       └── reddit_fetcher.py
└── routing/
    ├── router_orchestrator.py    ← entry point, tries RuleRouter then LLMRouter
    ├── rule_router.py            ← 0 tokens, category→sources map
    ├── llm_router.py             ← Groq fallback (~100t)
    └── registry.py               ← get_available_sources() (checks CONFIG for enabled+credentialed sources)
```

**Contract:** Every fetcher has the signature `fetch(state_obj: SimpleNamespace, config: TrendForgeConfig) -> list[dict]`. Each item in the list must have at minimum: `title`, `link`, `summary` (or `description` or `snippet`).

**How to extend:** Add a new source → create one new fetcher file with the same signature, add one line to `FETCHER_MAP` in `fetcher_orchestrator.py`, add one line to `registry.py`. Nothing else changes.

**When asking an AI for help:** Share `research/` + `config/__init__.py` only.

---

### `generation/`
**Purpose:** Converts fetched data + structured intent → final post objects. Strategy Pattern.

```
generation/
├── content_generator.py    ← entry point: selects intent strategy, selects platform strategy,
│                             calls compose_prompt(), makes ONE LLM call (Gemini + Groq fallback)
├── prompt_composer.py      ← the ONLY file that sees both strategy hierarchies
├── formatter.py            ← format_output() (CLI terminal block), save_output()
├── prompts.py              ← legacy (kept, not deleted)
├── intents/
│   ├── base_intent.py      ← BaseIntentStrategy ABC + IntentGuidance dataclass
│   ├── showcase_intent.py
│   ├── educate_intent.py
│   ├── news_intent.py
│   ├── inspire_intent.py
│   ├── review_intent.py
│   └── registry.py         ← INTENT_STRATEGY_MAP + get_intent_strategy(content_intent)
└── platforms/
    ├── base_platform.py    ← BasePlatformStrategy ABC
    ├── instagram_platform.py
    ├── linkedin_platform.py  ← overrides effective_post_count() → always 1
    ├── tiktok_platform.py    ← overrides wrap_caption_guide() → script format
    ├── youtube_platform.py   ← overrides wrap_caption_guide() → script format
    ├── facebook_platform.py
    └── registry.py           ← PLATFORM_STRATEGY_MAP + get_platform_strategy(platform)
```

**The two axes are independent:**
- `IntentStrategy.get_guidance(state)` → what to say (never branches on platform)
- `PlatformStrategy` → how to package it (never branches on content_intent)
- `compose_prompt()` combines them into one string → one LLM call in `ContentGenerator`

**Output contract** (what `generated_posts` items must have — validated by `workflow/gates.py`):
```python
{
    "title": str,
    "hook": str,
    "summary": list[str],   # non-empty
    "link": str,            # may be "" for inspire/educate
    "caption": str,
    "hashtags": list[str],  # each starts with "#"
}
```

**How to extend:**
- New intent → create one file in `intents/`, register one line in `intents/registry.py`
- New platform → create one file in `platforms/`, register one line in `platforms/registry.py`, add settings to `config/PLATFORM_SETTINGS`
- Nothing else changes in either case (Open/Closed)

**When asking an AI for help:** Share `generation/` + `core/state.py` + `config/__init__.py` only.

---

### `workflow/`
**Purpose:** Quality gates that decide whether to retry or proceed at each pipeline stage.

| Function | When called | What it checks |
|---|---|---|
| `evaluate_fetch_quality(state)` | After each fetch attempt | Item count ≥ floor, at least one real source returned data, no generic-search-only links |
| `evaluate_post_validation(state)` | After generation | Required fields present, caption length within platform limit, no duplicate titles, link quality for link-required intents |
| `evaluate_item_kind_match(state)` | After generation | Groq Tier-2 semantic check — titles actually name discrete instances of `item_kind` |

**Return shape** (all three gates): `{"valid": bool, "errors": list[str], "should_retry": bool}`

**How to extend:** Add a new gate → new function in `gates.py`, wire it into the retry loop in `main.py`. Existing gates are not modified.

**When asking an AI for help:** Share `workflow/gates.py` + `config/PLATFORM_SETTINGS` only.

---

### `memory/`
**Purpose:** Two separate stores — one for active sessions (fast, temporary), one for history (slow, permanent).

| File | Store | Backend | Lifetime | Key shape |
|---|---|---|---|---|
| `redis_session_store.py` | Active conversation dict | Redis (primary) + Postgres (fallback) | Sliding TTL (24h default) | `tf:session:{client_name}:{session_id}` |
| `session_store.py` | Permanent run history | JSON file | Last 100 sessions | Chronological list |

**Phase 7 architecture (write-through cache):**
- `save_conversation()` writes to Redis AND Postgres simultaneously
- `load_conversation()` checks Redis first (fast path), falls back to Postgres on miss, repopulates Redis
- `client_name` is `"user:{user_id}"` for logged-in users, `"anon:{anon_id}"` for guests
- Anon sessions never touch Postgres (`parse_user_id()` rejects non-`"user:"` prefixes)

**When asking an AI for help:** Share `memory/` only.

---

### `conversation/`
**Purpose:** Turn-by-turn routing and action execution for the chat interface.

| File | What it does |
|---|---|
| `orchestrator.py` | `process_turn(conversation, message)` — Groq tool-calling decides which action. `maybe_summarize()` — folds old history into rolling summary. `update_last_tool_result()` — fills the tool-role placeholder after dispatch. |
| `actions.py` | Pure action implementations: `edit_existing()`, `add_constraint()`, `remove_constraint()`, `targeted_refetch()`. No routing logic here. |

**Actions and where they run:**

| Action | Runs in | Slow? |
|---|---|---|
| `run_new_request` | RQ background job | Yes (20-96s) |
| `edit_existing` | RQ background job | Yes |
| `targeted_refetch` | RQ background job | Yes |
| `add_constraint` | Inline (request thread) | No |
| `remove_constraint` | Inline (request thread) | No |
| `clarify` | Inline (request thread) | No |

**When asking an AI for help:** Share `conversation/` + `core/state.py` only.

---

### `api/`
**Purpose:** FastAPI web layer. Adapts the pipeline to HTTP. Nothing in the pipeline imports from `api/` — dependency only flows inward.

```
api/web/
├── app.py          ← All route definitions. Uses Depends(verify_identity).
├── auth.py         ← JWT (create_jwt, verify_jwt), password hashing, verify_identity (accepts JWT or X-Anon-Id)
├── anon_trial.py   ← Guest trial usage tracking (Redis, never Postgres)
├── db.py           ← Postgres: users table, chat_sessions index, write-through conversation store
├── deps.py         ← resolve_session_id() (body → cookie → new)
├── handlers.py     ← finalize_turn() bridges web layer to main.dispatch_action()
├── jobs.py         ← run_slow_action() — the RQ job entry point
├── rate_limit.py   ← slowapi, keyed by resolved identity (not IP)
├── schemas.py      ← All Pydantic models
└── worker.py       ← RQ worker process entry point
```

**Auth flow:**
```
Request arrives
    │
    ├─ Authorization: Bearer <jwt>  →  verify_jwt()  →  "user:{id}"
    ├─ X-Anon-Id: <uuid>           →  anon_trial check  →  "anon:{uuid}" (or 403 if over limit)
    └─ neither                     →  401
```

**Rate limiting:** keyed by the resolved identity string (`"user:{id}"` or `"anon:{uuid}"`), backed by Redis, so limits are shared across replicas.

**When asking an AI for help:** Share `api/` + `memory/__init__.py` + `conversation/__init__.py` only.

---

### `publishing/` (Planned)
**Purpose:** Post content to social platforms after generation.
**Status:** Not yet built. See `publishing/__init__.py` for the planned interface.
**Integration point:** `main.py:run()` after `format_output()`.

---

### `analytics/` (Planned)
**Purpose:** Track post performance, feed back into generation.
**Status:** Not yet built. See `analytics/__init__.py` for the planned interface.
**Integration point:** Reads from `memory/session_store.py`, writes performance scores back.

---

### `agents/` (Planned)
**Purpose:** Autonomous agents that chain multiple pipeline steps.
**Status:** Not yet built. See `agents/__init__.py` for the planned interface.
**Integration point:** Uses only the public interfaces of each module (`from generation import ContentGenerator`, etc.).

---

## 4. Adding a New Feature — Decision Tree

```
New feature idea
        │
        ├─ New data source (e.g. LinkedIn scraper)?
        │   └── Add to research/fetchers/ + research/routing/registry.py
        │
        ├─ New content type/intent (e.g. "compare")?
        │   └── Add to generation/intents/ + generation/intents/registry.py
        │
        ├─ New platform (e.g. Threads)?
        │   └── Add to generation/platforms/ + config/PLATFORM_SETTINGS + conversation/orchestrator.py tool schema
        │
        ├─ New web endpoint (e.g. POST /publish)?
        │   └── Add to api/web/app.py + api/web/schemas.py
        │
        ├─ New quality check (e.g. plagiarism gate)?
        │   └── Add to workflow/gates.py, wire into main.py's retry loops
        │
        ├─ New autonomous behavior (e.g. scheduled posting)?
        │   └── Add to agents/ using only public module interfaces
        │
        └─ Cross-cutting change (e.g. new state field)?
            └── Add to core/state.py's _DEFAULT_CONVERSATION and TrendForgeState TypedDict
```

---

## 5. File → New Location Migration Map

> Use this table to move your existing files from the current flat structure to the new feature-oriented structure. The source paths are where your files are now; the destination paths are where they belong in the new layout. No file needs to be rewritten — only moved and imports updated.

| Current path | New path | Notes |
|---|---|---|
| `config.py` | `config/settings.py` (or keep as `config.py` at root) | Keep at root short-term; the `config/__init__.py` re-exports everything |
| `main.py` | `main.py` (keep at root) | Entry point, stays at root |
| `core/state.py` | `core/state.py` | No change |
| `core/token_tracker.py` | `core/token_tracker.py` | No change |
| `understanding/prompt_parser.py` | `understanding/prompt_parser.py` | No change |
| `understanding/prompt_cleaner.py` | `understanding/prompt_cleaner.py` | No change |
| `understanding/intent_extractor.py` | `understanding/intent_extractor.py` | No change — facebook added to platform enum |
| `routing/router_orchestrator.py` | `research/routing/router_orchestrator.py` | **Move** — routing is part of research |
| `routing/rule_router.py` | `research/routing/rule_router.py` | **Move** |
| `routing/llm_router.py` | `research/routing/llm_router.py` | **Move** |
| `routing/registry.py` | `research/routing/registry.py` | **Move** |
| `fetchers/fetcher_orchestrator.py` | `research/fetchers/fetcher_orchestrator.py` | **Move** |
| `fetchers/github_fetcher.py` | `research/fetchers/github_fetcher.py` | **Move** |
| `fetchers/hackernews_fetcher.py` | `research/fetchers/hackernews_fetcher.py` | **Move** |
| `fetchers/youtube_fetcher.py` | `research/fetchers/youtube_fetcher.py` | **Move** |
| `fetchers/google_trends_fetcher.py` | `research/fetchers/google_trends_fetcher.py` | **Move** |
| `fetchers/paperswithcode_fetcher.py` | `research/fetchers/paperswithcode_fetcher.py` | **Move** |
| `fetchers/tavily_fetcher.py` | `research/fetchers/tavily_fetcher.py` | **Move** |
| `fetchers/fetching_reddit/reddit_fetcher.py` | `research/fetchers/fetching_reddit/reddit_fetcher.py` | **Move** |
| `generation/content_generator.py` | `generation/content_generator.py` | No change |
| `generation/prompt_composer.py` | `generation/prompt_composer.py` | No change — new file from P11 |
| `generation/prompts.py` | `generation/prompts.py` | No change — kept as legacy |
| `generation/formatter.py` | `generation/formatter.py` | No change |
| `generation/intents/` | `generation/intents/` | No change — new from P11 |
| `generation/platforms/` | `generation/platforms/` | No change — new from P11 |
| `workflow/gates.py` | `workflow/gates.py` | No change |
| `conversation/orchestrator.py` | `conversation/orchestrator.py` | No change |
| `conversation/actions.py` | `conversation/actions.py` | No change |
| `memory/redis_session_store.py` | `memory/redis_session_store.py` | No change |
| `memory/session_store.py` | `memory/session_store.py` | No change |
| `web/app.py` | `api/web/app.py` | **Move** — web layer belongs under api/ |
| `web/auth.py` | `api/web/auth.py` | **Move** |
| `web/anon_trial.py` | `api/web/anon_trial.py` | **Move** |
| `web/db.py` | `api/web/db.py` | **Move** |
| `web/deps.py` | `api/web/deps.py` | **Move** |
| `web/handlers.py` | `api/web/handlers.py` | **Move** |
| `web/jobs.py` | `api/web/jobs.py` | **Move** |
| `web/rate_limit.py` | `api/web/rate_limit.py` | **Move** |
| `web/schemas.py` | `api/web/schemas.py` | **Move** |
| `web/worker.py` | `api/web/worker.py` | **Move** |

**After moving `routing/` → `research/routing/` and `fetchers/` → `research/fetchers/`**, the only imports that need updating are:
- `main.py`: `from routing.router_orchestrator` → `from research.routing.router_orchestrator`
- `main.py`: `from fetchers.fetcher_orchestrator` → `from research.fetchers.fetcher_orchestrator`
- `conversation/actions.py`: same fetcher import update
- Any internal imports within the routing/fetcher files themselves

All other import paths stay identical — the file names didn't change, only their parent folders.

---

## 6. Environment Variables

```bash
# LLM providers
GROQ_API_KEY=          # Required: routing, intent extraction, orchestrator, fallback generation
GEMINI_API_KEY=        # Required: content generation (primary)
GROQ_MODEL_SMALL=      # Default: openai/gpt-oss-20b   (classification, routing, gates)
GROQ_MODEL_LARGE=      # Default: openai/gpt-oss-120b  (generation fallback, orchestrator)
GEMINI_MODEL=          # Default: gemini-3.5-flash      (primary generation)

# Data sources (optional — sources disabled if key missing)
TAVILY_API_KEY=
YOUTUBE_API_KEY=
GITHUB_TOKEN=          # Optional — 60 req/hr without, 5000/hr with
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=     # Default: TrendForge/1.0

# Infrastructure
REDIS_URL=             # Default: redis://localhost:6379/0
DATABASE_URL=          # Postgres connection string (Phase 7)
SESSION_TTL_SECONDS=   # Default: 86400 (24h)

# Web auth (Phase 7/8)
JWT_SECRET=            # Required for web layer
POSTGRES_PASSWORD=     # Required for docker-compose

# Guest trial limits (Phase 8)
MAX_ANON_MESSAGES=     # Default: 3
MAX_ANON_TOKENS=       # Default: 3000
```

---

## 7. Docker Compose Services

```
redis     -- Session storage (Redis 7 Alpine)
postgres  -- User accounts + chat session index (Postgres 16 Alpine)
app       -- FastAPI (uvicorn api/web/app:app --host 0.0.0.0 --port 8000)
worker    -- RQ worker (python -m api.web.worker)
```

All four start with `docker-compose up --build`. Postgres schema is created automatically by `init_db()` on the app's first startup.

---

## 8. Frontend

React + Vite, served separately from the backend during development.

```
frontend/src/
├── App.jsx                      ← root: auth check, guest/user routing, session state
├── styles.css                   ← design tokens (ember palette, IBM Plex Mono)
├── api/client.js                ← all HTTP calls + auth header injection + polling
└── components/
    ├── AuthScreen.jsx            ← tabbed login/signup with validation
    ├── Sidebar.jsx               ← chat history list, new chat, logout
    ← ChatWindow.jsx              ← message list + input row
    ├── MessageBubble.jsx         ← user/assistant bubbles + post entry list
    ├── PostModal.jsx             ← blurred-backdrop post viewer + per-post edit
    └── ChatToolbar.jsx           ← platform/post-count controls + constraint editor
```

**Dev:** `npm run dev` (proxies `/chat`, `/auth`, `/sessions` to `localhost:8000`)
**Prod:** `npm run build` → serve `dist/` as static files (Caddy or Cloudflare Tunnel)

---

*Last updated: P11 (Strategy Pattern refactor). Next planned: publishing/, analytics/, agents/.*
