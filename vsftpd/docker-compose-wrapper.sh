#!/bin/bash
# Wrapper script to run docker compose with sudo for user systemd service

set -e

COMPOSE_FILE="$HOME/github/nemotron-v3-home-security-intelligence/docker-compose.yml"
WORK_DIR="$HOME/github/nemotron-v3-home-security-intelligence"

cd "$WORK_DIR"

case "$1" in
    start|up)
        sudo /usr/bin/docker compose -f "$COMPOSE_FILE" up -d vsftpd
        ;;
    stop)
        sudo /usr/bin/docker compose -f "$COMPOSE_FILE" stop vsftpd
        ;;
    restart)
        sudo /usr/bin/docker compose -f "$COMPOSE_FILE" restart vsftpd
        ;;
    *)
        echo "Usage: $0 {start|stop|restart}"
        exit 1
        ;;
esac
