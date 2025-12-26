#!/bin/bash
#
# Redis Server Startup Script
# Called by ServiceHealthMonitor for auto-recovery
#
# Usually managed by systemd, but this script allows manual control
#
# Port: 6379 (default)
#

set -e

PORT="${REDIS_PORT:-6379}"
HOST="${REDIS_HOST:-127.0.0.1}"
LOG_FILE="/tmp/redis.log"
STARTUP_TIMEOUT=10

# Check if already running
if redis-cli -h "$HOST" -p "$PORT" ping > /dev/null 2>&1; then
    echo "Redis already running on $HOST:$PORT"
    exit 0
fi

# Check if redis-server is available
if ! command -v redis-server > /dev/null 2>&1; then
    echo "ERROR: redis-server not found in PATH"
    echo "Install Redis or ensure it's in your PATH"
    exit 1
fi

echo "Starting Redis server..."
echo "Host: $HOST:$PORT"
echo "Log file: $LOG_FILE"

# Check if systemd is managing Redis
if systemctl is-active --quiet redis 2>/dev/null || systemctl is-active --quiet redis-server 2>/dev/null; then
    echo "Redis is managed by systemd. Attempting systemd restart..."
    if sudo systemctl start redis 2>/dev/null || sudo systemctl start redis-server 2>/dev/null; then
        sleep 2
        if redis-cli -h "$HOST" -p "$PORT" ping > /dev/null 2>&1; then
            echo "Redis started successfully via systemd"
            exit 0
        fi
    fi
    echo "WARNING: systemd start failed, falling back to direct start"
fi

# Start Redis directly with daemonize option
redis-server --daemonize yes --port "$PORT" --bind "$HOST" --logfile "$LOG_FILE" 2>/dev/null || {
    # If bind to specific host fails, try all interfaces
    redis-server --daemonize yes --port "$PORT" --logfile "$LOG_FILE"
}

# Wait for Redis to be ready
echo "Waiting for Redis to be ready (max ${STARTUP_TIMEOUT}s)..."
for i in $(seq 1 $STARTUP_TIMEOUT); do
    if redis-cli -h "$HOST" -p "$PORT" ping > /dev/null 2>&1; then
        echo "Redis started successfully on $HOST:$PORT"
        exit 0
    fi
    sleep 1
done

echo "ERROR: Redis failed to start within ${STARTUP_TIMEOUT} seconds"
echo "Last 20 lines of log:"
tail -20 "$LOG_FILE" 2>/dev/null || true
exit 1
