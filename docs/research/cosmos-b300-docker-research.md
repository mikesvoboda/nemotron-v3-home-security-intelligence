# Cosmos Predict 2.5 on NVIDIA B300 Blackwell GPUs - Docker Container Research

**Date:** 2026-01-27
**Target Hardware:** 8x NVIDIA B300 SXM6 (Blackwell, compute capability 10.3, 267GB VRAM each)
**Goal:** Find prebuilt Docker container with full Blackwell sm_103 support for Cosmos video generation

---

## Problem Statement

PyTorch's NVRTC (runtime CUDA compiler) fails with:

```
nvrtc: error: invalid value for --gpu-architecture (-arch)
```

This occurs because PyTorch's JIT compilation lacks proper B300/sm_103 architecture support, even when flash-attn and transformer-engine are successfully compiled for sm_100.

---

## Key Finding: B300 = sm_103 (not sm_100)

B300 SXM6 GPUs use compute capability **10.3 (sm_103)**, which is different from B100/B200 (sm_100). This distinction is critical - many "Blackwell" containers only support sm_100.

| GPU            | Compute Capability | CUDA Arch |
| -------------- | ------------------ | --------- |
| B100/B200      | 10.0               | sm_100    |
| B300/GB300     | 10.3               | sm_103    |
| RTX 50-series  | 12.0               | sm_120    |
| DGX Spark/GB10 | 12.1               | sm_121    |

---

## Recommended Container Options

### 1. Cosmos Predict 2.5 with nightly.Dockerfile (Best Option)

The official Cosmos repository has a dedicated Blackwell Dockerfile:

```bash
git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git
cd cosmos-predict2.5

# Build Blackwell-specific container
docker build -f docker/nightly.Dockerfile -t cosmos-blackwell .
```

**Base image:** `nvcr.io/nvidia/pytorch:25.10-py3` (CUDA 13.0)

**Note:** Blackwell + ARM inference support was added November 25, 2025

**Source:** https://github.com/nvidia-cosmos/cosmos-predict2.5

---

### 2. NGC PyTorch 25.12-py3 (Latest with CUDA 13.1)

```bash
docker pull nvcr.io/nvidia/pytorch:25.12-py3
```

| Feature             | Version           |
| ------------------- | ----------------- |
| CUDA                | 13.1.0            |
| Release Date        | Dec 22, 2025      |
| Blackwell Optimized | Yes (since 25.01) |

**Source:** https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-25-12.html

---

### 3. NGC Cosmos Predict2 Container 1.1

```bash
docker pull nvcr.io/nvidia/cosmos/cosmos-predict2-container:1.1
```

Pre-built with inference and post-training support, but may not have full sm_103 support. Test with your B300s.

**Source:** https://catalog.ngc.nvidia.com/orgs/nvidia/teams/cosmos/containers/cosmos-predict2-container

---

## Critical sm_103 Triton Issue

The NVRTC error is a known problem. As of December 2025:

- **PyTorch stable (2.9.1+cu130)** ships with Triton that lacks sm_103 compilation support
- **PyTorch nightly (2.11.0.dev+cu130)** fixes this issue

**Source:** https://github.com/vllm-project/vllm/issues/30245

### Workarounds

1. **Use NGC containers 25.10+** - They include custom Triton builds with Blackwell support

2. **Build Triton from source** - SGLang and vLLM teams use this workaround:

   ```bash
   pip install --pre triton-nightly
   ```

3. **Use Cosmos nightly.Dockerfile** - Built specifically for Blackwell edge cases

---

## Container Comparison Matrix

| Container                                  | CUDA   | sm_103 | Cosmos Ready   | Notes            |
| ------------------------------------------ | ------ | ------ | -------------- | ---------------- |
| `cosmos-predict2.5` + `nightly.Dockerfile` | 13.0   | ✅     | ✅             | **Recommended**  |
| `nvcr.io/nvidia/pytorch:25.12-py3`         | 13.1   | ⚠️     | Manual install | Best base image  |
| `nvcr.io/nvidia/pytorch:25.11-py3`         | 13.0.2 | ⚠️     | Manual install | CUDA 13.0 stable |
| `cosmos-predict2-container:1.1`            | Varies | ❓     | ✅             | Test on B300     |

⚠️ = Supported but may need Triton fixes
❓ = Untested on sm_103

---

## Recommended Approach

```bash
# 1. Clone Cosmos Predict 2.5
git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git
cd cosmos-predict2.5

# 2. Build Blackwell container (uses nightly.Dockerfile)
docker build -f docker/nightly.Dockerfile -t cosmos-b300 .

# 3. Run with your B300 GPUs
docker run --gpus all --ipc=host \
  -v /path/to/checkpoints:/workspace/checkpoints \
  -e HF_TOKEN="$HF_TOKEN" \
  cosmos-b300
```

