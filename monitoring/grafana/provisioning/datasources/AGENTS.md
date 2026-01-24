# Grafana Datasource Provisioning Directory - Agent Guide

## Purpose

This directory contains Grafana datasource provisioning configuration that automatically configures data sources when Grafana starts. Datasources define **where** Grafana queries data from (Prometheus, APIs, databases, etc.) and **how** to connect to them.

**Key distinction:** This is _datasource configuration_ (connections to external systems), not dashboard definitions. Dashboards reference these datasources by name or UID.

## Directory Contents

```
datasources/
  AGENTS.md         # This file
  prometheus.yml    # Datasource configuration (Prometheus + Backend-API)
```

## Key Files

### prometheus.yml

**Purpose:** Configures data sources for Grafana to query.

**File Path (in container):** `/etc/grafana/provisioning/datasources/prometheus.yml`

**Configuration:**

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: '15s'
      httpMethod: POST

  - name: Backend-API
    type: marcusolsson-json-datasource
    access: proxy
    url: http://backend:8000
    isDefault: false
    editable: false
    jsonData:
      tlsSkipVerify: true
```

## Datasource Definitions

### 1. Prometheus (Default)

**Type:** `prometheus`

**Purpose:** Primary metrics datasource. Queries time-series data scraped by Prometheus from backend `/metrics` endpoint.

**Configuration:**

| Field          | Value                  | Description                                     |
| -------------- | ---------------------- | ----------------------------------------------- |
| `name`         | Prometheus             | Datasource name (used in dashboard references)  |
| `type`         | prometheus             | Datasource plugin type                          |
| `access`       | proxy                  | Grafana proxies requests (not browser direct)   |
| `url`          | http://prometheus:9090 | Prometheus server URL (Docker network hostname) |
| `isDefault`    | true                   | Default datasource for new panels               |
| `editable`     | false                  | Cannot be modified in Grafana UI                |
| `timeInterval` | 15s                    | Min time interval between data points           |
| `httpMethod`   | POST                   | Use POST for queries (better for large queries) |

**What it provides:**

- Time-series metrics (CPU, memory, request rates, etc.)
- PromQL query language
- Aggregation and alerting capabilities
- Data scraped every 15 seconds from backend

**Example PromQL queries:**

```promql
# Request rate
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# GPU utilization
nvidia_gpu_utilization{instance="backend:8000"}
```

### 2. Backend-API (JSON Datasource)

**Type:** `marcusolsson-json-datasource`

**Purpose:** Direct REST API access to backend endpoints. Fetches JSON data from FastAPI routes for non-time-series data (system health, stats, GPU info).

**Configuration:**

| Field           | Value                        | Description                             |
| --------------- | ---------------------------- | --------------------------------------- |
| `name`          | Backend-API                  | Datasource name                         |
| `type`          | marcusolsson-json-datasource | JSON API datasource plugin              |
| `access`        | proxy                        | Grafana proxies requests                |
| `url`           | http://backend:8000          | Backend FastAPI server URL              |
| `isDefault`     | false                        | Not the default datasource              |
| `editable`      | false                        | Cannot be modified in UI                |
| `tlsSkipVerify` | true                         | Skip TLS verification (local HTTP only) |

**What it provides:**

- REST API endpoint access
- JSONPath data extraction
- Real-time system health status
- GPU statistics
- Camera status
- Event counts

**Example API endpoints used:**

```
/api/system/health       # System health status
/api/system/health/ready # Readiness check
/api/system/stats        # System statistics
/api/system/telemetry    # Pipeline telemetry
/api/system/gpu          # GPU metrics
/api/cameras             # Camera list
/api/events              # Event history
```

**Example JSONPath queries:**

```jsonpath
# Extract total cameras from /api/system/stats
$.total_cameras

# Extract GPU utilization from /api/system/gpu
$.utilization_percent

# Extract detection queue depth from /api/system/telemetry
$.queues.detection_queue
```

## How Datasources Work

### Startup Flow

1. Grafana container starts
2. Grafana reads `/etc/grafana/provisioning/datasources/` directory
3. `prometheus.yml` is parsed
4. Each datasource is registered with Grafana
5. Datasources appear in Data Sources settings
6. Dashboards can now reference datasources by name or UID

### Access Mode: Proxy vs Direct

**Proxy mode (used here):**

```
Browser → Grafana → Prometheus/Backend-API
```

- Requests go through Grafana server
- Grafana handles authentication and CORS
- Uses Docker network hostnames (prometheus, backend)
- More secure (credentials not exposed to browser)

**Direct mode (not used):**

```
Browser → Prometheus/Backend-API (bypassing Grafana)
```

- Browser queries datasource directly
- Requires CORS configuration
- Credentials visible in browser
- Not suitable for internal services

### Volume Mounting

In `docker-compose.prod.yml`:

```yaml
grafana:
  volumes:
    - ./monitoring/grafana/provisioning:/etc/grafana/provisioning
