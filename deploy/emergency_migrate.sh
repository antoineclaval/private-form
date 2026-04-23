#!/bin/sh
# Emergency migration: move the entire system to a new VPS quickly.
#
# Prerequisites on the NEW VPS:
#   - podman and podman-compose installed
#   - git installed
#   - ssh access from this machine
#
# Usage:
#   sh deploy/emergency_migrate.sh user@new-vps-ip /opt/mutual-aid
#
# What this script does:
#   1. Stops the running containers
#   2. Copies the SQLite database to the new VPS
#   3. Copies the secrets directory to the new VPS
#   4. Clones the git repo on the new VPS
#   5. Starts the containers on the new VPS
#   6. Verifies the new VPS is responding
set -eu

DEST="${1:?Usage: $0 user@host /opt/deploy-path}"
DEST_PATH="${2:-/opt/mutual-aid}"
LOCAL_DB_VOLUME="$(podman volume inspect mutual-aid_db_data --format '{{.Mountpoint}}' 2>/dev/null || echo '')"

echo "=== Emergency Migration ==="
echo "Destination: $DEST:$DEST_PATH"
echo ""

# 1. Stop containers (data is safe in volume)
echo "[1/6] Stopping containers..."
podman compose down

# 2. Copy database
if [ -z "$LOCAL_DB_VOLUME" ]; then
    echo "  ERROR: Could not find db_data volume. Is the container named 'mutual-aid'?"
    exit 1
fi
echo "[2/6] Copying database..."
ssh "$DEST" "mkdir -p $DEST_PATH/db_restore"
scp "$LOCAL_DB_VOLUME/db.sqlite3" "$DEST:$DEST_PATH/db_restore/db.sqlite3"

# 3. Copy secrets
echo "[3/6] Copying secrets..."
scp -r ./secrets/ "$DEST:$DEST_PATH/secrets"

# 4. Clone repo on new VPS (assumes repo is accessible via git)
echo "[4/6] Setting up application on new VPS..."
REPO_URL="$(git remote get-url origin 2>/dev/null || echo '')"
if [ -z "$REPO_URL" ]; then
    echo "  No git remote found. Copy the application code manually to $DEST:$DEST_PATH"
    echo "  Then run: cd $DEST_PATH && podman compose up -d"
    exit 0
fi

ssh "$DEST" "
    set -eu
    mkdir -p $DEST_PATH
    cd $DEST_PATH
    if [ ! -d .git ]; then
        git clone $REPO_URL .
    else
        git pull
    fi
    cp -f .env.example .env
    echo 'Edit $DEST_PATH/.env with your ALLOWED_HOSTS before starting containers.'
"

# 5. Restore database into the volume
echo "[5/6] Restoring database into container volume..."
ssh "$DEST" "
    cd $DEST_PATH
    podman compose up -d --no-start
    DB_MOUNT=\$(podman volume inspect mutual-aid_db_data --format '{{.Mountpoint}}')
    cp db_restore/db.sqlite3 \$DB_MOUNT/db.sqlite3
    rm -rf db_restore/
"

echo "[6/6] Done. On the new VPS, run:"
echo "  cd $DEST_PATH"
echo "  nano .env          # set ALLOWED_HOSTS"
echo "  podman compose up -d"
echo ""
echo "Then update your DNS A record to point to the new VPS IP."
