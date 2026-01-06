# vsftpd FTP Server
# Receives camera uploads from Foscam cameras via FTP
# Port: 21 (control), 20 (data active), 21100-21110 (data passive)

# Use specific image tag for reproducibility (LTS release)
FROM ubuntu:22.04

# OCI labels for security and metadata
LABEL org.opencontainers.image.title="vsftpd FTP Server"
LABEL org.opencontainers.image.description="FTP server for receiving Foscam camera uploads"
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.source="https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence"
LABEL org.opencontainers.image.licenses="MIT"

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install vsftpd and required packages in a single layer
# netcat-openbsd is used for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        vsftpd \
        openssl \
        netcat-openbsd && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create export directory and vsftpd secure chroot directory
RUN mkdir -p /export/foscam && \
    mkdir -p /var/run/vsftpd/empty && \
    chmod 555 /var/run/vsftpd/empty

# Copy configuration files using COPY (not ADD)
COPY vsftpd.conf /etc/vsftpd.conf
COPY vsftpd.user_list /etc/vsftpd.user_list
COPY entrypoint.sh /entrypoint.sh

# Set appropriate permissions for entrypoint
RUN chmod 755 /entrypoint.sh

# Expose FTP ports
# 21 for FTP control, 20 for FTP data (active mode)
# Passive mode ports (21100-21110) configured via vsftpd.conf
EXPOSE 21 20

# Health check - verify vsftpd is accepting connections
# Uses netcat to check if port 21 is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD nc -z localhost 21 || exit 1

# Note: vsftpd requires root to bind to privileged ports and manage user authentication
# The entrypoint creates a chrooted ftpsecure user for FTP operations
# This is standard practice for FTP servers

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
CMD ["vsftpd", "/etc/vsftpd.conf"]
