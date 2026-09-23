# Custom Python sandbox image with pre-installed test dependencies.
# Build:  docker build -t codecompletion-sandbox:latest .
# This speeds up container startup significantly — pip install becomes a
# no-op for all packages listed here, saving ~10-30s per test run.

FROM python:3.11-slim

# ── Environment ──────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /sandbox

# ── Pre-install packages ──────────────────────────────────────────────────────
# Covers every entry in docker_runner.py's IMPORT_TO_PACKAGE map plus common
# test utilities.  New packages needed at runtime will still be pip-installed
# inside the container, but this handles the vast majority of cases.
RUN pip install --no-cache-dir \
    # ── Test framework & plugins ─────────────────────────────────────────────
    pytest==8.3.5 \
    pytest-asyncio==0.24.0 \
    pytest-timeout==2.3.1 \
    pytest-cov==5.0.0 \
    pytest-mock==3.14.0 \
    # ── HTTP / networking ────────────────────────────────────────────────────
    requests==2.32.3 \
    httpx==0.27.2 \
    aiohttp==3.10.10 \
    # ── Web frameworks ───────────────────────────────────────────────────────
    fastapi==0.115.4 \
    starlette==0.41.2 \
    flask==3.1.0 \
    # ── Data validation ──────────────────────────────────────────────────────
    pydantic==2.9.2 \
    # ── Data science ─────────────────────────────────────────────────────────
    numpy==1.26.4 \
    pandas==2.2.3 \
    scipy==1.14.1 \
    scikit-learn==1.5.2 \
    # ── Image processing ─────────────────────────────────────────────────────
    Pillow==11.0.0 \
    # ── Database / ORM ───────────────────────────────────────────────────────
    sqlalchemy==2.0.36 \
    psycopg2-binary==2.9.10 \
    pymongo==4.10.1 \
    redis==5.2.0 \
    # ── AWS / cloud ──────────────────────────────────────────────────────────
    boto3==1.35.56 \
    # ── Task queues ──────────────────────────────────────────────────────────
    celery==5.4.0 \
    # ── Auth / security ──────────────────────────────────────────────────────
    PyJWT==2.10.0 \
    cryptography==43.0.3 \
    # ── Config / serialisation ───────────────────────────────────────────────
    python-dotenv==1.0.1 \
    pyyaml==6.0.2 \
    # ── Web scraping ─────────────────────────────────────────────────────────
    beautifulsoup4==4.12.3 \
    lxml==5.3.0

# ── Non-root user for security ────────────────────────────────────────────────
RUN useradd -m -u 1000 sandbox && \
    chown -R sandbox:sandbox /sandbox

USER sandbox

CMD ["/bin/bash"]
