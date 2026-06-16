# Backend image for the AURA FastAPI service.
# Python pinned to match runtime.txt (3.11).
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# System deps: build tools for any sdist-only wheels, libpq for psycopg, curl for healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# App source.
COPY . .

EXPOSE 8080

# start.sh runs alembic migrations (tolerant) then launches uvicorn on $PORT.
CMD ["bash", "start.sh"]
