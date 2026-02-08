# Monitoring & Container Infrastructure Evaluation

**Date:** 2026-02-08
**Scope:** Observability stack, container infrastructure, resource optimization
**System:** Single-node home security AI pipeline (2x NVIDIA GPUs, Podman rootless)

---

## Executive Summary

The current monitoring stack is **comprehensive and well-architected** for a home security AI pipeline, with excellent coverage across metrics (Prometheus), logs (Loki), traces (Jaeger), and profiles (Pyroscope). However, several components are **significantly behind current versions**, and the architecture carries **~10GB+ of memory overhead** for monitoring alone -- a substantial burden on a single-node system that also runs 6 AI services consuming 24GB+ GPU memory and ~36GB system RAM.

The highest-impact optimization is **replacing Jaeger + Elasticsearch with Grafana Tempo**, which would eliminate ~6.5GB of memory usage and remove an entire infrastructure dependency. The second highest-impact change is **upgrading Grafana from 10.2.3 to 12.3** for major performance improvements, dynamic dashboards, and improved exploration tools. Upgrading Alloy from v1.0.0 is also critical, as it is nearly 2 years behind and may resolve the privileged mode workaround.

**Total estimated memory savings from recommended changes: 5-7GB** (primarily from Elasticsearch elimination).

---

## Current Configuration Analysis

### Service Inventory (14 Monitoring Services)

| Service           | Version | Current Latest | Memory Limit      | Purpose              |
| ----------------- | ------- | -------------- | ----------------- | -------------------- |
| Prometheus        | v2.48.0 | v3.1.x         | 512MB             | Metrics TSDB         |
| Grafana           | 10.2.3  | 12.3           | 512MB             | Dashboards/Viz       |
| Jaeger            | 1.54    | 1.68+          | 512MB             | Trace collection     |
| Elasticsearch     | 8.12.0  | 8.17+          | 6GB               | Trace storage        |
| Loki              | 2.9.4   | 3.5+           | 1GB               | Log aggregation      |
| Pyroscope         | 1.18.0  | 1.12+          | 512MB             | Continuous profiling |
| Alloy             | v1.0.0  | v1.9+          | 768MB             | Collector/eBPF       |
| Alertmanager      | v0.27.0 | v0.28+         | 128MB             | Alert routing        |
| cAdvisor          | v0.49.1 | v0.51+         | 256MB             | Container metrics    |
| Node Exporter     | v1.8.2  | v1.9+          | 128MB             | Host metrics         |
| DCGM Exporter     | 3.3.5   | 3.6+           | (GPU reservation) | GPU metrics          |
| Blackbox Exporter | v0.24.0 | v0.26+         | 64MB              | Synthetic probes     |
| Redis Exporter    | v1.55.0 | v1.67+         | 64MB              | Redis metrics        |
| JSON Exporter     | v0.6.0  | v0.7+          | 64MB              | JSON-to-metrics      |

**Total monitoring memory allocation: ~10.6GB** (Elasticsearch alone accounts for 57% at 6GB).

### Architecture Strengths

1. **Full LGTM+P stack**: Logs (Loki), Grafana, Traces (Jaeger), Metrics (Prometheus), Profiles (Pyroscope) -- complete observability.
2. **Cross-signal correlation**: Trace-to-profile links (Jaeger to Pyroscope), log-to-trace links (Loki derived fields to Jaeger), trace-to-metrics queries -- all properly wired.
3. **Security hardening**: Consistent `no-new-privileges`, `cap_drop: ALL`, `127.0.0.1` binding across monitoring services.
4. **Native metrics exposure**: AI services expose Prometheus-native `/metrics` endpoints, avoiding JSON exporter overhead for primary telemetry.
5. **eBPF profiling for native code**: Correct use of Alloy eBPF for llama.cpp (C++) profiling alongside py-spy for Python services.
6. **Loki config**: Already using TSDB store, v13 schema, filesystem backend -- well-tuned for single-node.

### Architecture Weaknesses

1. **Elasticsearch is massively oversized** for trace storage: 6GB memory limit + 2GB JVM heap for a single-node system generating modest trace volumes.
2. **Alloy runs in privileged mode** due to SELinux conflicts with v1.0.0 -- a significant security gap in an otherwise well-hardened stack.
3. **Single flat network** for 20+ services (all on `security-net`) provides no blast radius containment.
4. **Version drift is severe**: Grafana is 2 major versions behind (10.x vs 12.x), Loki is 1 major version behind (2.x vs 3.x), Prometheus is 1 major version behind (2.x vs 3.x), Alloy is ~18 minor releases behind.
5. **Duplicate Prometheus scrape jobs**: `ai-llm-metrics` and `llama-cpp-metrics` both scrape `ai-llm:8091` at `/metrics`.

