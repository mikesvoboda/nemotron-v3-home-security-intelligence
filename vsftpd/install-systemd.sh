#!/bin/bash
# Install vsftpd systemd service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_FILE="$SCRIPT_DIR/vsftpd.service"
SYSTEMD_FILE="/etc/systemd/system/vsftpd.service"

echo "Installing vsftpd systemd service..."
echo "Project directory: $PROJECT_DIR"

# Copy service file
sudo cp "$SERVICE_FILE" "$SYSTEMD_FILE"
echo "✓ Copied service file to $SYSTEMD_FILE"

# Reload systemd
sudo systemctl daemon-reload
echo "✓ Reloaded systemd daemon"

# Enable service
sudo systemctl enable vsftpd.service
echo "✓ Enabled vsftpd service"

# Check if container is already running
if docker ps --format '{{.Names}}' | grep -q "vsftpd"; then
    echo "✓ vsftpd container is already running"
else
    echo "Starting vsftpd service..."
    sudo systemctl start vsftpd.service
    echo "✓ Started vsftpd service"
fi

echo ""
echo "Installation complete!"
echo ""
echo "Service status:"
sudo systemctl status vsftpd.service --no-pager -l || true

echo ""
echo "Useful commands:"
echo "  sudo systemctl status vsftpd    - Check service status"
echo "  sudo systemctl restart vsftpd  - Restart the service"
echo "  sudo journalctl -u vsftpd -f   - View service logs"