```

**Host → Container mapping:**

| Host Path                                        | Container Path                           | Contents       |
| ------------------------------------------------ | ---------------------------------------- | -------------- |
| `./monitoring/grafana/provisioning/datasources/` | `/etc/grafana/provisioning/datasources/` | This YAML file |

### Update Behavior

**Datasources are only loaded on startup:**

- Changes to `prometheus.yml` require Grafana restart
- Cannot be hot-reloaded like dashboards
- `editable: false` prevents UI modifications

**To apply datasource changes:**

```bash
podman-compose -f docker-compose.prod.yml restart grafana
```

## Adding a New Datasource

### Example: PostgreSQL Datasource

Add to `prometheus.yml`:

```yaml
datasources:
  - name: Prometheus
    # ... existing config ...

  - name: Backend-API
    # ... existing config ...

  - name: PostgreSQL
    type: postgres
    access: proxy
    url: postgres:5432
    database: security_monitoring
    user: $POSTGRES_USER
    secureJsonData:
      password: $POSTGRES_PASSWORD
    isDefault: false
    editable: false
    jsonData:
      sslmode: disable
      maxOpenConns: 10
      maxIdleConns: 5
      connMaxLifetime: 14400
```

Then restart Grafana: `podman-compose -f docker-compose.prod.yml restart grafana`

### Example: InfluxDB Datasource

```yaml
- name: InfluxDB
  type: influxdb
  access: proxy
  url: http://influxdb:8086
  database: monitoring
  isDefault: false
  editable: false
  jsonData:
    version: Flux
    organization: my-org
    defaultBucket: monitoring
  secureJsonData:
    token: $INFLUXDB_TOKEN
```

### Example: Additional JSON API

```yaml
- name: External-API
  type: marcusolsson-json-datasource
  access: proxy
  url: https://api.example.com
  isDefault: false
  editable: false
  jsonData:
    tlsSkipVerify: false
  secureJsonData:
    apiKey: $API_KEY
```

## Datasource Plugin Requirements

### Built-in Plugins (Pre-installed)

- `prometheus` - Prometheus datasource
- `postgres` - PostgreSQL datasource
- `mysql` - MySQL datasource
- `influxdb` - InfluxDB datasource

### Required External Plugins

**marcusolsson-json-datasource** is required for Backend-API datasource.

**Installation via docker-compose.prod.yml:**

```yaml
grafana:
  environment:
    - GF_INSTALL_PLUGINS=marcusolsson-json-datasource
```

This plugin is automatically installed when the Grafana container starts.

### Verifying Plugin Installation

```bash
# Check installed plugins
podman exec grafana grafana-cli plugins ls

