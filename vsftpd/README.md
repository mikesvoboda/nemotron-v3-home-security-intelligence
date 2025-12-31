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

## Security Notes

1. **Change the default password** by setting the `FTP_PASSWORD` environment variable
2. Consider enabling SSL/TLS (FTPS) by uncommenting SSL settings in `vsftpd.conf`
3. The user is chrooted to `/export/foscam` and cannot access files outside this directory
4. Only the `ftpsecure` user is allowed to login (configured via `vsftpd.user_list`)

## File Permissions

The `/export/foscam` directory is owned by `ftpsecure:ftpsecure` with permissions `755`, allowing the user to read and write files.
