#!/bin/bash
set -e

# Entrypoint wrapper that starts both Pyroscope server and py-spy profiler
# The profiler runs in the background and pushes profiles to Pyroscope

echo "[entrypoint] Starting py-spy profiler in background..."
# Profiler needs to run as root for ptrace access
# Use nohup to detach from terminal
nohup /usr/local/bin/profiler.sh >> /var/log/profiler.log 2>&1 &

echo "[entrypoint] Starting Pyroscope server..."
# Start Pyroscope server as main process
# Pass through any command line arguments
exec /usr/bin/pyroscope "$@"
