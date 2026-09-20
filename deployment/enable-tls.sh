#!/usr/bin/env bash
# Put a Let's Encrypt certificate on the API host.
#
#   sudo bash deployment/enable-tls.sh api.example.com you@example.com
#
# The DNS A record for the domain must already point at this instance's public
# IP, and port 80 must be reachable, or the HTTP-01 challenge fails.
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
VHOST=/etc/nginx/sites-available/agentgate-api

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "Usage: sudo bash $0 <domain> <email>" >&2
  exit 1
fi
if [ "$(id -u)" -ne 0 ]; then
  echo "Run with sudo: sudo bash $0 $DOMAIN $EMAIL" >&2
  exit 1
fi
if [ ! -f "$VHOST" ]; then
  echo "$VHOST is missing. Run deployment/bootstrap-ec2.sh first." >&2
  exit 1
fi

echo "==> Resolving $DOMAIN"
if ! getent hosts "$DOMAIN" >/dev/null; then
  echo "$DOMAIN does not resolve yet. Add the A record and retry." >&2
  exit 1
fi

echo "==> Installing certbot"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends certbot python3-certbot-nginx

echo "==> Claiming $DOMAIN in the vhost"
# certbot picks a vhost by server_name, so the catch-all has to become the real
# name first. Matching any current value keeps this re-runnable.
sed -i -E "s/^([[:space:]]*)server_name .*;/\1server_name ${DOMAIN};/" "$VHOST"
nginx -t
systemctl reload nginx

echo "==> Requesting the certificate"
certbot --nginx -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive --redirect

systemctl reload nginx

cat <<NEXT

TLS is live on https://${DOMAIN}.

Certbot added an HTTP-to-HTTPS redirect. A redirect is not followed by the
Vercel proxy on a POST, so the frontend must now be pointed at the https URL:

    cd frontend
    npm run set:backend -- https://${DOMAIN}
    vercel --prod

Renewal is handled by the certbot systemd timer. Check it with:

    systemctl list-timers 'certbot*'
NEXT