**Source:** https://github.com/nvidia-cosmos/cosmos-predict2.5/blob/main/docs/setup.md

---

## If Problems Persist

If the nightly.Dockerfile still fails with NVRTC errors on B300:

### Option A: Update Base Image

Edit `docker/nightly.Dockerfile`:

```dockerfile
ARG BASE_IMAGE=nvcr.io/nvidia/pytorch:25.12-py3
```

### Option B: Add Triton Nightly

Add after pip install in Dockerfile:

```dockerfile
RUN pip install --pre triton-nightly
```

### Option C: Set CUDA Arch Explicitly

```bash
export TORCH_CUDA_ARCH_LIST="10.3"
```

### Option D: Build Custom Container

Create a custom Dockerfile combining latest NGC PyTorch with Cosmos:

```dockerfile
FROM nvcr.io/nvidia/pytorch:25.12-py3

# Install Triton nightly for sm_103 support
RUN pip install --pre triton-nightly

# Install Cosmos dependencies
RUN pip install transformers accelerate diffusers

# Clone and install Cosmos
RUN git clone https://github.com/nvidia-cosmos/cosmos-predict2.5.git /opt/cosmos
WORKDIR /opt/cosmos
RUN pip install -e .

# Set CUDA arch for B300
ENV TORCH_CUDA_ARCH_LIST="10.3"
```

---

## NGC PyTorch Release Timeline for Blackwell

| Release | CUDA   | Blackwell Notes                |
| ------- | ------ | ------------------------------ |
| 25.01   | 12.x   | First Blackwell optimization   |
| 25.05   | 12.x   | TensorRT-LLM base image        |
| 25.10   | 13.0   | Cosmos nightly.Dockerfile base |
| 25.11   | 13.0.2 | CUDA 13 stable                 |
| 25.12   | 13.1.0 | **Latest**, recommended base   |

---

## System Requirements

From Cosmos documentation:

- NVIDIA GPUs with Ampere or newer architecture
- NVIDIA driver >=570.124.06 compatible with CUDA 12.8.1
- Linux x86-64 operating system
- glibc version 2.35 or higher (Ubuntu 22.04+)
- Docker with NVIDIA Container Toolkit installed
- **For Blackwell: CUDA 13.0 is mandatory**

---

## NVIDIA NIM Alternative

NVIDIA offers Cosmos as a NIM (NVIDIA Inference Microservice):

```bash
# Cosmos NIM for Predict1 (not Predict2.5 yet)
docker pull nvcr.io/nim/nvidia/cosmos-predict1-7b-text2world
```

**Hardware Requirements:**

- NVIDIA GPUs with Ampere architecture or later
- x86_64 architecture only (currently)
- At least 90GB RAM
- At least 100GB disk space

**Note:** NIM containers may lag behind the open-source Cosmos releases for Blackwell support.

**Source:** https://docs.nvidia.com/nim/cosmos/latest/quickstart-guide.html

---

## Sources

- [Cosmos-Predict2.5 GitHub](https://github.com/nvidia-cosmos/cosmos-predict2.5)
- [Cosmos Setup Documentation](https://github.com/nvidia-cosmos/cosmos-predict2.5/blob/main/docs/setup.md)
- [NGC PyTorch Containers](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/pytorch)
- [PyTorch 25.12 Release Notes](https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-25-12.html)
- [PyTorch 25.11 Release Notes](https://docs.nvidia.com/deeplearning/frameworks/pytorch-release-notes/rel-25-11.html)
- [vLLM sm_103 Issue #30245](https://github.com/vllm-project/vllm/issues/30245)
- [vLLM GB300 deep_gemm Issue #32647](https://github.com/vllm-project/vllm/issues/32647)
- [Cosmos Installation Docs](https://docs.nvidia.com/cosmos/latest/predict2/installation.html)
- [NGC Cosmos Container](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/cosmos/containers/cosmos-predict2-container)
- [NVIDIA B200 & B300 Software Stack](https://verda.com/blog/nvidia-b200-and-b300-gpu-architecture-and-software-stack)
- [NVIDIA NIM Cosmos Quickstart](https://docs.nvidia.com/nim/cosmos/latest/quickstart-guide.html)
- [PyTorch Enable CUDA 13.0 Binaries Issue #159779](https://github.com/pytorch/pytorch/issues/159779)
- [TensorRT-LLM Release Notes](https://nvidia.github.io/TensorRT-LLM/release-notes.html)
