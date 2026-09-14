# vsftpd Docker Container

This Docker container provides an FTP server using vsftpd, configured to allow the `ftpsecure` user to write files to `/export/foscam`.

## Configuration

- **User**: `ftpsecure`
- **Default Password**: `ftpsecure` (change via `FTP_PASSWORD` environment variable)
- **Chroot Directory**: `/export/foscam`
- **FTP Ports**:
  - Control: 21
  - Data (active): 20
  - Passive: 21100-21110

## Usage

### Using Docker Compose

The vsftpd service is included in the main `docker-compose.yml`. To start it:

```bash
docker compose up -d vsftpd
```

Set a custom password using an environment variable:

```bash
FTP_PASSWORD=your_secure_password docker compose up -d vsftpd
```

### Using Docker directly

Build the image:

```bash
docker build -t vsftpd-foscam ./vsftpd
```

Run the container:

```bash
docker run -d \
  --name vsftpd \
  -p 21:21 \
  -p 20:20 \
  -p 21100-21110:21100-21110 \
  -v /export/foscam:/export/foscam \
  -e FTP_PASSWORD=your_secure_password \
  vsftpd-foscam
```

## Connecting

Connect using any FTP client:

- **Host**: `localhost` (or your server IP)
- **Port**: `21`
- **Username**: `ftpsecure`
- **Password**: Set via `FTP_PASSWORD` environment variable (default: `ftpsecure`)
- **Mode**: Passive mode recommended

### Example using `ftp` command:

```bash
ftp localhost
# Enter username: ftpsecure
# Enter password: (your password)
```

### Example using `curl`:

```bash
curl -T localfile.txt ftp://ftpsecure:password@localhost/
```

---

## Systemd Installation (System-Level)

To enable the vsftpd Docker container to start automatically on boot:

### Installation Steps

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

### Service Management Commands

```bash
sudo systemctl start vsftpd     # Start
sudo systemctl stop vsftpd      # Stop
sudo systemctl restart vsftpd   # Restart
sudo systemctl status vsftpd    # Check status
sudo journalctl -u vsftpd -f    # View logs
sudo systemctl disable vsftpd   # Disable auto-start
```

---

## User-Level Systemd Setup

For running without root privileges:

### Option 1: Add User to Docker Group (Recommended)

```bash
# Add your user to the docker group (requires admin/root)
sudo usermod -aG docker $USER

# Log out and log back in for the group change to take effect
# Or run: newgrp docker

# Then use the user service file
cp vsftpd/vsftpd-user.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

### Option 2: Wrapper Script with Sudo

Configure passwordless sudo for docker commands:

```bash
# Configure passwordless sudo for docker compose (requires admin)
sudo visudo
# Add this line (replace username with your username):
# username ALL=(ALL) NOPASSWD: /usr/bin/docker compose *

# Then install the service
cp vsftpd/vsftpd-user.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

### Option 3: Use Podman

Podman works better with user services but can't bind to privileged ports (< 1024) without configuration:

```bash
# Configure sysctl to allow unprivileged ports (requires root)
sudo sysctl net.ipv4.ip_unprivileged_port_start=20
sudo sh -c 'echo "net.ipv4.ip_unprivileged_port_start=20" >> /etc/sysctl.conf'

# Then use podman service file
cp vsftpd/vsftpd-user-podman.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

### User Service Management

```bash
systemctl --user start vsftpd     # Start
systemctl --user stop vsftpd      # Stop
systemctl --user restart vsftpd   # Restart
systemctl --user status vsftpd    # Check status
journalctl --user -u vsftpd -f    # View logs
systemctl --user disable vsftpd   # Disable auto-start
```

---

## Security

### What is Protected

1. **Host Filesystem Isolation**

   - Only `/export/foscam` is mounted from the host
   - Container cannot access any other host directories

2. **FTP User Isolation**

   - `ftpsecure` user is chrooted to `/export/foscam` via vsftpd
   - Cannot access container filesystem or host filesystem outside the mount

3. **Container Capabilities**

   - Only `NET_BIND_SERVICE` capability (required for port 21)
   - Not running in privileged mode
   - `no-new-privileges` security option enabled

4. **Resource Limits**

   - CPU limit: 1 core
   - Memory limit: 256MB
   - Prevents resource exhaustion attacks

5. **Network Isolation**
   - Connected to isolated bridge network (`security-net`)
   - Only exposes necessary FTP ports (21, 20, 21100-21110)

### Security Considerations

1. **Container Runs as Root** - vsftpd requires root to bind to port 21. Mitigated by container isolation.

2. **FTP Protocol is Unencrypted** - Enable FTPS by uncommenting SSL settings in `vsftpd.conf`.

### Security Layers

```
┌─────────────────────────────────────────┐
│  FTP Client                             │
└──────────────┬──────────────────────────┘
               │ FTP Protocol (Port 21)
               ▼
┌─────────────────────────────────────────┐
│  Docker Container (vsftpd)              │
│  - Runs as root                         │
│  - Can only access /export/foscam       │
│  - Isolated network namespace           │
│  - Resource limits                      │
└──────────────┬──────────────────────────┘
               │ chroot to /export/foscam
               ▼
┌─────────────────────────────────────────┐
│  ftpsecure user                         │
│  - Chrooted to /export/foscam           │
│  - Can only read/write in that dir      │
└──────────────┬──────────────────────────┘
               │ Volume mount
               ▼
┌─────────────────────────────────────────┐
│  Host: /export/foscam                   │
│  - Only directory accessible to host    │
└─────────────────────────────────────────┘
```

### Production Recommendations

1. **Enable FTPS** - Uncomment SSL settings in `vsftpd.conf` and generate certificates
2. **Use Strong Password** - Set `FTP_PASSWORD` environment variable
3. **Firewall Rules** - Restrict FTP port access to trusted IPs
4. **Monitor Logs** - Review vsftpd logs regularly

### Verification Commands

```bash
# Check container capabilities
docker inspect vsftpd --format '{{.HostConfig.CapAdd}}'

# Check mounted volumes
docker inspect vsftpd --format '{{.Mounts}}'

# Check if running as root
docker exec vsftpd id

# Test FTP user chroot
docker exec vsftpd su - ftpsecure -c "pwd"
# Should show: /export/foscam
```

---

## Troubleshooting

### Service Fails to Start

1. Check the logs: `sudo journalctl -u vsftpd -n 50`
2. Verify docker is running: `sudo systemctl status docker`
3. Verify the docker-compose.yml file exists and is valid
4. Check file permissions on the working directory

### User Service Troubleshooting

1. Check logs: `journalctl --user -u vsftpd -n 50`
2. Verify docker is accessible: `docker ps` (or `sudo docker ps`)
3. Test the wrapper script manually: `./vsftpd/docker-compose-wrapper.sh start`

## File Permissions

The `/export/foscam` directory is owned by `ftpsecure:ftpsecure` with permissions `755`, allowing the user to read and write files.
