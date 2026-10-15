#!/usr/bin/env bash
# Publica Agrokbot en https://ops.agrokool.mx vía nginx + certbot. Ejecutar con sudo.
set -euo pipefail
DOMAIN=ops.agrokool.mx
EMAIL=${1:?uso: sudo $0 correo@agrokool.mx}
DIR="$(cd "$(dirname "$0")" && pwd)"

install -m 644 "$DIR/nginx-$DOMAIN.conf" /etc/nginx/sites-available/ops-agrokool
ln -sf /etc/nginx/sites-available/ops-agrokool /etc/nginx/sites-enabled/ops-agrokool
nginx -t
systemctl reload nginx

certbot --nginx -d "$DOMAIN" -m "$EMAIL" --agree-tos --no-eff-email --redirect --hsts
nginx -t && systemctl reload nginx
curl -sI "https://$DOMAIN/api/health" | head -1
