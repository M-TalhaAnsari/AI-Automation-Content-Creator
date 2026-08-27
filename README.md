# AIFlick ⚡ — AI-Powered Social Content Creator

> **Turn any trend, topic, or idea into polished, platform-ready Instagram / LinkedIn / TikTok posts in seconds — with a fully-editable visual canvas, AI background generation, and real-time copy sync.**

---

## 📸 What is AIFlick?

AIFlick is a full-stack AI content creation platform. You describe what you want to post about and AIFlick:

1. **Researches** live data across GitHub, Reddit, YouTube, HackerNews, Tavily, and more
2. **Generates** 1–10 viral-optimized post cards with clean headlines, hooks, bullet points, and rich captions
3. **Renders** each post on an interactive **Fabric.js canvas** you can edit directly like a design tool
4. **Generates AI backgrounds** via FLUX / Pollinations / Imagen pipelines into the canvas
5. **Exports** posts as high-res images ready to upload

---

## 🏗 Tech Stack

| Layer | Technology |
|:------|:-----------|
| **Frontend** | React 19, TanStack Router + Start, Vite 8, Fabric.js 5, Tailwind CSS 4, Framer Motion |
| **UI Components** | Radix UI (shadcn/ui), Lucide React, Sonner toasts |
| **Backend API** | FastAPI, Uvicorn, Pydantic v2 |
| **AI Orchestration** | LangGraph, LangChain |
| **LLM — Text** | Google Gemini (primary) + Groq LLaMA3 (fallback) |
| **LLM — Images** | Pollinations.ai FLUX (free default), Hugging Face, Google Imagen |
| **Database** | PostgreSQL 16 |
| **Cache / Queue** | Redis 7 + RQ (task queue for image generation) |
| **Auth** | JWT + bcrypt |
| **Research Sources** | Tavily, GitHub, Reddit, YouTube, HackerNews, Papers With Code, Hugging Face Hub |
| **Deployment** | Docker + docker-compose / Cloudflare Workers (frontend via Nitro) |

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **Docker + Docker Compose** (for Redis & Postgres)
- At minimum: `GEMINI_API_KEY`

### 1 — Clone & configure environment

```bash
git clone <your-repo-url>
cd trendforge
cp .env.example .env
# Edit .env with your API keys
```

### 2 — Start infrastructure

```bash
docker compose up redis postgres -d
```

### 3 — Start Python backend

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn api.web.app:app --reload --port 8000
```

In a second terminal — start image generation worker:

```bash
python -m api.web.image_worker
```

### 4 — Start frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** — API at **http://localhost:8000**

---

## ⚙️ Environment Variables

| Variable | Required | Description |
|:---------|:--------:|:------------|
| `GEMINI_API_KEY` | ✅ | Google Gemini — primary LLM + image |
| `GROQ_API_KEY` | ✅ | Groq LLaMA3 fallback LLM |
| `DATABASE_URL` | ✅ | `postgresql://user:pass@host:5432/db` |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` |
| `TAVILY_API_KEY` | ⭕ | Deep web search (paid) |
| `YOUTUBE_API_KEY` | ⭕ | YouTube trending research |
| `REDDIT_CLIENT_ID` + `SECRET` | ⭕ | Reddit research |
| `GITHUB_TOKEN` | ⭕ | GitHub trending repos |
| `IMAGE_PROVIDER` | ⭕ | `pollinations` (default/free), `huggingface`, `gemini_imagen` |
| `HF_TOKEN` | ⭕ | Hugging Face token for image gen |
| `IMAGEN_MODEL` | ⭕ | Google Imagen model ID |

---

## 🎭 User Tiers

| Tier | Posts/Day | AI Images | Models | Watermark |
|:-----|:---------:|:---------:|:------:|:---------:|
| **Explorer** (Free) | 5 | 3/day | Flash | Optional removal |
| **Creator** | 50 | 25/day | Flash + Pro | No |
| **Pro** | Unlimited | Unlimited | All + Imagen | No |

---

## 🏛 Architecture

