"""
web/worker.py -- run this as a separate, always-on process:

    python -m web.worker

It's what actually executes run_new_request/edit_existing/targeted_refetch
jobs enqueued by web/app.py. The FastAPI process never runs the pipeline
itself -- it only enqueues work and polls status. Scale this
horizontally (multiple worker processes/containers) independently of the
web process -- that's the entire point of pulling it out.
"""
from redis import Redis
from rq import Worker, Queue

from memory.redis_session_store import REDIS_URL

if __name__ == "__main__":
    conn = Redis.from_url(REDIS_URL)
    worker = Worker([Queue("trendforge", connection=conn)], connection=conn)
    worker.work()