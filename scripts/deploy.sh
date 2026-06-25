#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

echo "=== Pulling latest changes from Git ==="
git pull --ff-only origin main

echo "=== Building image ==="
# requirements.txt is cached separately, so application-only changes do not
# reinstall Python packages.
docker compose build bot

echo "=== Updating container ==="
docker compose up -d --no-build --remove-orphans bot api

echo "=== Waiting for healthcheck ==="
timeout="${DEPLOY_HEALTH_TIMEOUT:-30}"
if [[ ! "$timeout" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: DEPLOY_HEALTH_TIMEOUT must be a positive integer"
    exit 1
fi
for service in bot api; do
    deadline=$((SECONDS + timeout))
    container_id="$(docker compose ps -q "$service")"
    if [[ -z "$container_id" ]]; then
        echo "ERROR: $service container was not created"
        exit 1
    fi

    while (( SECONDS < deadline )); do
        if docker compose exec -T "$service" python -c \
            "import urllib.request; urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:8000/health', timeout=1).read()" \
            >/dev/null 2>&1; then
            echo "$service is ready"
            break
        fi

        status="$(docker inspect --format '{{.State.Status}}' "$container_id")"
        if [[ "$status" == "exited" || "$status" == "dead" ]]; then
            echo "ERROR: $service container status is $status"
            docker compose logs --tail=100 "$service"
            exit 1
        fi
        sleep 1
    done

    if (( SECONDS >= deadline )); then
        echo "ERROR: $service healthcheck did not pass within ${timeout}s"
        docker compose ps "$service"
        docker compose logs --tail=100 "$service"
        exit 1
    fi
done

echo "=== Done ==="