```
User Prompt
    │
    ▼
FastAPI Backend  (api/web/)
├── /chat      → LangGraph Pipeline → Gemini/Groq
├── /image     → RQ Worker → Pollinations/HF/Imagen
└── /auth      → JWT + bcrypt + PostgreSQL

React Frontend (frontend/)
├── Landing Page
├── Chat Workspace (TanStack Router)
├── Post Cards (inline editing)
└── Fabric.js Canvas Studio (direct text editing)
```

### Backend Module Map

| Path | Purpose |
|:-----|:--------|
| `api/web/app.py` | FastAPI factory, CORS, routers |
| `api/web/auth.py` | JWT issue / verify |
| `api/web/db.py` | Postgres models |
| `api/web/rate_limit.py` | SlowAPI per-tier limits |
| `generation/content_generator.py` | LLM post generation node |
| `generation/prompt_composer.py` | Viral prompt builder |
| `imaging/` | Image provider adapters |
| `research/` | Multi-source fetchers |
| `memory/` | User memory & session context |

### Frontend File Map

| Path | Purpose |
|:-----|:--------|
| `src/routes/index.tsx` | Main workspace state machine |
| `src/components/aiflick/post-modal.tsx` | Post studio modal |
| `src/components/aiflick/social-post-canvas.tsx` | Fabric.js canvas |
| `src/components/aiflick/post-card.tsx` | Chat feed cards |
| `src/components/aiflick/data.ts` | Types + cleanHumanCopy() |

---

## 🐳 Docker (Full Stack)

```bash
cp env.docker.example .env
# Set POSTGRES_PASSWORD in .env

docker compose up --build -d

# Logs
docker compose logs -f app worker image-worker
```

---

## 📦 Frontend Deployment

### Cloudflare Workers (recommended)

```bash
cd frontend
npm run build
npx wrangler deploy
```

### Vercel / Netlify Static

```bash
cd frontend && npm run build
# Deploy .output/public/
```

### Self-hosted Node SSR

```bash
cd frontend && npm run build
node .output/server/index.mjs
```

---

## 🔄 CI/CD — GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: CI/CD

on:
  push:
    branches: [main]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v

  build-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci && npm run build

  deploy-api:
    needs: test-backend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build Docker image
        run: docker build -t aiflick-api .
      - name: Deploy (Fly.io / Railway / Render)
        run: flyctl deploy --remote-only     # or your deploy command
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}

  deploy-frontend:
    needs: build-frontend
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: cd frontend && npm ci && npm run build
      - name: Deploy to Cloudflare Workers
        run: cd frontend && npx wrangler deploy
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
```

---

## 🛡 Security

- **JWT auth** — access tokens (15 min) + refresh tokens (7 days)
- **bcrypt** password hashing
- **SlowAPI rate limiting** — Explorer: 5 RPM, Creator: 60 RPM, Pro: 200 RPM
- **CORS** — origin whitelist
- **HTML escaping** — all fetched data sanitized before LLM injection
- **Prompt safety rules** — no markdown injection, no AI artifact generation

---

## 🎨 Canvas Direct Text Editing

| Action | How |
|:-------|:----|
| Edit title/hook on post | Double-click the text element |
| Sync sidebar → canvas | Type in sidebar inputs — canvas updates in <1ms (no rebuild) |
| Sync canvas → sidebar | Type on canvas — sidebar inputs update live |
| Undo / Redo | Ctrl+Z / Ctrl+Y |
| Delete element | Select + Delete key |
| Add free text | "Add Text" toolbar button |

---

## 🛠 Dev Commands

```bash
# Backend
uvicorn api.web.app:app --reload          # API server
python -m api.web.worker                  # Chat worker
python -m api.web.image_worker            # Image worker
python -m pytest tests/                   # Tests

# Frontend
cd frontend
npm run dev       # Dev server
npm run build     # Production build
npm run lint      # ESLint
npm run format    # Prettier
```

---

**AIFlick** — Used by modern creators to go from idea to post in seconds.
