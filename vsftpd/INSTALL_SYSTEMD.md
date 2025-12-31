# Installing vsftpd Systemd Service

To enable the vsftpd Docker container to start automatically on boot, follow these steps:

## Installation Steps

1. **Copy the service file to systemd directory:**

   ```bash
   sudo cp vsftpd/vsftpd.service /etc/systemd/system/vsftpd.service
   ```

2. **Reload systemd to recognize the new service:**

   ```bash
   sudo systemctl daemon-reload
   ```

3. **Enable the service to start on boot:**

   ```bash
   sudo systemctl enable vsftpd.service
   ```

4. **Start the service (optional - to start it now):**

   ```bash
   sudo systemctl start vsftpd.service
   ```

5. **Verify the service is running:**
   ```bash
   sudo systemctl status vsftpd.service
   ```

## Service Management Commands

- **Start the service:**

  ```bash
  sudo systemctl start vsftpd
  ```

- **Stop the service:**

  ```bash
  sudo systemctl stop vsftpd
  ```

- **Restart the service:**

  ```bash
  sudo systemctl restart vsftpd
  ```

- **Check service status:**

  ```bash
  sudo systemctl status vsftpd
  ```

- **View service logs:**

  ```bash
  sudo journalctl -u vsftpd -f
  ```

- **Disable auto-start (if needed):**
  ```bash
  sudo systemctl disable vsftpd
  ```

## Service Configuration

The service file is configured to:

- Start the vsftpd container automatically on boot
- Restart the container if it fails
- Stop the container gracefully on shutdown
- Work directory: `/home/msvoboda/github/nemotron-v3-home-security-intelligence`
- Uses `docker compose` to manage the container

## Troubleshooting

If the service fails to start:

1. Check the logs: `sudo journalctl -u vsftpd -n 50`
2. Verify docker is running: `sudo systemctl status docker`
3. Verify the docker-compose.yml file exists and is valid
4. Check file permissions on the working directory
