#!/bin/sh
# Container entrypoint: reads Podman secrets from files, exports as env vars,
# runs migrations, then starts gunicorn.
set -eu

# Read secrets from Podman secret mounts. Fail loudly if unreadable — `set -e`
# does NOT trigger on command-substitution failures inside assignments, so a
# permission error on `cat` would otherwise silently export an empty string.
read_secret() {
    [ -r "$1" ] || { echo "entrypoint: cannot read $1 (permission or missing file)" >&2; exit 1; }
    cat "$1"
}
DJANGO_SECRET_KEY="$(read_secret /run/secrets/django_secret)"
ENCRYPTION_KEYS="$(read_secret /run/secrets/encryption_keys)"
PHONE_HASH_SALT="$(read_secret /run/secrets/phone_hash_salt)"
export DJANGO_SECRET_KEY ENCRYPTION_KEYS PHONE_HASH_SALT

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
