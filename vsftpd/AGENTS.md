# vsftpd Directory - Agent Guide

## Purpose

This directory contains the vsftpd (Very Secure FTP Daemon) Docker container configuration for receiving FTP uploads from Foscam security cameras. Cameras upload motion-triggered images via FTP, which are then processed by the AI detection pipeline.

## Directory Contents

```
vsftpd/
  AGENTS.md                    # This file
  README.md                    # Detailed setup and usage documentation
  Dockerfile                   # Container build definition
  entrypoint.sh                # Container startup script
  vsftpd.conf                  # vsftpd server configuration
  vsftpd.user_list             # Allowed FTP users
  install-systemd.sh           # System-level systemd service installer
  vsftpd.service               # Systemd service file (system-level)
  vsftpd-user.service          # Systemd service file (user-level with Docker)
  vsftpd-user-podman.service   # Systemd service file (user-level with Podman)
  docker-compose-wrapper.sh    # Wrapper script for user services
```

## Key Files

### Dockerfile

**Purpose:** Builds the vsftpd container image.

**Base Image:** ubuntu:22.04

**What it installs:**

- vsftpd - FTP server
- openssl - For SSL/TLS support

**What it configures:**

- Creates `/export/foscam` directory for camera uploads
- Creates secure chroot directory at `/var/run/vsftpd/empty`
- Exposes ports 21 (control), 20 (data active mode)

### entrypoint.sh

**Purpose:** Container startup script that configures the FTP environment.

**What it does:**

1. Creates `/export/foscam` directory if missing
2. Creates `ftpsecure` user if it doesn't exist
3. Sets FTP password from `FTP_PASSWORD` environment variable (default: `ftpsecure`)
4. Sets proper ownership and permissions on `/export/foscam`
5. Starts vsftpd with the configured settings

### vsftpd.conf

**Purpose:** vsftpd server configuration.

**Key Settings:**

| Setting                  | Value         | Description                        |
| ------------------------ | ------------- | ---------------------------------- |
| `local_enable`           | YES           | Allow local user login             |
| `write_enable`           | YES           | Allow file uploads                 |
| `chroot_local_user`      | YES           | Jail users to home directory       |
| `allow_writeable_chroot` | YES           | Allow writes within chroot         |
| `pasv_enable`            | YES           | Enable passive mode                |
| `pasv_min_port`          | 21100         | Passive mode port range start      |
| `pasv_max_port`          | 21110         | Passive mode port range end        |
| `pasv_address`           | 192.168.1.145 | Passive mode external IP (update!) |
| `anonymous_enable`       | NO            | Disable anonymous access           |
| `max_clients`            | 50            | Maximum concurrent connections     |
| `max_per_ip`             | 5             | Max connections per IP             |

**Note:** Update `pasv_address` to match your server's IP address.

### vsftpd.user_list

**Purpose:** Defines allowed FTP users.

**Content:** `ftpsecure` - The only allowed user for camera uploads.

### Systemd Service Files

Three service file variants for different deployment scenarios:

| File                         | Use Case                          | Container Runtime |
| ---------------------------- | --------------------------------- | ----------------- |
| `vsftpd.service`             | System-level with root Docker     | Docker            |
| `vsftpd-user.service`        | User-level with Docker group      | Docker            |
| `vsftpd-user-podman.service` | User-level with Podman (rootless) | Podman            |

## Network Ports

| Port        | Protocol | Purpose                 |
| ----------- | -------- | ----------------------- |
| 21          | TCP      | FTP control connection  |
| 20          | TCP      | FTP data (active mode)  |
| 21100-21110 | TCP      | FTP data (passive mode) |

## Usage

### Starting the FTP Server

**With Docker Compose:**

```bash
docker compose up -d vsftpd
```

**With custom password:**

```bash
FTP_PASSWORD=your_secure_password docker compose up -d vsftpd
```

**Standalone Docker:**

```bash
docker build -t vsftpd-foscam ./vsftpd
docker run -d \
  --name vsftpd \
  -p 21:21 \
  -p 20:20 \
  -p 21100-21110:21100-21110 \
  -v /export/foscam:/export/foscam \
  -e FTP_PASSWORD=your_secure_password \
  vsftpd-foscam
```