---

## Recommended Optimizations

### 1. Replace Jaeger + Elasticsearch with Grafana Tempo

**Impact: HIGH | Effort: MEDIUM | Risk: LOW**

**What to change:**
Remove the `elasticsearch` and `jaeger` services from `docker-compose.prod.yml`. Add a single `tempo` service running in monolithic mode with local filesystem storage.

**Why:**

- Elasticsearch consumes 6GB memory limit (2GB heap) solely for trace storage. This is the single largest memory consumer in the monitoring stack.
- Grafana Tempo in monolithic mode can run with 512MB-1GB memory for equivalent trace volumes.
- Tempo uses a custom storage engine (TempoDB) that stores traces directly on the filesystem -- no database dependency.
- Tempo integrates natively with Grafana (same vendor), eliminating the need for the Jaeger datasource plugin.
- Tempo accepts OTLP natively, so Alloy can forward traces directly to Tempo instead of Jaeger.

**Expected impact:**

- Memory savings: **~5.5GB** (6GB ES + 512MB Jaeger - 1GB Tempo)
- Reduced operational complexity: 2 services removed, 1 added
- Improved Grafana integration: native TraceQL query language, better trace-to-log and trace-to-metric correlation

**Implementation:**

```yaml
# Replace elasticsearch + jaeger with:
tempo:
  image: docker.io/grafana/tempo:2.7.1
  security_opt:
    - no-new-privileges:true
  cap_drop:
    - ALL
  volumes:
    - ./monitoring/tempo/tempo-config.yml:/etc/tempo/config.yml:ro,z
    - tempo_data:/var/tempo
  command: -config.file=/etc/tempo/config.yml
  ports:
    - '127.0.0.1:${TEMPO_PORT:-3200}:3200' # Tempo API
    - '127.0.0.1:${TEMPO_OTLP_GRPC:-4317}:4317' # OTLP gRPC
  healthcheck:
    test: ['CMD', 'wget', '-q', '--spider', 'http://localhost:3200/ready']
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
        memory: 1G
```

Tempo config for local filesystem:

```yaml
stream_over_http_enabled: true
server:
  http_listen_port: 3200
distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: '0.0.0.0:4317'
        http:
          endpoint: '0.0.0.0:4318'
storage:
  trace:
    backend: local
    local:
      path: /var/tempo/traces
    wal:
      path: /var/tempo/wal
compactor:
  compaction:
    block_retention: 720h # 30 days
```

Update Alloy config to export to Tempo instead of Jaeger:

```
otelcol.exporter.otlp "tempo" {
  client {
    endpoint = "tempo:4317"
    tls { insecure = true }
  }
}
```

Update Grafana datasource provisioning to use Tempo instead of Jaeger.

**Risks:**

- Tempo's query capabilities differ from Jaeger's. Tempo is "search by trace ID" first, with TraceQL for attribute-based search (requires Grafana 10.2+, which you have). Jaeger's tag-based search is more intuitive for ad-hoc debugging.
- Migration: existing traces in Elasticsearch would be inaccessible (acceptable for a home security system; traces are ephemeral debugging data).

**References:**

