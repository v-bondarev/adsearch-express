#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "=== Pulling latest changes from Git ==="
git pull --rebase origin main

echo "=== Building Docker image (no cache) ==="
docker compose build --no-cache bot

echo "=== Restarting container ==="
docker compose up -d bot

echo "=== Checking health ==="
sleep 10
if docker compose ps bot | grep -q "healthy"; then
    echo "✓ Container is healthy"
else
    echo "⚠ Container may not be healthy yet, check: docker compose ps"
fi

echo "=== Done ==="