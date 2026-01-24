# Grafana Dashboard Provisioning Directory - Agent Guide

## Purpose

This directory contains Grafana dashboard provisioning configuration that defines **how** and **where** dashboards are loaded from. It configures the dashboard provider that tells Grafana to automatically import dashboard JSON files from the file system.

**Key distinction:** This directory contains _provisioning configuration_ (YAML), not dashboard definitions (JSON). The actual dashboard JSON files are in `monitoring/grafana/dashboards/`.

## Directory Contents

```
dashboards/
  AGENTS.md         # This file
  dashboard.yml     # Dashboard provider configuration
```

## Key Files

### dashboard.yml

**Purpose:** Configures automatic dashboard loading from the file system.

**File Path (in container):** `/etc/grafana/provisioning/dashboards/dashboard.yml`

**Configuration:**

```yaml
apiVersion: 1

providers:
  - name: 'Home Security Intelligence'
    orgId: 1
    folder: 'Home Security Intelligence'
    folderUid: 'hsi-dashboards'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

**Configuration Breakdown:**

| Field                       | Value                       | Description                                                               |
| --------------------------- | --------------------------- | ------------------------------------------------------------------------- |
| `apiVersion`                | 1                           | Provisioning API version                                                  |
| `name`                      | Home Security Intelligence  | Provider name (shown in Grafana logs)                                     |
| `orgId`                     | 1                           | Grafana organization ID (1 = default org)                                 |
| `folder`                    | Home Security Intelligence  | Dashboard folder name in Grafana UI                                       |
| `folderUid`                 | hsi-dashboards              | Unique folder identifier (used in URLs)                                   |
| `type`                      | file                        | Load dashboards from file system                                          |
| `disableDeletion`           | false                       | Allow deleting dashboards in UI                                           |
| `updateIntervalSeconds`     | 30                          | How often to check for changes (dashboard hot-reload)                     |
| `allowUiUpdates`            | true                        | Allow editing dashboards in UI (changes persisted to JSON files)          |
| `path`                      | /var/lib/grafana/dashboards | Container path where dashboard JSON files are located                     |
| `foldersFromFilesStructure` | false                       | All dashboards go to same folder (ignore file system directory structure) |

## How It Works

### Startup Flow

1. Grafana container starts
2. Grafana reads `/etc/grafana/provisioning/dashboards/` directory
3. `dashboard.yml` is parsed
4. Dashboard provider is registered with Grafana
5. Grafana scans `/var/lib/grafana/dashboards` for JSON files
6. Each JSON file is imported as a dashboard
7. All dashboards appear in the "Home Security Intelligence" folder

### Volume Mounting

In `docker-compose.prod.yml`:

```yaml
grafana:
  volumes:
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
```

**Host → Container mapping:**

| Host Path                                       | Container Path                          | Contents             |
| ----------------------------------------------- | --------------------------------------- | -------------------- |
| `./monitoring/grafana/provisioning/dashboards/` | `/etc/grafana/provisioning/dashboards/` | This YAML file       |
| `./monitoring/grafana/dashboards/`              | `/var/lib/grafana/dashboards/`          | Dashboard JSON files |

### Auto-Reload Behavior

- **updateIntervalSeconds: 30** means Grafana checks for changes every 30 seconds
- If a JSON file is added/modified/deleted, Grafana automatically updates
- No Grafana restart required for dashboard changes
- YAML provisioning changes require restart

### Editable vs Immutable Dashboards

**allowUiUpdates: true** means:

- Dashboards can be edited in Grafana UI
- Changes are saved back to the JSON files (if file system is writable)
- Useful for development and iterative design

**allowUiUpdates: false** would:

- Make dashboards read-only in UI
- Prevent accidental changes
- Recommended for production

## Adding a New Dashboard

### Method 1: Drop JSON File

1. Create or export dashboard JSON
2. Save to the dashboards directory (e.g., `monitoring/grafana/dashboards/`)
3. Wait 30 seconds or restart Grafana
4. Dashboard appears in "Home Security Intelligence" folder

**Example JSON structure:**

```json
{
  "title": "My Custom Dashboard",
  "uid": "my-custom-dash",
  "panels": [],
  "schemaVersion": 38
}
```

### Method 2: Create in UI, Export, Save

1. Create dashboard in Grafana UI
2. Dashboard Settings → JSON Model
3. Copy JSON content
4. Save to the dashboards directory (e.g., `monitoring/grafana/dashboards/`)
5. Dashboard is now provisioned (survives container restarts)

## Adding a New Dashboard Provider

To load dashboards from a different directory or with different settings:

1. Edit `dashboard.yml`
2. Add new provider to `providers` array:

```yaml
providers:
  - name: 'Home Security Intelligence'
    folder: 'Home Security Intelligence'
    # ... existing config ...

  - name: 'Custom Dashboards'
    orgId: 1
    folder: 'Custom'
    folderUid: 'custom-dashboards'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/custom-dashboards
