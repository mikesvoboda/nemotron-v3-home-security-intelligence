# AI Services Startup - Quick Start

Quick reference for starting and managing AI inference services.

## Prerequisites

1. **NVIDIA GPU** with CUDA support (RTX A5500 or similar)
2. **llama-server** installed (from llama.cpp)
3. **Python 3.10+** with dependencies installed
4. **Model files** downloaded

## Quick Start

### 1. Download Models (First Time Only)

```bash
./ai/download_models.sh
```

Downloads:

- Nemotron Mini 4B Instruct (Q4_K_M) - ~2.5GB
- YOLO26 model info (auto-downloads on first use)

### 2. Start All AI Services

```bash
./scripts/start-ai.sh start
```

This starts:

- **YOLO26 Detection Server** on port 8090 (~4GB VRAM)
- **Nemotron LLM Server** on port 8091 (~3GB VRAM)

First startup takes 2-3 minutes for model loading and GPU warmup.

### 3. Check Status

```bash
./scripts/start-ai.sh status
```

Shows running services, PIDs, health status, and GPU usage.

### 4. Test Services

```bash
# Quick health check
./scripts/start-ai.sh health

# Manual health checks
curl http://localhost:8090/health  # YOLO26
curl http://localhost:8091/health  # Nemotron
```

## Service Management

```bash
# Start services
./scripts/start-ai.sh start

# Stop services
./scripts/start-ai.sh stop

# Restart services
./scripts/start-ai.sh restart

# Check status
./scripts/start-ai.sh status

# Health check
./scripts/start-ai.sh health
```

## Service Endpoints

### YOLO26 Detection Server (Port 8090)

```bash
# Health check
GET http://localhost:8090/health

# Single image detection
POST http://localhost:8090/detect
Content-Type: multipart/form-data
Body: file=<image>

# Batch detection
POST http://localhost:8090/detect/batch
Content-Type: multipart/form-data
Body: files=<image1>, files=<image2>, ...
```

### Nemotron LLM Server (Port 8091)

```bash
# Health check
GET http://localhost:8091/health

# Text completion
POST http://localhost:8091/completion
Content-Type: application/json
Body: {
  "prompt": "Your prompt here",
  "temperature": 0.7,
  "max_tokens": 500
}

# OpenAI-compatible chat
POST http://localhost:8091/v1/chat/completions
```

## Log Files

Services log to:

- YOLO26: `/tmp/yolo26-detector.log`
- Nemotron LLM: `/tmp/nemotron-llm.log`

View logs:

```bash
tail -f /tmp/yolo26-detector.log
tail -f /tmp/nemotron-llm.log
```

## Resource Usage

| Service   | VRAM     | CPU        | Latency | Port |
| --------- | -------- | ---------- | ------- | ---- |
| YOLO26 | ~4GB     | 10-20%     | 30-50ms | 8090 |
| Nemotron  | ~3GB     | 5-10%      | 2-5s    | 8091 |
| **Total** | **~7GB** | **15-30%** | -       | -    |

## Troubleshooting

### Services Won't Start

1. **Check prerequisites**:

   ```bash
   nvidia-smi                    # NVIDIA GPU
   which llama-server           # llama.cpp
   python3 --version            # Python 3.10+
   ```

2. **Check logs**:

   ```bash
   tail -f /tmp/yolo26-detector.log
   tail -f /tmp/nemotron-llm.log
   ```

3. **Common issues**:
   - **CUDA out of memory**: Close other GPU applications
   - **llama-server not found**: Install llama.cpp (see docs/operator/ai-installation.md)
   - **Model not found**: Run `./ai/download_models.sh`

### Services Unhealthy

```bash
# Restart services
./scripts/start-ai.sh restart

# Check GPU usage
nvidia-smi

# Verify processes
ps aux | grep -E "python.*model.py|llama-server"
```

### Port Already in Use

```bash
# Find and kill process using port
lsof -ti:8090 | xargs kill -9  # YOLO26
lsof -ti:8091 | xargs kill -9  # Nemotron

# Restart services
./scripts/start-ai.sh start
```

## Alternative: Individual Service Startup

If you need to start services separately:

```bash
# YOLO26 (terminal 1)
./ai/start_detector.sh

# Nemotron LLM (terminal 2)
./ai/start_llm.sh
```

## Integration with Backend

The FastAPI backend automatically connects to these services:

```python
# Backend configuration (backend/core/config.py)
yolo26_url: str = "http://localhost:8090"      # YOLO26
nemotron_url: str = "http://localhost:8091"    # Nemotron
```

Backend services that use AI:

- `backend/services/detector_client.py` - Calls YOLO26
- `backend/services/nemotron_analyzer.py` - Calls Nemotron LLM

## Full Documentation

For comprehensive setup instructions, troubleshooting, and performance tuning:

**See: `docs/operator/ai-installation.md`**

Topics covered:

- Detailed hardware requirements
- Software prerequisites and installation
- llama.cpp build instructions
- Performance tuning and optimization
- Production deployment with systemd
- Monitoring and logging
- Troubleshooting guide

## Development Workflow

1. **Start AI services**: `./scripts/start-ai.sh start`
2. **Start backend**: `cd backend && uvicorn main:app --reload`
3. **Start frontend**: `cd frontend && npm run dev`
4. **Check status**: `./scripts/start-ai.sh status`
5. **Stop services**: `./scripts/start-ai.sh stop` (when done)

## Production Deployment

For production use, consider:

1. **Systemd service units** - Auto-start on boot
2. **Resource monitoring** - Prometheus + Grafana
3. **Log rotation** - logrotate configuration
4. **Health checks** - Automated monitoring

See `docs/operator/ai-installation.md` for details.

## Quick Commands Reference

```bash
# Setup (first time)
./ai/download_models.sh
./scripts/start-ai.sh start

# Daily operations
./scripts/start-ai.sh status    # Check status
./scripts/start-ai.sh health    # Test endpoints
./scripts/start-ai.sh restart   # Restart if needed

# Debugging
tail -f /tmp/yolo26-detector.log
tail -f /tmp/nemotron-llm.log
nvidia-smi
curl http://localhost:8090/health
curl http://localhost:8091/health

# Cleanup
./scripts/start-ai.sh stop
```

## Support

- **Full documentation**: `docs/operator/ai-installation.md`
- **AI pipeline overview**: `ai/AGENTS.md`
- **YOLO26 details**: `ai/yolo26/README.md`
- **Nemotron details**: `ai/nemotron/AGENTS.md`
