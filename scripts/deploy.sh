#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "=== Pulling latest changes from Git ==="
git pull --rebase origin main

echo "=== Building Docker image ==="
docker compose build --pull bot

echo "=== Restarting container ==="
docker compose up -d --force-recreate bot

echo "=== Checking health ==="
sleep 5
if docker compose ps bot | grep -q "healthy"; then
    echo "✓ Container is healthy"
else
    echo "⚠ Container may not be healthy yet, check: docker compose ps"
fi

echo "=== Done ==="