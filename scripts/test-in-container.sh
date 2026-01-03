#!/bin/bash
set -e

# Container-first integration testing script
# Usage: ./scripts/test-in-container.sh [pytest args]

COMPOSE_FILE="docker-compose.test.yml"

echo "=== Starting test containers ==="
docker compose -f "$COMPOSE_FILE" up -d postgres-test redis-test

echo "=== Waiting for services to be healthy ==="
docker compose -f "$COMPOSE_FILE" ps

# Wait for postgres
until docker compose -f "$COMPOSE_FILE" exec -T postgres-test pg_isready -U security_test; do
  echo "Waiting for postgres..."
  sleep 2
done

# Wait for redis
until docker compose -f "$COMPOSE_FILE" exec -T redis-test redis-cli ping; do
  echo "Waiting for redis..."
  sleep 2
done

echo "=== Running tests ==="
DATABASE_URL="postgresql+asyncpg://security_test:test_password@localhost:5433/security_test" \
REDIS_URL="redis://localhost:6380/0" \
uv run pytest "${@:-backend/tests/integration/ -v}"

EXIT_CODE=$?

echo "=== Stopping test containers ==="
docker compose -f "$COMPOSE_FILE" down

exit $EXIT_CODE
