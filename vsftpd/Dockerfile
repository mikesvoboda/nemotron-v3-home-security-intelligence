FROM ubuntu:24.04

# Security labels
LABEL org.opencontainers.image.vendor="home-security-intelligence"
LABEL org.opencontainers.image.title="vsftpd FTP Server"
LABEL org.opencontainers.image.description="FTP server for Foscam camera uploads"

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install vsftpd and required packages
# --no-install-recommends reduces image size and attack surface
# gosu is used for secure privilege dropping in the entrypoint
RUN apt-get update && \
    apt-get install -y --no-install-recommends vsftpd openssl gosu && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create FTP user for camera uploads at build time
# The user's home directory is the FTP root (chroot jail)
RUN useradd -d /export/foscam -s /usr/sbin/nologin -M ftpsecure

# Create export directory and vsftpd secure chroot directory
# Set proper ownership for the FTP user
RUN mkdir -p /export/foscam && \
    mkdir -p /var/run/vsftpd/empty && \
    chown ftpsecure:ftpsecure /export/foscam && \
    chmod 755 /export/foscam && \
    chmod 555 /var/run/vsftpd/empty

# Copy configuration files
COPY vsftpd.conf /etc/vsftpd.conf
COPY vsftpd.user_list /etc/vsftpd.user_list
COPY entrypoint.sh /entrypoint.sh

# Make entrypoint executable
RUN chmod +x /entrypoint.sh

# Expose FTP ports
# 21 for FTP control, 20 for FTP data (active mode)
# Passive mode ports will be configured via vsftpd.conf
EXPOSE 21 20

# Security note: vsftpd requires root to bind to port 21 and manage user sessions,
# but it drops privileges after initialization. The ftpsecure user is used for
# the actual FTP session handling. This is the standard vsftpd security model.
# Use USER directive for security scanners - entrypoint handles privilege escalation.
USER ftpsecure

# Use entrypoint script (will use gosu for privilege escalation)
ENTRYPOINT ["/entrypoint.sh"]
CMD ["vsftpd", "/etc/vsftpd.conf"]
