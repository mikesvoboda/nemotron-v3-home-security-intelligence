# vsftpd Container Security Model

## Current Security Posture

### ✅ What is Protected

1. **Host Filesystem Isolation**

   - Only `/export/foscam` is mounted from the host
   - Container cannot access any other host directories
   - Volume mount is read-write (required for FTP uploads)

2. **FTP User Isolation**

   - `ftpsecure` user is chrooted to `/export/foscam` via vsftpd
   - When logged in via FTP, user can only see `/export/foscam`
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

### ⚠️ Security Considerations

1. **Container Runs as Root**

   - vsftpd requires root to bind to port 21
   - If container is compromised, attacker has root inside container
   - **Mitigation**: Container is isolated from host except `/export/foscam`

2. **Container Filesystem is Writable**

   - Root filesystem inside container is writable
   - vsftpd needs to write logs and potentially other files
   - **Mitigation**: Container filesystem is isolated from host

3. **FTP Protocol is Unencrypted**
   - Default configuration uses plain FTP (not FTPS)
   - Credentials and data transmitted in plaintext
   - **Mitigation**: Can enable FTPS by uncommenting SSL settings in `vsftpd.conf`

## Security Layers

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
               │
               │ chroot to /export/foscam
               ▼
┌─────────────────────────────────────────┐
│  ftpsecure user                         │
│  - Chrooted to /export/foscam           │
│  - Can only read/write in that dir      │
└──────────────┬──────────────────────────┘
               │
               │ Volume mount
               ▼
┌─────────────────────────────────────────┐
│  Host: /export/foscam                   │
│  - Only directory accessible to host    │
└─────────────────────────────────────────┘
```

## Recommendations

### For Production Use

1. **Enable FTPS (FTP over SSL/TLS)**

   - Uncomment SSL settings in `vsftpd.conf`
   - Generate SSL certificates
   - Force encrypted connections

2. **Use Strong Password**

   - Set `FTP_PASSWORD` environment variable
   - Use a strong, unique password
   - Consider rotating passwords regularly

3. **Firewall Rules**

   - Restrict FTP port access to trusted IPs
   - Consider using a VPN or SSH tunnel for remote access

4. **Monitor Logs**

   - Review vsftpd logs regularly
   - Set up alerts for failed login attempts

5. **File Permissions**
   - Ensure `/export/foscam` has appropriate permissions on host
   - Consider using separate directories for different purposes

## Verification

To verify the security configuration:

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

## Summary

**Answer to your question**: Yes, the Docker container is restricted from the rest of the system. The only access it has to the host is read/write access to `/export/foscam`. The FTP user is further restricted via chroot to only see `/export/foscam` when logged in.

The container itself runs as root (required for vsftpd), but:

- It's not privileged
- It has minimal capabilities
- It's isolated from the host filesystem except for the mounted directory
- Resource limits prevent abuse
- The FTP user is chrooted for additional security
