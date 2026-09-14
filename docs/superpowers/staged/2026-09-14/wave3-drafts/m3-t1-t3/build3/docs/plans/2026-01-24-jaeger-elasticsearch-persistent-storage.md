# Jaeger Elasticsearch Persistent Storage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Configure Jaeger with Elasticsearch backend for persistent trace storage with 30-day retention.

**Architecture:** Deploy single-node Elasticsearch alongside existing Jaeger. Configure Jaeger to use ES as span storage backend with index lifecycle management for automatic retention. No changes to OpenTelemetry instrumentation required - only storage backend changes.

**Tech Stack:** Elasticsearch 8.x, Jaeger 1.54, Docker Compose, Index Lifecycle Management (ILM)

**Linear Issue:** [NEM-3053](https://linear.app/nemotron-v3-home-security/issue/NEM-3053)

---

## Overview

### Current State

- Jaeger all-in-one with in-memory storage (`SPAN_STORAGE_TYPE=memory`)
- Max 100K traces before eviction
- Traces lost on container restart
- OpenTelemetry already configured and sending traces

### Target State

- Elasticsearch single-node for span storage
- 30-day retention with automatic index cleanup
- Traces persist across restarts
- Same Grafana integration (no datasource changes needed)

### Files Changed

| File                                                     | Action | Purpose                              |
| -------------------------------------------------------- | ------ | ------------------------------------ |
| `docker-compose.prod.yml`                                | Modify | Add ES service, update Jaeger config |
| `docker-compose.staging.yml`                             | Modify | Mirror prod changes                  |
| `monitoring/elasticsearch/ilm-policy.json`               | Create | Index lifecycle policy               |
| `monitoring/elasticsearch/index-template.json`           | Create | Jaeger index template                |
| `.env.example`                                           | Modify | Add ES configuration variables       |
| `docs/architecture/observability/distributed-tracing.md` | Modify | Document ES backend                  |

---

## Task 1: Create Elasticsearch Configuration Files

**Files:**

- Create: `monitoring/elasticsearch/ilm-policy.json`
- Create: `monitoring/elasticsearch/index-template.json`

### Step 1: Create monitoring/elasticsearch directory

```bash
mkdir -p monitoring/elasticsearch
```

### Step 2: Create ILM policy file

Create `monitoring/elasticsearch/ilm-policy.json`:

```json
{
  "policy": {
    "phases": {
      "hot": {
        "min_age": "0ms",
        "actions": {
          "rollover": {
            "max_age": "1d",
            "max_primary_shard_size": "10gb"
          },
          "set_priority": {
            "priority": 100
          }
        }
      },
      "warm": {
        "min_age": "2d",
        "actions": {
          "set_priority": {
            "priority": 50
          },
          "shrink": {
            "number_of_shards": 1
          },
          "forcemerge": {
            "max_num_segments": 1
          }
        }
      },
      "delete": {
        "min_age": "30d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}
```

### Step 3: Create index template file

Create `monitoring/elasticsearch/index-template.json`:

```json
{
  "index_patterns": ["jaeger-span-*", "jaeger-service-*", "jaeger-dependencies-*"],
  "template": {
    "settings": {
      "index.lifecycle.name": "jaeger-ilm-policy",
      "index.lifecycle.rollover_alias": "jaeger-span-write",
      "number_of_shards": 1,
      "number_of_replicas": 0,
      "refresh_interval": "5s"
    }
  }
}
```

### Step 4: Commit configuration files

```bash
git add monitoring/elasticsearch/
git commit -m "feat: add Elasticsearch ILM and index template for Jaeger (NEM-3053)"
```

---

## Task 2: Add Elasticsearch Service to Docker Compose

**Files:**

- Modify: `docker-compose.prod.yml:623-650` (Jaeger section)

### Step 1: Add Elasticsearch service

Add this service block after line 621 (before the Jaeger service) in `docker-compose.prod.yml`:

```yaml
# Elasticsearch for Jaeger trace storage (NEM-3053)
# Single-node deployment with 30-day retention via ILM
elasticsearch:
  image: docker.io/elasticsearch:8.12.0
  environment:
    # Single-node discovery (no cluster)
    - discovery.type=single-node
    # Disable security for internal network (no external exposure)
    - xpack.security.enabled=false
    # Memory settings - ES needs locked memory for performance
    - bootstrap.memory_lock=true
    - 'ES_JAVA_OPTS=-Xms${ES_HEAP_SIZE:-2g} -Xmx${ES_HEAP_SIZE:-2g}'
    # Reduce disk watermarks for single-node
    - cluster.routing.allocation.disk.threshold_enabled=true
    - cluster.routing.allocation.disk.watermark.low=85%
    - cluster.routing.allocation.disk.watermark.high=90%
    - cluster.routing.allocation.disk.watermark.flood_stage=95%
  volumes:
    - elasticsearch_data:/usr/share/elasticsearch/data
    - ./monitoring/elasticsearch:/usr/share/elasticsearch/config/ilm:ro,z
  ulimits:
    memlock:
      soft: -1
      hard: -1
    nofile:
      soft: 65536
      hard: 65536
  healthcheck:
    test:
      [
        'CMD-SHELL',
        'curl -s http://localhost:9200/_cluster/health | grep -q ''"status":"green"\|"status":"yellow"''',
      ]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s
  restart: unless-stopped
  networks:
    - security-net
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: ${ES_MEMORY_LIMIT:-4G}
```

### Step 2: Add elasticsearch_data volume

Add to the `volumes:` section at the bottom of docker-compose.prod.yml:

```yaml
elasticsearch_data:
```

### Step 3: Update Jaeger service configuration

Replace the existing Jaeger service block (lines 625-650) with:

```yaml
# Jaeger all-in-one for distributed tracing (NEM-1629, NEM-3053)
# Provides trace collection, storage, and visualization for cross-service request correlation
# Uses Elasticsearch backend for persistent storage with 30-day retention
jaeger:
  image: docker.io/jaegertracing/all-in-one:1.54
  ports:
    - '16686:16686' # Jaeger UI
    - '4317:4317' # OTLP gRPC receiver
    - '4318:4318' # OTLP HTTP receiver
  environment:
    - COLLECTOR_OTLP_ENABLED=true
    # Elasticsearch storage backend (NEM-3053)
    - SPAN_STORAGE_TYPE=elasticsearch
    - ES_SERVER_URLS=http://elasticsearch:9200
    # Index configuration
    - ES_INDEX_PREFIX=jaeger
    - ES_TAGS_AS_FIELDS_ALL=true
    # Performance tuning
    - ES_NUM_SHARDS=1
    - ES_NUM_REPLICAS=0
    - ES_BULK_SIZE=5000000
    - ES_BULK_WORKERS=1
    - ES_BULK_FLUSH_INTERVAL=200ms
  depends_on:
    elasticsearch:
      condition: service_healthy
  healthcheck:
    test: ['CMD', 'wget', '--no-verbose', '--tries=1', '--spider', 'http://localhost:16686']
    interval: 15s
    timeout: 5s
    retries: 3
  restart: unless-stopped
  networks:
    - security-net
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
```

### Step 4: Run docker-compose config validation

```bash
podman-compose -f docker-compose.prod.yml config > /dev/null && echo "Config valid"
```

Expected: "Config valid"

### Step 5: Commit docker-compose changes

```bash
git add docker-compose.prod.yml
git commit -m "feat: add Elasticsearch service and update Jaeger for ES backend (NEM-3053)"
```

---

## Task 3: Update Staging Docker Compose

**Files:**

- Modify: `docker-compose.staging.yml`

### Step 1: Mirror the changes from docker-compose.prod.yml

Apply the same Elasticsearch service and Jaeger configuration changes to `docker-compose.staging.yml`. The staging environment should match production for testing.

### Step 2: Commit staging changes

```bash
git add docker-compose.staging.yml
git commit -m "feat: add Elasticsearch to staging compose (NEM-3053)"
```

---

## Task 4: Update Environment Configuration

**Files:**

- Modify: `.env.example`

### Step 1: Add Elasticsearch environment variables

Add to `.env.example`:

```bash
# =============================================================================
# Elasticsearch Configuration (Jaeger Storage Backend)
# =============================================================================
# Heap size for Elasticsearch JVM (default: 2g)
# Recommended: Set to 50% of available memory, max 32g
ES_HEAP_SIZE=2g

# Memory limit for Elasticsearch container (default: 4G)
# Should be at least 2x ES_HEAP_SIZE for OS cache
ES_MEMORY_LIMIT=4G
```

### Step 2: Commit environment changes

```bash
git add .env.example
git commit -m "docs: add Elasticsearch environment variables (NEM-3053)"
```

---

## Task 5: Create ILM Policy Initialization Script

**Files:**

- Create: `scripts/init-elasticsearch.sh`

### Step 1: Create initialization script

Create `scripts/init-elasticsearch.sh`:

```bash
#!/bin/bash
# Initialize Elasticsearch with Jaeger ILM policy and index template
# Run this after Elasticsearch is healthy but before Jaeger starts writing

set -euo pipefail

ES_URL="${ES_URL:-http://localhost:9200}"

echo "Waiting for Elasticsearch to be ready..."
until curl -s "${ES_URL}/_cluster/health" | grep -q '"status":"green"\|"status":"yellow"'; do
  echo "Elasticsearch not ready, waiting..."
  sleep 5
done

echo "Elasticsearch is ready. Creating ILM policy..."

# Create ILM policy
curl -X PUT "${ES_URL}/_ilm/policy/jaeger-ilm-policy" \
  -H 'Content-Type: application/json' \
  -d '{
    "policy": {
      "phases": {
        "hot": {
          "min_age": "0ms",
          "actions": {
            "rollover": {
              "max_age": "1d",
              "max_primary_shard_size": "10gb"
            },
            "set_priority": {
              "priority": 100
            }
          }
        },
        "warm": {
          "min_age": "2d",
          "actions": {
            "set_priority": {
              "priority": 50
            },
            "shrink": {
              "number_of_shards": 1
            },
            "forcemerge": {
              "max_num_segments": 1
            }
          }
        },
        "delete": {
          "min_age": "30d",
          "actions": {
            "delete": {}
          }
        }
      }
    }
  }'

echo ""
echo "Creating index template..."

# Create index template
curl -X PUT "${ES_URL}/_index_template/jaeger-template" \
  -H 'Content-Type: application/json' \
  -d '{
    "index_patterns": ["jaeger-span-*", "jaeger-service-*", "jaeger-dependencies-*"],
    "template": {
      "settings": {
        "index.lifecycle.name": "jaeger-ilm-policy",
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "refresh_interval": "5s"
      }
    },
    "priority": 100
  }'

echo ""
echo "Elasticsearch initialization complete!"
echo "ILM policy 'jaeger-ilm-policy' created with 30-day retention"
echo "Index template 'jaeger-template' created for jaeger-* indices"
```

### Step 2: Make script executable

```bash
chmod +x scripts/init-elasticsearch.sh
```

### Step 3: Commit initialization script

```bash
git add scripts/init-elasticsearch.sh
git commit -m "feat: add Elasticsearch initialization script for Jaeger ILM (NEM-3053)"
```

---

## Task 6: Add Smoke Test for Elasticsearch Integration

**Files:**

- Modify: `tests/smoke/test_monitoring_smoke.py`

### Step 1: Add Elasticsearch health check test

Add to `tests/smoke/test_monitoring_smoke.py`:

```python
@pytest.mark.smoke
def test_elasticsearch_healthy():
    """Verify Elasticsearch is healthy and accepting connections."""
    response = requests.get(
        "http://localhost:9200/_cluster/health",
        timeout=10
    )
    assert response.status_code == 200
    health = response.json()
    assert health["status"] in ("green", "yellow")


@pytest.mark.smoke
def test_jaeger_elasticsearch_backend():
    """Verify Jaeger is using Elasticsearch backend."""
    # Query Jaeger for services (this exercises ES backend)
    response = requests.get(
        "http://localhost:16686/api/services",
        timeout=10
    )
    assert response.status_code == 200

    # Verify ES has Jaeger indices
    es_response = requests.get(
        "http://localhost:9200/_cat/indices/jaeger-*?format=json",
        timeout=10
    )
    assert es_response.status_code == 200
```

### Step 2: Commit test changes

```bash
git add tests/smoke/test_monitoring_smoke.py
git commit -m "test: add Elasticsearch smoke tests (NEM-3053)"
```

---

## Task 7: Update Documentation

**Files:**

- Modify: `docs/architecture/observability/distributed-tracing.md`

### Step 1: Update distributed tracing documentation

Add a new section to `docs/architecture/observability/distributed-tracing.md`:

````markdown
## Storage Backend

### Elasticsearch Configuration

Jaeger uses Elasticsearch for persistent trace storage with automatic retention management.

| Setting                 | Value                       | Purpose                        |
| ----------------------- | --------------------------- | ------------------------------ |
| `SPAN_STORAGE_TYPE`     | `elasticsearch`             | Storage backend type           |
| `ES_SERVER_URLS`        | `http://elasticsearch:9200` | ES cluster endpoint            |
| `ES_INDEX_PREFIX`       | `jaeger`                    | Index name prefix              |
| `ES_TAGS_AS_FIELDS_ALL` | `true`                      | Index all span tags for search |

### Index Lifecycle Management

Traces are automatically managed with the following lifecycle:

| Phase  | Age       | Actions                        |
| ------ | --------- | ------------------------------ |
| Hot    | 0-1 day   | Active writes, high priority   |
| Warm   | 2-30 days | Shrink to 1 shard, force merge |
| Delete | 30+ days  | Automatic deletion             |

### Resource Requirements

| Component     | CPU     | Memory         | Disk      |
| ------------- | ------- | -------------- | --------- |
| Elasticsearch | 2 cores | 4GB (2GB heap) | 50GB+ SSD |
| Jaeger        | 1 core  | 512MB          | -         |

### Initialization

On first deployment, run the ILM initialization script:

```bash
./scripts/init-elasticsearch.sh
```
````

This creates the ILM policy and index template for automatic retention.

````

### Step 2: Commit documentation

```bash
git add docs/architecture/observability/distributed-tracing.md
git commit -m "docs: add Elasticsearch backend documentation (NEM-3053)"
````

---

## Task 8: Integration Test

**Files:** None (manual verification)

### Step 1: Start the stack

```bash
podman-compose -f docker-compose.prod.yml up -d elasticsearch
```

### Step 2: Wait for Elasticsearch to be healthy

```bash
podman-compose -f docker-compose.prod.yml logs -f elasticsearch
# Wait for "started" message
```

### Step 3: Initialize Elasticsearch

```bash
./scripts/init-elasticsearch.sh
```

Expected output:

```
Elasticsearch is ready. Creating ILM policy...
{"acknowledged":true}
Creating index template...
{"acknowledged":true}
Elasticsearch initialization complete!
```

### Step 4: Start Jaeger

```bash
podman-compose -f docker-compose.prod.yml up -d jaeger
```

### Step 5: Verify Jaeger is using ES backend

```bash
# Check Jaeger logs for ES connection
podman-compose -f docker-compose.prod.yml logs jaeger | grep -i elastic

# Verify indices are created after some traces
curl -s http://localhost:9200/_cat/indices/jaeger-*
```

### Step 6: Generate test traces

```bash
# Start backend and generate some traffic
podman-compose -f docker-compose.prod.yml up -d backend
curl http://localhost:8000/api/health
curl http://localhost:8000/api/system/status
```

### Step 7: Verify traces in Jaeger UI

Open http://localhost:16686 and:

1. Select service "nemotron-backend"
2. Click "Find Traces"
3. Verify traces are displayed

### Step 8: Verify traces persist after restart

```bash
# Restart Jaeger
podman-compose -f docker-compose.prod.yml restart jaeger

# Check traces are still available in UI
```

---

## Task 9: Final Commit and PR

### Step 1: Run full validation

```bash
./scripts/validate.sh
```

### Step 2: Create final commit if needed

```bash
git status
# If any uncommitted changes, commit them
```

### Step 3: Update Linear issue to In Review

```bash
# Using Linear MCP tool:
mcp__linear__update_issue(issueId="14ebb61f-1027-4662-861f-213d927e295c", status="ec90a3c4-c160-44fc-aa7e-82bdca77aa46")
```

---

## Rollback Plan

If issues occur, revert to in-memory storage:

1. Stop services:

   ```bash
   podman-compose -f docker-compose.prod.yml down jaeger elasticsearch
   ```

2. Revert Jaeger config in `docker-compose.prod.yml`:

   ```yaml
   environment:
     - SPAN_STORAGE_TYPE=memory
     - MEMORY_MAX_TRACES=100000
   ```

3. Remove `depends_on: elasticsearch` from Jaeger service

4. Restart:
   ```bash
   podman-compose -f docker-compose.prod.yml up -d jaeger
   ```

---

## Resource Sizing Guide

| Trace Volume | ES Heap | ES Memory | Disk (30 days) |
| ------------ | ------- | --------- | -------------- |
| < 1M/day     | 1GB     | 2GB       | 20GB           |
| 1-5M/day     | 2GB     | 4GB       | 50GB           |
| 5-20M/day    | 4GB     | 8GB       | 100GB          |
| > 20M/day    | 8GB+    | 16GB+     | 200GB+         |

For home security with moderate camera activity, 2GB heap / 4GB container should be sufficient.
