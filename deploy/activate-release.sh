#!/bin/sh
# Update the single checkout to the desired commit before invoking this script.
set -eu
cd /home/mblanquet/Agrokbot
umask 077
# Serialize deployments; never run migrations/tests against the live volume.
exec 9>/var/lock/campo-deploy.lock
flock -n 9 || { echo 'Otro despliegue está en curso.' >&2; exit 1; }
compose() { docker compose --env-file .env --env-file deploy/production.env -p agrokbot "$@"; }
command -v node >/dev/null || { echo 'Falta Node.js para las pruebas frontend; no se activó nada.' >&2; exit 1; }
node --test tests/*.cjs
release=$(git rev-parse --short HEAD)
docker build --target test -t "agrokbot-campo:test-$release" .
docker run --rm --network none --read-only --tmpfs /tmp "agrokbot-campo:test-$release"
container=$(compose ps -q campo)
previous=''
stamp=$(date -u +%Y%m%dT%H%M%SZ)
if [ -n "$container" ]; then
  previous="agrokbot-campo:rollback-$stamp"
  docker tag "$(docker inspect --format '{{.Image}}' "$container")" "$previous"
  backup="/home/mblanquet/campo-backups/$stamp"
  mkdir -p "$backup"
  chmod 700 "$backup"
  # SQLite online backup is consistent even with WAL enabled.
  docker exec "$container" python -c 'import sqlite3; s=sqlite3.connect("/data/campo.sqlite3"); d=sqlite3.connect("/tmp/pre-deploy.sqlite3"); s.backup(d); assert d.execute("PRAGMA quick_check").fetchone()[0]=="ok"; d.close(); s.close()'
  docker cp "$container:/tmp/pre-deploy.sqlite3" "$backup/campo.sqlite3"
  cp .env "$backup/environment"
  if docker exec "$container" test -f /data/push-vapid.pem; then
    docker cp "$container:/data/push-vapid.pem" "$backup/push-vapid.pem"
  fi
  printf '%s\n' "$previous" > "$backup/image"
fi
compose build campo
if ! compose up -d --no-deps --wait --wait-timeout 90 campo; then
  echo 'Falló la activación. Se intentará recuperar la imagen anterior sin restaurar ni borrar datos.' >&2
  if [ -n "$previous" ]; then
    CAMPO_IMAGE="$previous" compose up -d --no-deps --no-build --wait --wait-timeout 90 campo
  fi
  exit 1
fi
# Keep the last rollback image and backups. No automatic destructive cleanup here.
echo "Activación verificada. Respaldo: ${backup:-no había instancia anterior}"
