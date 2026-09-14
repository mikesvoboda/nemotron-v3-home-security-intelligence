# Platform Health Check Report
**Generated:** 2026-02-22

## 1. Container Status

| Service | Status | Notes |
|---------|--------|-------|
| postgres | ✅ healthy | Up 30 min |
| redis | ✅ healthy | Up 30 min |
| ai-llm (Nemotron) | ✅ healthy | Up 29 min |
| ai-gateway | ✅ starting→running | Up 2 min, GPU working |
| backend | ⚠️ unhealthy | Readiness returns 503 |
| frontend | ✅ healthy | Up 28 min |
| go2rtc | ✅ healthy | Video streaming |
| prometheus | ✅ healthy | |
| grafana | ✅ healthy | |
| alertmanager | ✅ healthy | |
| loki | ✅ healthy | |
| tempo | ✅ healthy | |
| pyroscope | ✅ healthy | |
| node-exporter | ✅ healthy | |
| blackbox-exporter | ✅ healthy | |

## 2. Core Services

| Endpoint | Status | Response |
|----------|--------|----------|
| Backend /health | ✅ 200 | Liveness OK |
| Backend /ready | ⚠️ 503 | not_ready |
| Backend /api/system/health | ✅ healthy | database, redis, ai OK |
| Backend /api/system/health/ready | ⚠️ 503 | supervisor_healthy: false |
| AI Gateway /health | ✅ 200 | 11/14 models loaded |
| LLM /health | ✅ 200 | {"status":"ok"} |
| Frontend HTTPS :8444 | ✅ 200 | |

## 3. AI Gateway Models (Triton)

| Model | Loaded | Health Endpoint |
|-------|--------|-----------------|
| clip | ✅ | 200 |
| clip_text | ✅ | - |
| demographics_age | ✅ | - |
| demographics_gender | ✅ | - |
| depth | ✅ | - |
| fashion_clip | ✅ | - |
| florence2 | ✅ | - |
| pose | ✅ | - |
| reid | ✅ | - |
| threat | ✅ | - |
| vehicle | ✅ | - |
| **yolo26** | ❌ | ONNX runtime error |
| **pet** | ❌ | Config shape mismatch |
| **xclip_action** | ❌ | HF path validation |
| **stgcn_action** | ❌ | No model files |

**Models loaded:** 11/14 | **Triton ready:** false (strict_readiness)

## 4. Infrastructure

| Component | Status |
|-----------|--------|
| PostgreSQL | ✅ pg_isready OK |
| Redis | ✅ ping OK (auth required from host) |
| GPU (A100 80GB) | ✅ 33.8 GB / 81.9 GB used |

## 5. Monitoring

| Service | Status |
|---------|--------|
| Prometheus :9090/-/healthy | ✅ 200 |
| Grafana :3002/api/health | ✅ 200 |

## 6. Issues Summary

1. **Backend unhealthy** – Healthcheck uses `/api/system/health/ready` which returns 503. Readiness requires `pipeline_workers_healthy` (detection + analysis workers running). `supervisor_healthy: false` suggests pipeline workers may not be fully started.

2. **YOLO26 unavailable** – ONNX runtime provider error in Triton. Detection pipeline depends on YOLO26; detection worker may fail or be stuck.

3. **Pet, xclip_action, stgcn_action** – Models not loaded (config/path/missing files).

4. **Readiness vs health** – `/health` returns 200 (liveness OK). `/ready` returns 503 because pipeline workers (detection, analysis) are not considered healthy.

## 7. Recommendations

- Fix YOLO26 ONNX export/provider compatibility.
- Check backend logs for detection/analysis worker startup failures.
- Consider relaxing Triton `strict_readiness` to avoid 120s startup delay when some models fail.
