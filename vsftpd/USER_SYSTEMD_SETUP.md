# User Systemd Service Setup for vsftpd

## Option 1: Add User to Docker Group (Recommended)

This allows you to use Docker without sudo:

```bash
# Add your user to the docker group (requires admin/root)
sudo usermod -aG docker $USER

# Log out and log back in for the group change to take effect
# Or run: newgrp docker

# Then use the regular docker service file
cp vsftpd/vsftpd-user.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

## Option 2: Use Wrapper Script with Sudo (Current Setup)

This uses a wrapper script that calls docker compose with sudo. You'll need to configure passwordless sudo for docker commands:

```bash
# Configure passwordless sudo for docker compose (requires admin)
sudo visudo
# Add this line (replace msvoboda with your username):
# msvoboda ALL=(ALL) NOPASSWD: /usr/bin/docker compose *

# Then install the service
cp vsftpd/vsftpd-user.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

## Option 3: Use Podman (Requires Port Configuration)

Podman works better with user services but can't bind to privileged ports (< 1024) without system configuration:

```bash
# Option 3a: Configure sysctl to allow unprivileged ports (requires root)
sudo sysctl net.ipv4.ip_unprivileged_port_start=20
sudo sh -c 'echo "net.ipv4.ip_unprivileged_port_start=20" >> /etc/sysctl.conf'

# Then use podman service file
cp vsftpd/vsftpd-user-podman.service ~/.config/systemd/user/vsftpd.service
systemctl --user daemon-reload
systemctl --user enable vsftpd.service
systemctl --user start vsftpd.service
```

## Current Status

The service is currently configured to use Option 2 (wrapper script with sudo).

**To check status:**

```bash
systemctl --user status vsftpd
```

**To view logs:**

```bash
journalctl --user -u vsftpd -f
```

**To manage the service:**

```bash
systemctl --user start vsftpd    # Start
systemctl --user stop vsftpd      # Stop
systemctl --user restart vsftpd   # Restart
systemctl --user enable vsftpd    # Enable on login
systemctl --user disable vsftpd   # Disable auto-start
```

## Troubleshooting

If the service fails:

1. Check logs: `journalctl --user -u vsftpd -n 50`
2. Verify docker is accessible: `docker ps` (or `sudo docker ps`)
3. Test the wrapper script manually: `./vsftpd/docker-compose-wrapper.sh start`
