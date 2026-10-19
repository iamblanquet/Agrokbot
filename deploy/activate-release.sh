#!/bin/sh
# Update the single checkout to the desired commit before invoking this script.
set -eu
cd /home/mblanquet/Agrokbot
docker compose --env-file .env --env-file deploy/production.env -p agrokbot build campo
docker compose --env-file .env --env-file deploy/production.env -p agrokbot up -d --no-deps --wait --wait-timeout 60 campo
python3 /usr/local/sbin/campo-cleanup-releases.py --apply
