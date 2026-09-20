#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu EC2 instance that will serve the AgentGate
# API. The control room is not built here; Vercel builds and serves it.
#
#   sudo bash deployment/bootstrap-ec2.sh
set -euo pipefail

APP_DIR="${AGENTGATE_APP_DIR:-/opt/agentgate}"
SERVICE_USER="${AGENTGATE_USER:-agentgate}"
ENV_DIR=/etc/agentgate
ENV_FILE="$ENV_DIR/agentgate.env"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0" >&2
  exit 1
fi

echo "==> Installing system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# No Node here on purpose: the frontend is built by Vercel, so this box needs
# nothing but Python, nginx and the tools to move files around.
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl git nginx python3-venv python3-dev build-essential rsync

echo "==> Creating service user $SERVICE_USER"
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi

echo "==> Creating directories"
install -d "$APP_DIR"
install -d -m 0750 -o root -g "$SERVICE_USER" "$ENV_DIR"

if [ -f "$ENV_FILE" ]; then
  echo "    $ENV_FILE exists, leaving your settings alone"
else
  install -m 0640 -o root -g "$SERVICE_USER" \
    "$REPO_ROOT/deployment/agentgate.env.example" "$ENV_FILE"
  echo "    wrote $ENV_FILE from the example"
fi

echo "==> Installing the systemd unit"
install -m 0644 "$REPO_ROOT/deployment/agentgate.service" /etc/systemd/system/agentgate.service
systemctl daemon-reload
systemctl enable agentgate >/dev/null

echo "==> Installing the nginx vhost"
install -m 0644 "$REPO_ROOT/deployment/nginx-agentgate-api.conf" \
  /etc/nginx/sites-available/agentgate-api
ln -sfn /etc/nginx/sites-available/agentgate-api /etc/nginx/sites-enabled/agentgate-api
# The stock default site also claims default_server on port 80, so nginx
# refuses to start while both are enabled.
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> Building and starting the API"
bash "$REPO_ROOT/deployment/deploy-backend.sh"

cat <<'NEXT'

Bootstrap complete.

Next:
  1. Confirm the public API answers:
       curl -fsS http://<EC2_PUBLIC_IP>/health
  2. Point the frontend at this box, from your machine:
       cd frontend && npm run set:backend -- http://<EC2_PUBLIC_IP>
       vercel --prod
  3. Optional but recommended before sharing the link:
       sudo bash deployment/enable-tls.sh api.example.com you@example.com

Edit /etc/agentgate/agentgate.env and run `sudo systemctl restart agentgate`
to change settings.
NEXT
