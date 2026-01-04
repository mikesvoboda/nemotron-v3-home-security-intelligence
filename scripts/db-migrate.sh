#!/usr/bin/env bash
# Database Migration Script
#
# Usage:
#   ./scripts/db-migrate.sh upgrade      # Run all pending migrations
#   ./scripts/db-migrate.sh downgrade    # Rollback one migration
#   ./scripts/db-migrate.sh revision     # Create new migration
#   ./scripts/db-migrate.sh current      # Show current revision
#   ./scripts/db-migrate.sh history      # Show migration history
#
# Environment:
#   DATABASE_URL - Database connection string (required for non-SQLite)
#                  SQLite: sqlite+aiosqlite:///./data/security.db
#                  PostgreSQL: postgresql+asyncpg://user:pass@host:5432/dbname

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/../backend"

# Change to backend directory for alembic
cd "$BACKEND_DIR"

# Default DATABASE_URL for local development
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="sqlite+aiosqlite:///./data/security.db"
    echo "Using default SQLite database: $DATABASE_URL"
fi

# Run alembic command
case "$1" in
    upgrade)
        echo "Running database migrations..."
        alembic upgrade head
        echo "Migrations complete."
        ;;
    downgrade)
        echo "Rolling back one migration..."
        alembic downgrade -1
        echo "Rollback complete."
        ;;
    revision)
        if [ -z "$2" ]; then
            echo "Usage: $0 revision \"migration message\""
            exit 1
        fi
        echo "Creating new migration: $2"
        alembic revision --autogenerate -m "$2"
        echo "Migration created. Review the generated file in backend/alembic/versions/"
        ;;
    current)
        echo "Current database revision:"
        alembic current
        ;;
    history)
        echo "Migration history:"
        alembic history
        ;;
    heads)
        echo "Migration heads:"
        alembic heads
        ;;
    *)
        echo "Database Migration Tool"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  upgrade     Run all pending migrations"
        echo "  downgrade   Rollback one migration"
        echo "  revision    Create new migration (requires message)"
        echo "  current     Show current database revision"
        echo "  history     Show migration history"
        echo "  heads       Show latest migrations"
        echo ""
        echo "Examples:"
        echo "  $0 upgrade"
        echo "  $0 revision \"Add user preferences table\""
        echo "  DATABASE_URL=postgresql://... $0 upgrade"
        exit 1
        ;;
esac