- [Grafana Tempo vs Jaeger Comparison (Last9)](https://last9.io/blog/grafana-tempo-vs-jaeger/)
- [Best practices for migration from Jaeger to Tempo (Red Hat)](https://developers.redhat.com/articles/2025/04/09/best-practices-migration-jaeger-tempo)
- [Tempo Monolithic Deployment](https://grafana.com/docs/tempo/latest/setup/operator/monolithic/)

---

### 2. Upgrade Grafana from 10.2.3 to 12.3

**Impact: HIGH | Effort: LOW | Risk: LOW-MEDIUM**

**What to change:**
Update the Grafana image from `grafana/grafana:10.2.3` to `grafana/grafana:12.3.x`.

**Why (key features gained):**

- **Grafana 11.0** (May 2024): Scenes-powered dashboards, Explore Metrics/Logs (no-code PromQL/LogQL exploration), improved alerting, table row coloring.
- **Grafana 11.6** (March 2025): LBAC for metrics, improved alerting.
- **Grafana 12.0** (May 2025): Observability-as-code (version/validate/deploy dashboards), dynamic dashboards with auto-grid layouts, new versioned API model.
- **Grafana 12.2** (Sept 2025): Redesigned table with react-data-grid (97.8% faster CPU for 40K+ rows), Logs Drilldown JSON viewer.
- **Grafana 12.3** (Jan 2026): Redesigned logs panel with faster pattern recognition and better exploration.

**Expected impact:**

- Significantly better dashboard performance and user experience
- No-code metric exploration for ad-hoc debugging
- Observability-as-code for version-controlled dashboard management
- Better log panel performance for high-volume AI pipeline logs

**Implementation:**

```yaml
grafana:
  image: docker.io/grafana/grafana:12.3.2
  # Note: Remove JSON API plugin pin or update to compatible version
  # v1.3.15+ requires Grafana 11.6+, which 12.x satisfies
  environment:
    - GF_INSTALL_PLUGINS=marcusolsson-json-datasource
    # ... rest unchanged
```

**Risks:**

- Breaking changes in Grafana 11.0: legacy alerting removed (already using Grafana Alerting, so no impact).
- The `marcusolsson-json-datasource 1.3.0` pin was for Grafana 10.x compatibility. With 12.x, you should use the latest version (remove the version pin).
- Dashboard JSON compatibility: most dashboards should auto-migrate, but test all 13 custom dashboards.

**References:**

- [Grafana 12 Release (Grafana Labs)](https://grafana.com/blog/grafana-12-release-all-the-new-features/)
- [What's new in Grafana v12.0](https://grafana.com/docs/grafana/latest/whatsnew/whats-new-in-v12-0/)
- [Breaking changes in Grafana v11.0](https://grafana.com/docs/grafana/latest/breaking-changes/breaking-changes-v11-0/)

---

### 3. Upgrade Alloy from v1.0.0 to v1.9+

**Impact: HIGH | Effort: MEDIUM | Risk: MEDIUM**

**What to change:**
Update `grafana/alloy:v1.0.0` to `grafana/alloy:v1.9.2` (or latest stable).

**Why:**

- v1.0.0 is nearly 2 years old and the root cause of the **privileged mode workaround** (NEM-4499). Newer versions have had significant SELinux and security context improvements.
- 18+ minor releases of improvements to the eBPF profiler, log collection pipeline, and OTLP handling.
- OpenTelemetry components upgraded to v0.125.0 in recent releases.
- Live graph telemetry visualization for debugging pipeline flow.
- Numerous bug fixes for Docker/Podman log source stability.

**Expected impact:**

- Potential resolution of the privileged mode requirement (test with newer version + `--security-opt label=disable` + specific capabilities)
- Improved eBPF profiling reliability and symbol resolution
- Better OTLP pipeline performance

**Implementation:**

```yaml
alloy:
  image: docker.io/grafana/alloy:v1.9.2
  # Test without privileged first:
  # privileged: false
  # security_opt:
  #   - label=disable
  # cap_add:
  #   - SYS_ADMIN
  #   - BPF
  #   - PERFMON
  #   - SYS_PTRACE
  #   - SYS_RESOURCE
```

**Risks:**

- Config syntax may have changed between v1.0.0 and v1.9.x. Review the Alloy changelog for breaking changes in the `pyroscope.ebpf`, `loki.source.docker`, and `otelcol.receiver.otlp` components.
- The SELinux/privileged issue may persist even with newer versions, as eBPF fundamentally requires elevated privileges. However, the scope of required privileges may be narrower.
- Test thoroughly: eBPF profiling, log collection, and OTLP forwarding must all work.

**References:**

- [Grafana Alloy Release Notes](https://grafana.com/docs/alloy/latest/release-notes/)
- [Alloy GitHub Releases](https://github.com/grafana/alloy/releases)
- [Deploy eBPF without privilege (Issue #1273)](https://github.com/grafana/alloy/issues/1273)

---

### 4. Upgrade Prometheus from v2.48.0 to v3.1.x

**Impact: MEDIUM | Effort: LOW | Risk: MEDIUM**

**What to change:**
Update `prom/prometheus:v2.48.0` to `prom/prometheus:v3.1.0`.

**Key features gained:**

- **Native OTLP receiver**: Accept OTLP metrics directly via `--web.enable-otlp-receiver` at `/api/v1/otlp/v1/metrics`. This enables AI services to push metrics via OTLP instead of requiring Prometheus scrape endpoints.
- **UTF-8 support**: Store OpenTelemetry metric names with dots natively (no underscore conversion).
- **Native histograms (stable)**: More efficient histogram storage, critical for latency tracking on AI inference.
- **TSDB efficiency improvements**: Better CPU and memory usage.
- **Delta-to-cumulative conversion**: Handle OTLP delta temporality metrics natively.

**Expected impact:**

- Reduced scrape configuration complexity (AI services can push to Prometheus directly)
- More efficient storage for histogram-heavy workloads (AI inference latencies)
- Better OpenTelemetry interoperability

**Implementation:**

```yaml
prometheus:
  image: docker.io/prom/prometheus:v3.1.0
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'
    - '--storage.tsdb.retention.time=${PROMETHEUS_RETENTION_TIME:-15d}'
    - '--web.enable-lifecycle'
    - '--web.enable-otlp-receiver' # NEW: Accept OTLP metrics
```

**Risks:**

- Prometheus 3.0 has breaking changes in some PromQL behaviors and configuration syntax. Review the [migration guide](https://prometheus.io/blog/2024/11/14/prometheus-3-0/).
- Some deprecated configuration options from v2.x may be removed.
- Recording rules and alerting rules should be tested for compatibility.

**References:**

- [Announcing Prometheus 3.0](https://prometheus.io/blog/2024/11/14/prometheus-3-0/)
- [Prometheus OTLP Support Guide](https://prometheus.io/docs/guides/opentelemetry/)

---

### 5. Upgrade Loki from 2.9.4 to 3.5.x

**Impact: MEDIUM | Effort: MEDIUM | Risk: MEDIUM**

**What to change:**
Update `grafana/loki:2.9.4` to `grafana/loki:3.5.8`.

**Key features gained:**

- **OTLP native endpoint**: Accept logs via OTLP directly (enabled by default in 3.0+), aligning with OpenTelemetry standards.
- **Structured Metadata**: Store additional metadata with log entries without increasing label cardinality.
- **Bloom filters**: Accelerated log queries for high-cardinality data (useful for searching by trace_id, batch_id).
- **Improved compactor**: Better retention management and storage efficiency.
- **BoltDB deprecation**: BoltDB store removed; TSDB is the primary store (you already use TSDB, so minimal impact).

**Expected impact:**

- Faster log queries, especially for trace correlation lookups
- Better memory efficiency with improved compaction
- Alignment with OpenTelemetry ecosystem

**Implementation notes:**

- The Loki config is already using TSDB, v13 schema, and filesystem backend -- minimal config changes needed.
- Max label limit changed from 30 to 15 per series in Loki 3.x. Verify your log pipeline doesn't exceed this.
- Loki 3.5.8 removed busybox from the Docker image. The healthcheck `wget` command will need to be updated to use `curl` or a custom binary.

**Risks:**

- Breaking change: BoltDB store deprecated. Since you already use TSDB, this is a non-issue.
- The label limit reduction (30 to 15) could affect high-cardinality log streams. Audit current label usage.
- Healthcheck needs updating since `wget` is no longer available in the image.

**References:**

- [Loki 3.0 Release Notes](https://grafana.com/docs/loki/latest/release-notes/v3-0/)
- [Upgrade Loki Guide](https://grafana.com/docs/loki/latest/setup/upgrade/)

---

### 6. Implement Network Segmentation

**Impact: MEDIUM | Effort: MEDIUM | Risk: LOW**

**What to change:**
Replace the single `security-net` bridge network with three segmented networks:

```yaml
networks:
  core-net: # Backend, postgres, redis, frontend, go2rtc
    driver: bridge
  ai-net: # AI services (yolo26, llm, florence, clip, enrichment)
    driver: bridge
  monitoring-net: # All monitoring services
    driver: bridge
```

Services that need cross-network communication (e.g., backend needs both `core-net` and `ai-net`; Prometheus needs `monitoring-net` and access to scraped services) would be attached to multiple networks.

**Why:**

- Currently, all 20+ services share one broadcast domain. A compromised monitoring container (especially Alloy running privileged) can reach every service.
- Network segmentation limits blast radius: a compromised monitoring service cannot directly access the database.
- Podman Netavark supports multiple bridge networks with proper isolation between them.

**Expected impact:**

- Improved security posture: monitoring services cannot reach postgres/redis directly
- Clearer architecture documentation: network membership makes service relationships explicit
- Minimal performance impact (container-internal networking overhead is negligible)

**Implementation approach:**

- `core-net`: postgres, redis, backend, frontend, go2rtc
- `ai-net`: ai-yolo26, ai-llm, ai-florence, ai-clip, ai-enrichment, ai-enrichment-light
- `monitoring-net`: prometheus, grafana, loki, pyroscope, alloy, alertmanager, cadvisor, node-exporter, dcgm-exporter, blackbox-exporter, redis-exporter, json-exporter, tempo (if adopted)
- Backend joins all three networks (needs DB, AI services, and exposes metrics)
- Prometheus/blackbox-exporter join `ai-net` for scraping AI service metrics
- Alloy joins `core-net` for Podman socket log collection

**Risks:**

- Increased compose file complexity with multi-network service definitions.
- DNS resolution across networks requires careful configuration.
- Some scrape targets may need adjustment.

**References:**

- [Podman Networking Tutorial](https://github.com/containers/podman/blob/main/docs/tutorials/basic_networking.md)
- [Configuring container networking with Podman (Red Hat)](https://www.redhat.com/en/blog/container-networking-podman)

---

### 7. Remove Duplicate Prometheus Scrape Job

**Impact: LOW | Effort: LOW | Risk: NONE**

**What to change:**
Remove the `llama-cpp-metrics` scrape job from `monitoring/prometheus.yml`. It duplicates the `ai-llm-metrics` job -- both scrape `ai-llm:8091` at `/metrics`.

**Current duplication:**

```yaml
# Job 1 - Line 81
- job_name: 'ai-llm-metrics'
  metrics_path: /metrics
  static_configs:
    - targets: ['ai-llm:8091']

# Job 2 - Line 274 (DUPLICATE)
- job_name: 'llama-cpp-metrics'
  metrics_path: /metrics
  static_configs:
    - targets: ['ai-llm:8091']
```

**Expected impact:**

- Eliminates duplicate scrapes that waste CPU and create confusing metrics with different `job` labels.
- No data loss: all LLM metrics are already captured by `ai-llm-metrics`.

---

### 8. Evaluate Podman Quadlet Migration

**Impact: MEDIUM | Effort: HIGH | Risk: MEDIUM**

**What to change:**
Migrate from `podman-compose` with `docker-compose.prod.yml` to Podman Quadlet systemd units.

**Why:**

- Quadlet is the officially recommended approach for running Podman containers under systemd (merged into Podman 4.4+).
- Provides native systemd restart handling (superior to compose `restart: unless-stopped`).
- Enables auto-update and rollback capabilities.
- Containers start at boot via systemd, not requiring a manual `podman-compose up`.
- Declarative ini-style files that integrate with journald for logging.

**Expected impact:**

- More reliable container lifecycle management
- Native systemd dependency ordering (more robust than compose `depends_on`)
- Better integration with host system management tools

**Why this is marked HIGH effort:**

- 20+ services to convert from compose YAML to Quadlet `.container` unit files.
- GPU passthrough, volume mounts, and health checks all need translation.
- Loss of single-command `podman-compose up -d` convenience.
- Multi-file management vs single compose file.

**Recommendation:** Defer this to a future phase. The current compose setup works and the effort-to-benefit ratio is unfavorable for a single-node system. Revisit if compose restart reliability becomes a problem.

**References:**

- [Make systemd better for Podman with Quadlet (Red Hat)](https://www.redhat.com/en/blog/quadlet-podman)
- [Quadlet: Running Podman containers under systemd](https://mo8it.com/blog/quadlet/)

---

### 9. Do NOT Adopt Grafana Mimir

**Impact: N/A | Effort: N/A | Risk: N/A**

**Recommendation: Do not adopt Mimir.**

Grafana Mimir is designed for horizontally scalable, multi-tenant, long-term metric storage at the scale of billions of time series. For a single-node home security system with modest metric cardinality (~50K active series at most), standalone Prometheus is the correct choice.

**Rationale:**

- Mimir adds operational complexity (requires object storage backend like MinIO/S3).
- Single-node Prometheus handles tens of millions of active series before hitting architectural limits.
- 15-day retention with local TSDB is perfectly adequate for this use case.
- If long-term storage is needed later, Prometheus remote_write to a simple Mimir monolithic instance could be added incrementally.

**References:**

- [Grafana Mimir (GitHub)](https://github.com/grafana/mimir)
- [How I installed Grafana Mimir on my homelab cluster](https://grafana.com/blog/2022/06/07/how-i-installed-grafana-mimir-on-my-homelab-cluster/)

---

### 10. eBPF Profiling Assessment for llama.cpp

**Impact: LOW | Effort: N/A (informational) | Risk: N/A**

**Question:** Is the Alloy eBPF profiling for llama.cpp actually useful?

**Assessment:**
The eBPF profiler collects **CPU profiles only** for native (C/C++) applications. For llama.cpp, this provides:

**Useful data:**

- CPU hotspot identification in inference loops (tensor operations, attention computations)
- Thread utilization patterns across llama.cpp's thread pool
- Identification of CPU-bound vs GPU-bound phases during token generation
- Symbol-resolved stack traces showing which llama.cpp functions consume CPU time

**Limitations:**

- Cannot profile GPU execution (kernel launches, CUDA operations). GPU profiling requires NVIDIA Nsight or DCGM metrics.
- eBPF overhead is very low (~1-3% CPU), making it suitable for continuous production profiling.
- Stack trace quality depends on frame pointers being enabled in llama.cpp builds.
- Known issue: C++ programs may show "unknown" symbols if frame pointers are missing (GitHub issue #1970).

**Comparison with Pyroscope py-spy (Python services):**

- py-spy profiles Python code including GIL contention, memory allocation patterns, and wall-clock time.
- eBPF profiles native code at the CPU instruction level.
- These are complementary, not overlapping -- both are valuable for the mixed Python/C++ architecture.

**Recommendation:** Keep eBPF profiling enabled for llama.cpp. The CPU profile data is genuinely useful for understanding inference bottlenecks, especially when correlating with DCGM GPU metrics. The 768MB Alloy memory limit is justified given it handles log collection, eBPF profiling, AND OTLP forwarding.

**References:**

- [Pyroscope eBPF Setup](https://grafana.com/docs/pyroscope/latest/configure-client/grafana-alloy/ebpf/)
- [Profile types and instrumentation](https://grafana.com/docs/pyroscope/latest/configure-client/profile-types/)

---

### 11. Keep Both cAdvisor and Node Exporter

**Impact: N/A | Effort: N/A | Risk: N/A**

**Question:** Do we need both cAdvisor and Node Exporter?

**Answer: Yes.** They serve distinct, complementary purposes:

- **Node Exporter** (128MB): Host-level hardware and OS metrics -- CPU, memory, disk I/O, network interfaces, filesystem usage, system uptime. Answers: "How is the host machine performing?"
- **cAdvisor** (256MB): Container-level resource metrics -- per-container CPU, memory, network, filesystem. Answers: "How is each container utilizing its resource limits?"

For an AI pipeline with 6+ GPU-accelerated containers with specific resource limits, cAdvisor provides critical per-container visibility that Node Exporter cannot. Both are lightweight (combined 384MB) and the metrics they provide are non-overlapping.

**Recommendation:** Keep both. The 384MB combined memory cost is justified for the distinct visibility they provide.

**References:**

- [Docker Container Monitoring with cAdvisor, Node Exporter, Prometheus, and Grafana](https://www.virtualizationhowto.com/2024/10/docker-container-monitoring-with-cadvisor-node-exporter-prometheus-and-grafana/)

---

### 12. NVIDIA Container Toolkit CDI Improvements

**Impact: LOW | Effort: LOW | Risk: LOW**

**What to change:**
Ensure the NVIDIA Container Toolkit is updated to the latest version (v1.17+) for improved CDI support with Podman rootless.

**Key improvements in recent versions:**

- **Automatic CDI specification generation**: A systemd unit now generates CDI specs automatically, removing manual setup steps.
- **Rootless container support**: CDI specification files are now generated with 644 permissions, enabling rootless Podman to read them.
- **Improved error handling**: CDI refresh service trigger fixed for compressed kernels; clearer error messages for JIT CDI spec generation failures.

**Current usage is correct:**
The compose file already uses the standard `deploy.resources.reservations.devices` approach with `driver: nvidia` and `capabilities: [gpu]`, which works with CDI. The `CUDA_VISIBLE_DEVICES` environment variable correctly controls per-GPU assignment from `.env`.

**Recommendation:** Verify the host toolkit version and update if behind. No compose file changes needed.

**References:**

- [CDI Support (NVIDIA Container Toolkit)](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/cdi-support.html)
- [GPU container access (Podman Desktop)](https://podman-desktop.io/docs/podman/gpu)

---

### 13. Podman Cgroup v2 Tuning

**Impact: LOW | Effort: LOW | Risk: LOW**

**What to change:**
Verify cgroup v2 is active (it should be on Fedora 43) and apply container-level cgroup tuning.

**Relevant optimizations:**

- **Cgroup pinning**: Can reduce latency by up to 35% for latency-sensitive containers (AI inference services).
- **Cgroup v2 delegation**: Ensure proper delegation for rootless containers via `systemd-run --user --scope`.
- **CPU pinning for AI services**: Use `--cpuset-cpus` to pin AI inference containers to specific CPU cores, reducing context switch overhead.

**Implementation (in compose):**

```yaml
ai-llm:
  cpuset: '0-3' # Pin to cores 0-3 for predictable performance
ai-yolo26:
  cpuset: '4-5' # Pin to cores 4-5
```

**Expected impact:** Small but measurable latency reduction for AI inference. Most benefit comes from reducing CPU cache thrashing in multi-container environments.

**Risks:** Minimal. CPU pinning can reduce overall system flexibility but improves per-service predictability.

---

## Summary: Optimization Priority Matrix

| Priority | Optimization                     | Memory Savings | Effort | Risk    |
| -------- | -------------------------------- | -------------- | ------ | ------- |
| **1**    | Replace Jaeger+ES with Tempo     | ~5.5GB         | Medium | Low     |
| **2**    | Upgrade Grafana 10.2 to 12.3     | 0 (same limit) | Low    | Low-Med |
| **3**    | Upgrade Alloy v1.0 to v1.9+      | 0              | Medium | Medium  |
| **4**    | Upgrade Prometheus v2.48 to v3.1 | 0              | Low    | Medium  |
| **5**    | Upgrade Loki 2.9.4 to 3.5.x      | 0              | Medium | Medium  |
| **6**    | Network segmentation             | 0              | Medium | Low     |
| **7**    | Remove duplicate scrape job      | Negligible     | Low    | None    |
| **8**    | Evaluate Quadlet migration       | 0              | High   | Medium  |
| **9**    | Do NOT adopt Mimir               | N/A            | N/A    | N/A     |
| **10**   | Keep eBPF profiling              | N/A            | N/A    | N/A     |
| **11**   | Keep cAdvisor + Node Exporter    | N/A            | N/A    | N/A     |
| **12**   | Update NVIDIA toolkit            | 0              | Low    | Low     |
| **13**   | Cgroup v2 CPU pinning            | 0              | Low    | Low     |

**Recommended implementation order:** 1 > 7 > 2 > 3 > 4 > 5 > 6 > 12 > 13

Items 1 and 7 are quick wins that should be done together. Items 2-5 are version upgrades that should be done one at a time with testing between each. Item 6 (network segmentation) should be done after all version upgrades are stable. Items 8 (Quadlet) should be deferred to a future phase.

---

## Appendix: Version Upgrade Quick Reference

| Component         | Current | Target  | Breaking Changes                                    |
| ----------------- | ------- | ------- | --------------------------------------------------- |
| Prometheus        | v2.48.0 | v3.1.0  | PromQL changes, UTF-8 default, config deprecations  |
| Grafana           | 10.2.3  | 12.3.2  | Legacy alerting removed, plugin API changes         |
| Loki              | 2.9.4   | 3.5.8   | BoltDB removed, 15-label limit, no busybox in image |
| Alloy             | v1.0.0  | v1.9.2  | Component config syntax changes                     |
| Jaeger            | 1.54    | REMOVED | Replaced by Tempo                                   |
| Elasticsearch     | 8.12.0  | REMOVED | Replaced by Tempo                                   |
| Tempo             | N/A     | 2.7.1   | NEW service                                         |
| Alertmanager      | v0.27.0 | v0.28.0 | Minimal changes                                     |
| cAdvisor          | v0.49.1 | v0.51.0 | Minimal changes                                     |
| Node Exporter     | v1.8.2  | v1.9.0  | Minimal changes                                     |
| Blackbox Exporter | v0.24.0 | v0.26.0 | Minimal changes                                     |
