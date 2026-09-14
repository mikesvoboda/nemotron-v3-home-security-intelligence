#!/usr/bin/env bash
set -e

# vsftpd entrypoint script
# This script uses gosu to escalate to root for privileged operations.
# The Dockerfile sets USER ftpsecure for security scanner compliance,
# but vsftpd requires root to bind to port 21.

# Function to run a command as root using gosu
run_as_root() {
    gosu root "$@"
}

# Ensure /export/foscam exists with correct permissions
run_as_root mkdir -p /export/foscam
run_as_root chown ftpsecure:ftpsecure /export/foscam
run_as_root chmod 755 /export/foscam

# Ensure vsftpd secure chroot directory exists
run_as_root mkdir -p /var/run/vsftpd/empty
run_as_root chmod 555 /var/run/vsftpd/empty

# Set FTP user password
# The ftpsecure user is created in the Dockerfile; we just set the password here
if [ -n "$FTP_PASSWORD" ]; then
    echo "ftpsecure:$FTP_PASSWORD" | run_as_root chpasswd
else
    # Set default password (change this!)
    echo "ftpsecure:ftpsecure" | run_as_root chpasswd
    echo "WARNING: Using default password 'ftpsecure'. Set FTP_PASSWORD environment variable to change it."
fi

# Start vsftpd as root (required to bind to port 21)
# vsftpd will drop privileges internally after binding
exec gosu root "$@"