# Expected output should include:
# marcusolsson-json-datasource @ 1.3.x
```

## Dashboard References to Datasources

Dashboards reference datasources using:

1. **By name (legacy):**

```json
"datasource": "Prometheus"
```

2. **By UID (recommended):**

```json
"datasource": {
  "type": "prometheus",
  "uid": "Prometheus"
}
```

**Note:** If no UID is specified in datasource config, Grafana uses the datasource name as the UID.

### Current Datasource Usage

**Prometheus datasource used in:**

- `consolidated.json` - All Prometheus metric panels
- Time-series graphs
- Rate calculations
- Histogram quantiles

**Backend-API datasource used in:**

- `consolidated.json` - System health, stats, telemetry panels
- Stat panels (gauges, counters)
- Real-time status indicators

## Troubleshooting

### Datasource Not Appearing

**Symptom:** Datasource not listed in Grafana → Configuration → Data Sources.

**Debugging steps:**

1. **Check Grafana logs:**

   ```bash
   podman logs grafana | grep -i provisioning
   podman logs grafana | grep -i datasource
   ```

2. **Verify YAML syntax:**

   ```bash
   yamllint monitoring/grafana/provisioning/datasources/prometheus.yml
   ```

3. **Check file permissions:**

   ```bash
   ls -la monitoring/grafana/provisioning/datasources/
   ```

4. **Verify volume mount:**

   ```bash
   podman exec grafana ls -la /etc/grafana/provisioning/datasources/
   ```

5. **Check plugin installation (for Backend-API):**

   ```bash
   podman exec grafana grafana-cli plugins ls | grep json
   ```

### Connection Error: "Bad Gateway" or "Connection Refused"

**Symptom:** Datasource shows red "HTTP Error Bad Gateway" in dashboard panels.

**Possible causes:**

1. **Service not running:**

   ```bash
   podman ps | grep prometheus
   podman ps | grep backend
   ```

2. **Wrong hostname/port:**

   Verify Docker network connectivity:

   ```bash
   podman exec grafana ping -c 2 prometheus
   podman exec grafana curl -s http://prometheus:9090/-/healthy
   podman exec grafana curl -s http://backend:8000/api/system/health
   ```

3. **Network isolation:**

   Ensure all services are on the same Docker network in `docker-compose.prod.yml`.

### Datasource Shows "Provisioned" Lock

**Symptom:** Cannot edit datasource in Grafana UI.

**Cause:** `editable: false` in config (intentional for immutable infrastructure).

**To allow editing:**

Change in `prometheus.yml`:

```yaml
editable: true
```

Then restart Grafana.

**Warning:** UI changes to editable datasources won't persist (overwritten by provisioning on restart).

### JSONPath Query Returns No Data

**Symptom:** Backend-API panels show "No data" despite API returning data.

**Debugging steps:**

1. **Test API endpoint directly:**

   ```bash
   curl http://localhost:8000/api/system/health | jq
   ```

2. **Check JSONPath syntax:**

   ```bash
   # Test JSONPath extraction
   curl http://localhost:8000/api/system/stats | jq '.total_cameras'
   ```

3. **Verify Grafana can reach backend:**

   ```bash
   podman exec grafana curl -s http://backend:8000/api/system/stats
   ```

4. **Check panel configuration:**

   - Datasource set to "Backend-API"
   - URL path correct (e.g., `/api/system/stats`)
   - JSONPath correct (e.g., `$.total_cameras`)

### Prometheus Connection Issues

**Symptom:** Prometheus datasource shows "Error reading Prometheus".

**Debugging steps:**

1. **Check Prometheus is running:**

   ```bash
   curl http://localhost:9090/-/healthy
   ```

2. **Verify Prometheus has data:**

   ```bash
   curl http://localhost:9090/api/v1/query?query=up
   ```

3. **Check Grafana can reach Prometheus:**

   ```bash
   podman exec grafana curl -s http://prometheus:9090/-/healthy
   ```

4. **Check Prometheus logs:**

   ```bash
   podman logs prometheus --tail=50
   ```

## Configuration Best Practices

### Security

- Use `editable: false` to prevent UI tampering
- Use `secureJsonData` for sensitive values (passwords, tokens)
- Use environment variables for secrets: `$ENV_VAR_NAME`
- Keep `tlsSkipVerify: false` for external HTTPS datasources

### Performance

- Use `httpMethod: POST` for Prometheus (better for large queries)
- Set `timeInterval` to match Prometheus scrape interval (15s)
- Configure connection pooling for database datasources
- Use proxy access mode for internal services

### Maintenance

- Document datasource purpose in comments
- Use consistent naming conventions
- Keep UID stable (used in dashboard references)
- Version control all provisioning files

## Environment Variables

Datasource configs can use environment variables for sensitive data:

### Example with secrets:

```yaml
datasources:
  - name: PostgreSQL
    user: $POSTGRES_USER
    secureJsonData:
      password: $POSTGRES_PASSWORD

  - name: External-API
    secureJsonData:
      apiKey: $API_KEY
```

### Setting environment variables:

In `docker-compose.prod.yml`:

```yaml
grafana:
  environment:
    - POSTGRES_USER=${POSTGRES_USER}
    - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    - API_KEY=${API_KEY}
  env_file:
    - .env
```

In `.env`:

```env
POSTGRES_USER=monitoring_user
POSTGRES_PASSWORD=secure_password
API_KEY=secret_api_key
```

## Related Files

- **Parent directory:** `../` - Main provisioning AGENTS.md with overview
- **Dashboard provisioning:** `../dashboards/dashboard.yml` - Dashboard provider config
- **Dashboard definitions:** `../../dashboards/*.json` - Dashboards that use these datasources
- **Prometheus config:** `../../prometheus.yml` - Prometheus scrape targets
- **Backend metrics:** `backend/api/routes/metrics.py` - Prometheus metrics endpoint
- **Backend API:** `backend/api/routes/system.py` - REST API endpoints for Backend-API datasource
- **Compose file:** `../../../docker-compose.prod.yml` - Service definitions and network config

## References

- [Grafana Provisioning Documentation](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [Datasource Provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/#data-sources)
- [Prometheus Datasource](https://grafana.com/docs/grafana/latest/datasources/prometheus/)
- [JSON API Datasource Plugin](https://grafana.com/grafana/plugins/marcusolsson-json-datasource/)

## Quick Commands

```bash
# Restart Grafana to apply datasource changes
podman-compose -f docker-compose.prod.yml restart grafana

# View Grafana logs
podman logs grafana -f

# Check datasource config in container
podman exec grafana cat /etc/grafana/provisioning/datasources/prometheus.yml

# Test datasource connectivity from Grafana container
podman exec grafana curl -s http://prometheus:9090/-/healthy
podman exec grafana curl -s http://backend:8000/api/system/health

# Check installed plugins
podman exec grafana grafana-cli plugins ls

# Validate YAML syntax
yamllint monitoring/grafana/provisioning/datasources/prometheus.yml

# Test Prometheus query
curl "http://localhost:9090/api/v1/query?query=up"

# Test Backend API endpoint
curl http://localhost:8000/api/system/stats | jq
```
