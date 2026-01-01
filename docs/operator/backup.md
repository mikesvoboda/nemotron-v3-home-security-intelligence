# Backup and Recovery

> Comprehensive guide for protecting your security data and recovering from failures.

**Time to read:** ~10 min
**Prerequisites:** [Container Setup](../DOCKER_DEPLOYMENT.md)

---

## What to Back Up

The Home Security Intelligence system stores data in multiple locations:

| Data Type              | Location                         | Priority     |
| ---------------------- | -------------------------------- | ------------ |
| PostgreSQL Database    | `postgres_data` volume           | **Critical** |
| Detection Images/Clips | `./backend/data/`                | **High**     |
| Configuration          | `.env`                           | **Critical** |
| Camera FTP Uploads     | `${CAMERA_PATH:-/export/foscam}` | **Medium**   |

> [!NOTE]
> Redis is ephemeral cache - it does **not** require backup.

### Database Tables

| Table                | Description                      |
| -------------------- | -------------------------------- |
| `cameras`            | Camera configuration and status  |
| `events`             | Security events with AI analysis |
| `detections`         | Object detection results         |
| `alerts`             | Alert history and status         |
| `alert_rules`        | User-defined alert rules         |
| `zones`              | Camera zone definitions          |
| `activity_baselines` | Anomaly detection baselines      |
| `class_baselines`    | Object class frequency baselines |
| `audit_logs`         | Security audit trail             |
| `gpu_stats`          | GPU performance history          |
| `api_keys`           | API authentication keys          |

---

## Quick Backup Commands

### Database Backup

```bash
# Docker - compressed custom format (recommended)
docker exec postgres pg_dump -U security -d security \
    --format=custom --compress=9 \
    > backup_$(date +%Y%m%d).dump

# Podman
podman exec postgres pg_dump -U security -d security \
    --format=custom --compress=9 \
    > backup_$(date +%Y%m%d).dump

# Plain SQL format
docker exec postgres pg_dump -U security security > backup.sql
```

### File Backup

```bash
# Full data directory
tar -czvf files_$(date +%Y%m%d).tar.gz backend/data/

# Clips only (most important)
tar -czvf clips_$(date +%Y%m%d).tar.gz backend/data/clips/
```

### Configuration Backup

```bash
# Save .env and any customizations
cp .env .env.backup_$(date +%Y%m%d)
```

---

## Daily Automated Backup

Create `/opt/hsi-backup/backup.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/opt/hsi-backup/daily"
RETENTION_DAYS=30
DATE=$(date +%Y-%m-%d_%H%M%S)
PROJECT_DIR="/path/to/nemotron-v3-home-security-intelligence"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup..."

# Database
docker exec postgres pg_dump -U security -d security \
    --format=custom --compress=9 \
    > "${BACKUP_DIR}/database_${DATE}.dump"

# Files
tar -czf "${BACKUP_DIR}/files_${DATE}.tar.gz" \
    -C "${PROJECT_DIR}/backend" data/ \
    --exclude='data/logs/*.log.*'

# Config
tar -czf "${BACKUP_DIR}/config_${DATE}.tar.gz" \
    -C "${PROJECT_DIR}" .env

# Cleanup old backups
find "${BACKUP_DIR}" -name "*.dump" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "*.tar.gz" -mtime +${RETENTION_DAYS} -delete

echo "[$(date)] Backup complete"
```

Schedule with cron:

```bash
chmod +x /opt/hsi-backup/backup.sh

# Add to crontab - runs daily at 2 AM
0 2 * * * /opt/hsi-backup/backup.sh >> /var/log/hsi-backup.log 2>&1
```

---

## Recovery Procedures

### Full System Recovery

**Estimated time:** 30-60 minutes

1. **Install prerequisites and clone repo**

   ```bash
   git clone https://github.com/mikesvoboda/nemotron-v3-home-security-intelligence.git
   cd nemotron-v3-home-security-intelligence
   ```

2. **Restore configuration**

   ```bash
   tar -xzf config_backup.tar.gz
   ```

3. **Start database**

   ```bash
   docker compose -f docker-compose.prod.yml up -d postgres redis
   # Wait for healthy
   docker compose -f docker-compose.prod.yml ps
   ```

4. **Restore database**

   ```bash
   docker exec -i postgres pg_restore \
       -U security -d security --clean --if-exists \
       < backup.dump
   ```

5. **Restore files**

   ```bash
   tar -xzf files_backup.tar.gz -C backend/
   chown -R 1000:1000 backend/data/
   ```

6. **Start all services**

   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

7. **Verify**
   ```bash
   curl http://localhost:8000/api/system/health/ready
   docker exec postgres psql -U security -d security -c "SELECT COUNT(*) FROM events;"
   ```

### Database-Only Recovery

```bash
# Stop backend
docker compose -f docker-compose.prod.yml stop backend

# Drop and recreate database
docker exec postgres psql -U security -c "DROP DATABASE security;"
docker exec postgres psql -U security -c "CREATE DATABASE security;"

# Restore
docker exec -i postgres pg_restore -U security -d security < backup.dump

# Restart
docker compose -f docker-compose.prod.yml up -d backend
```

### File-Only Recovery

```bash
docker compose -f docker-compose.prod.yml stop backend
tar -xzf files_backup.tar.gz -C backend/
chown -R 1000:1000 backend/data/
docker compose -f docker-compose.prod.yml up -d backend
```

---

## Disaster Recovery Checklist

### Pre-Recovery

- [ ] Backup files accessible and verified
- [ ] New server meets requirements
- [ ] Docker/Podman + NVIDIA Container Toolkit installed
- [ ] Sufficient storage space

### Recovery Steps

- [ ] Clone repository
- [ ] Restore `.env` configuration
- [ ] Start PostgreSQL and Redis
- [ ] Verify database containers healthy
- [ ] Restore database from backup
- [ ] Restore file backups
- [ ] Fix file permissions
- [ ] Start all services
- [ ] Verify all containers healthy

### Post-Recovery Verification

- [ ] API health check: `curl localhost:8000/api/system/health/ready`
- [ ] Frontend loads: `curl localhost:5173`
- [ ] Event count matches expected
- [ ] Camera list correct
- [ ] Detection images load
- [ ] Alert rules present

---

## Backup Verification

Test backups regularly:

```bash
# Verify backup structure
pg_restore --list backup.dump > /dev/null && echo "OK"

# Check backup size (should be > 1KB)
ls -lh backup.dump
```

---

## Offsite Backup

For disaster recovery, store backups offsite:

```bash
# AWS S3
aws s3 sync /opt/hsi-backup/ s3://your-bucket/hsi-backups/

# rsync to remote server
rsync -avz /opt/hsi-backup/ user@remote:/backups/hsi/
```

---

## Recovery Testing

> [!IMPORTANT]
> Test your recovery procedures monthly. An untested backup is not a backup.

1. Create a test environment (VM or separate server)
2. Restore from backup following full recovery procedure
3. Verify data integrity and functionality
4. Document results
5. Destroy test environment

---

## Next Steps

- [Database Management](database.md) - PostgreSQL setup and maintenance
- [Data Model](../developer/data-model.md) - Understanding what is backed up

---

## See Also

- [Database Troubleshooting](../reference/troubleshooting/database-issues.md) - Solve PostgreSQL problems
- [Environment Variable Reference](../reference/config/env-reference.md) - Retention configuration

---

[Back to Operator Hub](../operator-hub.md)
