"""
api/ -- Public interface
===================================
The FastAPI web layer. Wraps the pipeline as HTTP endpoints.
Nothing in the pipeline imports from api/ -- the dependency only flows inward.

Usage (run from project root):
    uvicorn api.web.app:app --host 0.0.0.0 --port 8000

What lives here:
    web/app.py        -- FastAPI app, all route definitions
    web/auth.py       -- JWT auth + password hashing + verify_identity dependency (Phase 7/8)
    web/anon_trial.py -- Guest/trial usage tracking (Phase 8)
    web/db.py         -- Postgres layer: users table, chat_sessions index (Phase 7)
    web/deps.py       -- Session ID resolution (body -> cookie -> new)
    web/handlers.py   -- finalize_turn(): bridges web layer to main.dispatch_action
    web/jobs.py       -- run_slow_action(): RQ background job entry point
    web/rate_limit.py -- slowapi rate limiter, keyed by resolved identity
    web/schemas.py    -- All Pydantic request/response models
    web/worker.py     -- RQ worker process entry point
"""