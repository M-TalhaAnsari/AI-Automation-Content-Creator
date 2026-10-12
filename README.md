![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-multi--agent-1C3C3C)

# AIFlick ⚡ — AI-Powered Social Content Creator

> **Turn any trend, topic, or idea into polished, platform-ready Instagram / LinkedIn / TikTok posts in seconds — with a fully-editable visual canvas, AI background generation, and real-time copy sync.**

## At a glance

| | |
|---|---|
| **What it does** | Idea → researched, drafted, and designed social posts, end to end |
| **Pipeline** | LangGraph multi-agent research (6+ live sources) → up to 10 platform-optimized drafts per request |
| **Design layer** | Real-time editable Fabric.js canvas, sub-millisecond sidebar↔canvas text sync |
| **Image pipeline** | Async Redis/RQ job queue across 3 image providers (FLUX/Pollinations, Hugging Face, Imagen) |
| **Product shape** | 3-tier subscription model (Explorer / Creator / Pro) with per-tier rate limits |
| **Stack** | React 19 · FastAPI · LangGraph · PostgreSQL · Redis + RQ |

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
## IMAGES
![alt text](image.png)
![alt text](image-1.png)
![alt text](image-3.png)
![alt text](image-2.png)

## 🚀 Quick Start (Local Development)

### Prerequisites

- **Python 3.12+**
- **Node.js 20+**
- **Docker + Docker Compose** (for Redis & Postgres)
- At minimum: `GEMINI_API_KEY`

### 1 — Clone & configure environment

```bash
git clone https://github.com/M-TalhaAnsari/AI-Automation-Content-Creator.git
cd AI-Automation-Content-Creator
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

## 🛡 Security

- **JWT auth** — access tokens (15 min) + refresh tokens (7 days)
- **bcrypt** password hashing
- **SlowAPI rate limiting** — Explorer: 5 RPM, Creator: 60 RPM, Pro: 200 RPM
- **CORS** — origin whitelist
- **HTML escaping** — all fetched data sanitized before LLM injection
- **Prompt safety rules** — no markdown injection, no unauthorized artifact generation

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

**Author:** Muhammad Talha Ansari — [LinkedIn](https://www.linkedin.com/in/talha-ansari-504312375/) · [GitHub](https://github.com/M-TalhaAnsari)
