"""
web/worker.py -- run this as a separate, always-on process:

    python -m web.worker

It's what actually executes run_new_request/edit_existing/targeted_refetch
jobs enqueued by web/app.py. The FastAPI process never runs the pipeline
itself -- it only enqueues work and polls status. Scale this
horizontally (multiple worker processes/containers) independently of the
web process -- that's the entire point of pulling it out.
"""
import os

from redis import Redis
from rq import Queue

from memory.redis_session_store import REDIS_URL

if __name__ == "__main__":
    conn = Redis.from_url(REDIS_URL)
    queue = Queue("trendforge", connection=conn)

    if os.name == "nt":
        # RQ's default Worker forks a child process per job (os.fork()),
        # which doesn't exist on Windows at all. SimpleWorker runs each
        # job in the worker's own process instead -- no crash isolation
        # between jobs, but it's the only worker class Windows can run.
        # Fine for local dev; deploy on Linux and the branch below (the
        # real, process-isolated Worker) is what actually runs.
        from rq import SimpleWorker
        worker = SimpleWorker([queue], connection=conn)
    else:
        from rq import Worker
        worker = Worker([queue], connection=conn)

    worker.work()