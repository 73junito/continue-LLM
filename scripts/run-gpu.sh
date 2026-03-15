#!/usr/bin/env bash
# Build and run the GPU container with docker-compose
set -euo pipefail

echo "Building and running GPU container..."
docker compose -f docker-compose.gpu.yml up --build --remove-orphans
