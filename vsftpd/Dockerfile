FROM ubuntu:22.04

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install vsftpd and required packages
RUN apt-get update && \
    apt-get install -y vsftpd openssl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Create export directory and vsftpd secure chroot directory
RUN mkdir -p /export/foscam && \
    mkdir -p /var/run/vsftpd/empty

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

# Use entrypoint script
ENTRYPOINT ["/entrypoint.sh"]
CMD ["vsftpd", "/etc/vsftpd.conf"]
