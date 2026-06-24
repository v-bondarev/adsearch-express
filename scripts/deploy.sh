#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

echo "=== Pulling latest changes from Git ==="
git pull --ff-only origin main

echo "=== Building and updating container ==="
# Compose builds the new image before replacing the running container.
# Docker layer cache keeps dependency installation and unchanged layers fast.
docker compose up -d --build --remove-orphans bot

container_id="$(docker compose ps -q bot)"
if [[ -z "$container_id" ]]; then
    echo "ERROR: bot container was not created"
    exit 1
fi

echo "=== Waiting for healthcheck ==="
timeout="${DEPLOY_HEALTH_TIMEOUT:-30}"
if [[ ! "$timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: DEPLOY_HEALTH_TIMEOUT must be a positive integer"
    exit 1
fi
deadline=$((SECONDS + timeout))

while (( SECONDS < deadline )); do
    if docker compose exec -T bot python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=1).read()" \
        >/dev/null 2>&1; then
        echo "Application is ready"
        echo "=== Done ==="
        exit 0
    fi

    status="$(docker inspect --format '{{.State.Status}}' "$container_id")"
    if [[ "$status" == "exited" || "$status" == "dead" ]]; then
        echo "ERROR: container status is $status"
        docker compose logs --tail=100 bot
        exit 1
    fi
    sleep 1
done

echo "ERROR: healthcheck did not pass within ${timeout}s"
docker compose ps bot
docker compose logs --tail=100 bot
exit 1
