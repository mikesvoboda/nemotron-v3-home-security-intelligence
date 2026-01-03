# Grafana Provisioning Directory - Agent Guide

## Purpose

This directory contains Grafana provisioning configuration files that automatically configure datasources and dashboards when Grafana starts. This enables "configuration as code" - the monitoring stack is fully reproducible without manual setup.

## Directory Structure

```
provisioning/
  AGENTS.md                  # This file
  dashboards/                # Dashboard provider configuration
    dashboard.yml            # Defines where dashboards are loaded from
  datasources/               # Datasource configuration
    prometheus.yml           # Configures Prometheus and Backend-API sources
```

## Key Files

### dashboards/dashboard.yml

**Purpose:** Configures automatic dashboard loading from the file system.

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

**Key Settings:**

| Setting                 | Value                       | Description                         |
| ----------------------- | --------------------------- | ----------------------------------- |
| `folder`                | Home Security Intelligence  | Dashboard folder name in Grafana UI |
| `folderUid`             | hsi-dashboards              | Unique folder identifier            |
| `updateIntervalSeconds` | 30                          | How often to check for changes      |
| `allowUiUpdates`        | true                        | Permits editing dashboards in UI    |
| `path`                  | /var/lib/grafana/dashboards | Container path for dashboard files  |

### datasources/prometheus.yml

**Purpose:** Configures data sources for Grafana to query.

**Datasources Defined:**

1. **Prometheus** (Default)

   ```yaml
   name: Prometheus
   type: prometheus
   url: http://prometheus:9090
   isDefault: true
   editable: false
   jsonData:
     timeInterval: '15s'
     httpMethod: POST
   ```

2. **Backend-API**
   ```yaml
   name: Backend-API
   type: marcusolsson-json-datasource
   url: http://backend:8000
   isDefault: false
   editable: false
   jsonData:
     tlsSkipVerify: true
   ```

## How Provisioning Works

### Startup Sequence

1. Grafana container starts
2. Grafana reads `/etc/grafana/provisioning/` directory
3. Datasources from `datasources/*.yml` are configured
4. Dashboard providers from `dashboards/*.yml` are registered
5. Dashboards from specified paths are imported

### File Mounting (Podman/Docker)

In docker-compose.prod.yml (this project uses Podman, not Docker):

```yaml
grafana:
  volumes:
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
    - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
```

Note: Use `podman-compose` instead of `docker compose` in all commands.

### Update Behavior

- **Datasources:** Only applied on startup (editable: false)
- **Dashboards:** Checked every 30 seconds for changes
- Changes to dashboard JSON files auto-reload
- Changes to provisioning YAML require Grafana restart

## Usage

### Adding a New Datasource

Add to `datasources/prometheus.yml`:

```yaml
- name: MySource
  type: datasource-type
  url: http://service:port
  isDefault: false
  editable: false
```

Then restart Grafana: `podman-compose -f docker-compose.prod.yml restart grafana`

### Adding a Dashboard Provider

Add to `dashboards/dashboard.yml`:

```yaml
providers:
  - name: 'Additional Dashboards'
    folder: 'Custom'
    type: file
    options:
      path: /var/lib/grafana/custom-dashboards
```

### Debugging Provisioning

1. Check Grafana logs:

   ```bash
   docker compose logs grafana | grep -i provisioning
   ```

2. Verify file permissions:

   ```bash
   docker compose exec grafana ls -la /etc/grafana/provisioning/
   ```

3. Check datasource connectivity:
   ```bash
   docker compose exec grafana wget -qO- http://prometheus:9090/-/healthy
   ```

## Important Patterns

### Datasource UID References

Dashboard panels reference datasources by UID:

```json
"datasource": {
  "type": "marcusolsson-json-datasource",
  "uid": "Backend-API"
}
```

The UID defaults to the datasource name if not specified.

### Folder Organization

```yaml
folder: 'Home Security Intelligence'
folderUid: 'hsi-dashboards'
```

### Immutable vs Editable

- `editable: false` - Datasource cannot be modified in UI
- `allowUiUpdates: true` - Dashboard changes in UI are allowed

## Troubleshooting

### Datasource Not Appearing

1. Verify YAML syntax: `yamllint datasources/prometheus.yml`
2. Check Grafana logs for errors
3. Ensure datasource type plugin is installed

### Dashboard Not Loading

1. Check provider path matches volume mount
2. Verify dashboard JSON is valid
3. Check folder permissions in container

### Connection Refused

1. Verify service is running and accessible
2. Check Docker network connectivity
3. Ensure hostname matches service name in compose file

## Required Grafana Plugins

The Backend-API datasource requires:

- `marcusolsson-json-datasource` - JSON API datasource plugin

Install via environment variable:

```yaml
grafana:
  environment:
    - GF_INSTALL_PLUGINS=marcusolsson-json-datasource
```

## Related Files

- `../../prometheus.yml` - Prometheus configuration
- `../../json-exporter-config.yml` - JSON to metrics conversion
- `../dashboards/pipeline.json` - Dashboard definitions
- `docker-compose.yml` - Service and volume definitions
