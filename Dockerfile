# Single-stage, not multi-stage: nothing in this project's dependency
# set needs a heavy build toolchain discarded afterward (no compiled
# C/Rust extensions without prebuilt wheels for linux/amd64 + py3.12 --
# pydantic-core, protobuf, etc. all ship manylinux wheels). Multi-stage
# would add complexity for no real image-size or build-time win here;
# revisit only if that assumption turns out wrong.
FROM python:3.12-slim

WORKDIR /app

# Install dependencies first, separately from the app code, so Docker's
# layer cache only re-runs pip install when requirements.txt itself
# changes -- not on every code edit.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# No CMD here on purpose -- docker-compose.yml supplies a different
# command per service (uvicorn for `app`, `python -m web.worker` for
# `worker`) from this SAME image, per the master doc's explicit
# requirement not to build two separate images without a concrete
# reason to.
