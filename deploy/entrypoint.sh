#!/bin/sh
# Container entrypoint: reads Podman secrets from files, exports as env vars,
# runs migrations, then starts gunicorn.
set -eu

# Read secrets from Podman secret mounts
export DJANGO_SECRET_KEY="$(cat /run/secrets/django_secret)"
export ENCRYPTION_KEYS="$(cat /run/secrets/encryption_keys)"
export PHONE_HASH_SALT="$(cat /run/secrets/phone_hash_salt)"

# ALLOWED_HOSTS must be set in compose.yaml environment block
: "${ALLOWED_HOSTS:?ALLOWED_HOSTS env var is required}"

export DJANGO_SETTINGS_MODULE=mutual_aid.settings.production

# Disable core dumps
ulimit -c 0

# Apply any pending migrations
python manage.py migrate --noinput

# Start gunicorn:
# --access-logfile /dev/null  → no IP addresses in access logs
# --error-logfile -           → errors go to stderr (picked up by podman logs)
# --log-level warning         → no per-request noise
exec gunicorn mutual_aid.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --worker-class sync \
    --timeout 30 \
    --access-logfile /dev/null \
    --error-logfile - \
    --log-level warning
