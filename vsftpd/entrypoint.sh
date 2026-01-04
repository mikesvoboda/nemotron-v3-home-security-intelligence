#!/usr/bin/env bash
set -e

# Ensure /export/foscam exists
mkdir -p /export/foscam

# Ensure vsftpd secure chroot directory exists
mkdir -p /var/run/vsftpd/empty
chmod 555 /var/run/vsftpd/empty

# Create ftpsecure user if it doesn't exist
if ! id -u ftpsecure > /dev/null 2>&1; then
    # Create user with home directory set to /export/foscam
    # This way the user will be chrooted to /export/foscam when logging in
    useradd -d /export/foscam -s /bin/bash ftpsecure
else
    # Update existing user's home directory if needed
    usermod -d /export/foscam ftpsecure
fi

# Always set password (in case it changed or user was recreated)
if [ -n "$FTP_PASSWORD" ]; then
    echo "ftpsecure:$FTP_PASSWORD" | chpasswd
else
    # Set default password (change this!)
    echo "ftpsecure:ftpsecure" | chpasswd
    echo "WARNING: Using default password 'ftpsecure'. Set FTP_PASSWORD environment variable to change it."
fi

# Set correct permissions for /export/foscam
chown -R ftpsecure:ftpsecure /export/foscam
chmod 755 /export/foscam

# Start vsftpd
exec "$@"
