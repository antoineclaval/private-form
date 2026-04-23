# syntax=docker/dockerfile:1
# Mutual Aid Form — production container
# Build with: podman build -t mutual-aid .

FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependencies into a venv (no dev deps in prod)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY . .

# Create non-root user and data directory
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
RUN mkdir -p /app/data /app/staticfiles && chown -R appuser:appgroup /app/data /app/staticfiles

# Collect static files as root (writing to /app/staticfiles)
RUN DJANGO_SETTINGS_MODULE=mutual_aid.settings.production \
    DJANGO_SECRET_KEY=build-placeholder \
    ENCRYPTION_KEYS=Zm9vYmFyYmF6cXV4cXV4cXV4cXV4cXV4cXV4cXV4cXU= \
    PHONE_HASH_SALT=build-placeholder \
    ALLOWED_HOSTS=localhost \
    uv run python manage.py collectstatic --noinput

USER appuser

EXPOSE 8000

COPY deploy/entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
