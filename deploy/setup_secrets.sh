#!/bin/sh
# Run once on a fresh VPS to generate and store secrets.
# The secrets/ directory is gitignored — it lives only on the server.
#
# Usage: sh deploy/setup_secrets.sh
set -eu

SECRETS_DIR="$(dirname "$0")/../secrets"
mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

echo "Generating secrets in $SECRETS_DIR ..."

# Django secret key (50 random chars from safe alphabet)
python3 -c "
import secrets, string
chars = string.ascii_letters + string.digits + '!@#\$%^&*(-_=+)'
print(secrets.choice(chars) * 0 + ''.join(secrets.choice(chars) for _ in range(50)))
" > "$SECRETS_DIR/django_secret.txt"

# Fernet encryption key (URL-safe base64, 32 bytes)
python3 -c "
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
" > "$SECRETS_DIR/encryption_keys.txt"

# Phone hash salt (32 random bytes, hex-encoded)
python3 -c "
import secrets
print(secrets.token_hex(32))
" > "$SECRETS_DIR/phone_hash_salt.txt"

# Files must be world-readable so the container's non-root `appuser` can read
# them through the bind mount. Host-level protection comes from the 700 dir
# above — other host users can't traverse into secrets/ to reach the files.
chmod 644 "$SECRETS_DIR"/*.txt

echo ""
echo "Secrets written to $SECRETS_DIR/"
echo "  django_secret.txt"
echo "  encryption_keys.txt   ← BACK THIS UP SEPARATELY. Losing it means losing all PII."
echo "  phone_hash_salt.txt"
echo ""
echo "To add encryption key rotation later:"
echo "  1. Generate a new Fernet key"
echo "  2. Prepend it to encryption_keys.txt (comma-separated, newest first)"
echo "  3. Restart the container"
echo "  4. Run: podman exec web python manage.py rotate_encryption"
echo "  5. Remove the old key from encryption_keys.txt"
echo "  6. Restart the container again"
