#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$SCRIPT_DIR" || exit

docker compose -f docker-compose.linux.yml down
docker compose -f docker-compose.linux.yml up --build