### Installing as System Service

```bash
# System-level (requires root)
sudo ./vsftpd/install-systemd.sh

# Or manually:
sudo cp vsftpd/vsftpd.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vsftpd.service
sudo systemctl start vsftpd.service
```

### Installing as User Service

**For Docker (user in docker group):**

```bash
mkdir -p ~/.config/systemd/user
cp vsftpd/vsftpd-user.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

**For Podman (rootless):**

```bash
# First, allow unprivileged ports
sudo sysctl net.ipv4.ip_unprivileged_port_start=20
# Then install service
mkdir -p ~/.config/systemd/user
cp vsftpd/vsftpd-user-podman.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

### Service Management

```bash
# System service
sudo systemctl status vsftpd
sudo systemctl restart vsftpd
sudo journalctl -u vsftpd -f

# User service
systemctl --user status vsftpd
systemctl --user restart vsftpd
journalctl --user -u vsftpd -f
```

## Camera Configuration

### Foscam Camera FTP Settings

Configure your Foscam cameras with these settings:

| Setting      | Value                                |
| ------------ | ------------------------------------ |
| FTP Server   | Your server IP (e.g., 192.168.1.145) |
| Port         | 21                                   |
| Username     | ftpsecure                            |
| Password     | (your FTP_PASSWORD)                  |
| Upload Path  | /{camera_name}/                      |
| Passive Mode | Enabled (recommended)                |

### Directory Structure

Cameras should upload to subdirectories of `/export/foscam`:

```
/export/foscam/
  front-door/
    MDAlarm_20240115_123456.jpg
    MDAlarm_20240115_123457.jpg
  backyard/
    MDAlarm_20240115_124000.jpg
  garage/
    ...
```

The file watcher service monitors these directories for new uploads.

## Security

### Implemented Protections

1. **Filesystem Isolation** - Container only has access to `/export/foscam`
2. **User Chroot** - `ftpsecure` user is jailed to `/export/foscam`
3. **Container Hardening:**
   - Only `NET_BIND_SERVICE` capability
   - Not running in privileged mode
   - `no-new-privileges` security option
4. **Resource Limits** - CPU: 1 core, Memory: 256MB

### Security Considerations

1. **FTP is unencrypted** - Enable FTPS by uncommenting SSL settings in `vsftpd.conf`
2. **Container runs as root** - Required for port 21, mitigated by isolation
3. **Default password** - Always set `FTP_PASSWORD` in production

### Enabling FTPS (Encrypted)

Uncomment these lines in `vsftpd.conf`:

```
ssl_enable=YES
rsa_cert_file=/etc/ssl/certs/vsftpd.pem
rsa_private_key_file=/etc/ssl/private/vsftpd.pem
allow_anon_ssl=NO
force_local_data_ssl=NO
force_local_logins_ssl=NO
```

Then mount SSL certificates into the container.

## Troubleshooting

### Connection Refused

1. Check container is running: `docker ps | grep vsftpd`
2. Verify ports are exposed: `netstat -tlnp | grep 21`
3. Check firewall rules allow FTP ports

### Passive Mode Failures

1. Verify `pasv_address` matches your server's external IP
2. Ensure ports 21100-21110 are exposed and firewall allows them
3. Try active mode if passive fails

### Permission Denied on Upload

1. Check `/export/foscam` ownership: `ls -la /export/foscam`
2. Verify ftpsecure user exists in container
3. Check container logs: `docker logs vsftpd`

### Service Won't Start

1. Check logs: `sudo journalctl -u vsftpd -n 50`
2. Verify Docker/Podman is running
3. Check docker-compose.yml file exists

## Related Files

- `/docker-compose.yml` - Main compose file with vsftpd service definition
- `/docker-compose.prod.yml` - Production compose file
- `/backend/services/file_watcher.py` - Service that monitors uploaded files
- `/CLAUDE.md` - Project documentation mentioning FTP camera configuration
