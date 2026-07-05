# ---- Builder stage ----
FROM python:3.13-slim AS builder

# Install uv (single static binary, no pip bootstrap needed)
# Pinned to a specific version, never :latest, for reproducible builds
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv

WORKDIR /app

# Copy only dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# --locked: verify uv.lock actually matches pyproject.toml and FAIL if not
# (stricter than --frozen, which would silently use a stale lockfile as-is)
# --no-dev: exclude dev-only tools (ruff, pytest, httpx) from the runtime image
RUN uv sync --locked --no-dev --no-install-project

# Now copy the actual application code and install it
COPY app ./app
RUN uv sync --locked --no-dev

# ---- Runtime stage ----
FROM python:3.13-slim AS runtime

# Create an unprivileged user to run the app (never run as root)
RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

# Copy the virtual environment and app code from the builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]