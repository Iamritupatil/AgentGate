#!/usr/bin/env bash
# Build and restart the AgentGate API on this EC2 instance. Safe to re-run:
# it syncs source, reinstalls pinned dependencies, restarts the unit and only
# reports success once the service answers on the loopback interface.
set -euo pipefail

APP_DIR="${AGENTGATE_APP_DIR:-/opt/agentgate}"
SERVICE_USER="${AGENTGATE_USER:-agentgate}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0" >&2
  exit 1
fi

echo "==> Syncing source into $APP_DIR"
if [ "$REPO_ROOT" != "$APP_DIR" ]; then
  # backend/data holds the Policy Studio store written at runtime, so it is
  # excluded here and therefore also protected from --delete.
  rsync -a --delete \
    --exclude '.git/' \
    --exclude 'node_modules/' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude 'backend/data/' \
    --exclude 'frontend/dist/' \
    "$REPO_ROOT/" "$APP_DIR/"
else
  echo "    already running from $APP_DIR, nothing to copy"
fi

VENV="$APP_DIR/backend/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  echo "==> Creating virtualenv"
  python3 -m venv "$VENV"
fi

echo "==> Installing pinned dependencies"
"$VENV/bin/pip" install --quiet --upgrade pip
# requirements.txt is exported from uv.lock with hashes, so pip refuses any
# artifact that does not match the lock the app was tested against.
"$VENV/bin/pip" install --quiet --require-hashes -r "$APP_DIR/backend/requirements.txt"

echo "==> Fixing ownership"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_DIR/backend/data"
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"

echo "==> Restarting agentgate"
systemctl restart agentgate

for _ in $(seq 1 30); do
  if curl -fsS --max-time 2 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "==> Service is answering on 127.0.0.1:8000"
    curl -fsS http://127.0.0.1:8000/health
    echo
    exit 0
  fi
  sleep 1
done

echo "The service did not become healthy within 30s. Recent log:" >&2
journalctl -u agentgate -n 40 --no-pager >&2
exit 1