```

3. Add volume mount in `docker-compose.prod.yml`:

```yaml
grafana:
  volumes:
    - ./monitoring/grafana/custom-dashboards:/var/lib/grafana/custom-dashboards
```

4. Restart Grafana: `podman-compose -f docker-compose.prod.yml restart grafana`

## Current Dashboard Inventory

Dashboards loaded by this provider (from `monitoring/grafana/dashboards/`):

| File                 | Title                                     | UID              | Purpose                           |
| -------------------- | ----------------------------------------- | ---------------- | --------------------------------- |
| `consolidated.json`  | Home Security Intelligence - Consolidated | hsi-consolidated | Main unified monitoring dashboard |
| `analytics.json`     | Home Security Intelligence - Analytics    | hsi-analytics    | Analytics metrics dashboard       |
| `hsi-profiling.json` | Home Security Intelligence - Profiling    | hsi-profiling    | Performance profiling dashboard   |
| `logs.json`          | Home Security Intelligence - Logs         | hsi-logs         | Log aggregation dashboard         |
| `tracing.json`       | Home Security Intelligence - Tracing      | hsi-tracing      | Distributed tracing dashboard     |

## Troubleshooting

### Dashboard Not Loading

**Symptom:** Dashboard JSON exists but doesn't appear in Grafana.

**Debugging steps:**

1. **Check Grafana logs for errors:**

   ```bash
   podman logs grafana | grep -i provisioning
   podman logs grafana | grep -i dashboard
   ```

2. **Verify JSON syntax:**

   ```bash
   jq . monitoring/grafana/dashboards/consolidated.json
   ```

3. **Check file permissions:**

   ```bash
   ls -la monitoring/grafana/dashboards/
   ```

   Files should be readable by Grafana (UID 472 in container).

4. **Verify volume mount:**

   ```bash
   podman exec grafana ls -la /var/lib/grafana/dashboards/
   ```

5. **Check provider path matches volume:**

   Ensure `path: /var/lib/grafana/dashboards` matches the container volume mount.

### Dashboard Shows "Provisioned" Lock Icon

**Symptom:** Dashboard has lock icon, can't be deleted or edited.

**Cause:** `allowUiUpdates: false` or `disableDeletion: true`

**Fix:** Change in `dashboard.yml`:

```yaml
allowUiUpdates: true
disableDeletion: false
```

Then restart Grafana.

### Dashboard Changes Not Persisting

**Symptom:** Edit dashboard in UI, changes disappear after refresh.

**Possible causes:**

1. Volume not writable by Grafana container
2. `allowUiUpdates: false` in config
3. SELinux denying writes (on RHEL/Fedora)

**Fix for SELinux:**

```bash
chcon -Rt svirt_sandbox_file_t monitoring/grafana/dashboards/
```

### Dashboard Not Auto-Updating

**Symptom:** Edit JSON file, changes don't appear in Grafana.

**Checks:**

1. Wait for `updateIntervalSeconds` (30s) to elapse
2. Check if Grafana detected the change:

   ```bash
   podman logs grafana --tail=50 | grep -i "file.*changed"
   ```

3. Force reload by restarting Grafana:

   ```bash
   podman-compose -f docker-compose.prod.yml restart grafana
   ```

## Configuration Best Practices

### Development Settings

```yaml
disableDeletion: false
updateIntervalSeconds: 10
allowUiUpdates: true
```

- Fast iteration
- Easy editing
- Quick feedback

### Production Settings

```yaml
disableDeletion: true
updateIntervalSeconds: 60
allowUiUpdates: false
```

- Prevent accidental changes
- Immutable infrastructure
- Configuration as code

## Related Files

- **Parent directory:** `../` - Main provisioning AGENTS.md with overview
- **Dashboard definitions:** `../../dashboards/` - Actual dashboard JSON files
- **Datasource config:** `../datasources/prometheus.yml` - Data sources used by dashboards
- **Compose file:** Root `docker-compose.prod.yml` - Volume mounts and service config

## References

- [Grafana Provisioning Documentation](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Dashboard Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/#dashboards)
- [Grafana Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/)

## Quick Commands

```bash
# Restart Grafana to apply provisioning changes
podman-compose -f docker-compose.prod.yml restart grafana

# View Grafana logs
podman logs grafana -f

# Check provisioned dashboards in container
podman exec grafana ls -la /var/lib/grafana/dashboards/

# Validate dashboard JSON syntax
jq . monitoring/grafana/dashboards/*.json

# Check provisioning config in container
podman exec grafana cat /etc/grafana/provisioning/dashboards/dashboard.yml

# Force reload by touching config
touch monitoring/grafana/provisioning/dashboards/dashboard.yml
```
