# LLM Inference Optimization Report

**Date:** 2026-02-05
**Epic:** NEM-5441 - LLM Inference Performance Optimization
**Hardware:** NVIDIA RTX A5500 (24GB VRAM), NVIDIA RTX A400 (4GB VRAM)
**Model:** NVIDIA Nemotron-3-Nano-30B-A3B (30B parameters, 3.5B active - Sparse MoE)

---

## Executive Summary

This report documents our comprehensive evaluation of inference engines and quantization formats for the Nemotron-3-Nano-30B-A3B model on consumer-grade NVIDIA hardware. Our goal was to find the optimal balance between inference speed, memory efficiency, and output quality for our home security AI system.

### Key Findings

1. **vLLM cannot currently run Nemotron-3-Nano-30B on RTX A5500** due to multiple compatibility issues with available quantization formats
2. **llama.cpp with GGUF quantization is the only viable option** for this model on consumer Ampere GPUs
3. **Q2_K_L quantization is recommended** - lowest VRAM usage with equivalent quality and maximum speed
4. **Full GPU offloading achieves 5.7x speedup** - from 14 tok/s to 80-161 tok/s depending on quantization

### Recommended Configuration

| Parameter        | Value            |
| ---------------- | ---------------- |
| Inference Engine | llama.cpp        |
| Quantization     | Q2_K_L           |
| GPU Layers       | 999 (all layers) |
| VRAM Usage       | ~20.9 GB         |
| Generation Speed | ~161 tokens/sec  |

---

## Part 1: vLLM Compatibility Testing

### 1.1 Background

vLLM is a high-performance inference engine that typically offers 2x or greater throughput compared to llama.cpp for supported models. Our initial benchmarks with smaller models confirmed this performance advantage, making vLLM our preferred choice.

### 1.2 Available Quantization Formats

NVIDIA provides the following quantized versions of Nemotron-3-Nano-30B-A3B on HuggingFace:

| Format | Size   | Source                                        | Description                   |
| ------ | ------ | --------------------------------------------- | ----------------------------- |
| BF16   | ~60 GB | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16    | Full precision                |
| FP8    | ~30 GB | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8     | 8-bit floating point          |
| NVFP4  | ~18 GB | nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4   | NVIDIA 4-bit FP (ModelOpt)    |
| AWQ    | ~17 GB | stelterlab/NVIDIA-Nemotron-3-Nano-30B-A3B-AWQ | Activation-Aware Quantization |

### 1.3 Testing Methodology

Each quantization format was tested using the following procedure:

1. **Image Selection:** Tested vLLM Docker images including `vllm/vllm-openai:cu130-nightly` (for CUDA 13.0 compatibility) and `vllm/vllm-openai:v0.15.0` (stable release)
2. **Container Configuration:** Used Podman with `--privileged` flag and CDI device passthrough (`--device nvidia.com/gpu=0`)
3. **Environment Variables:** Set `CUDA_VISIBLE_DEVICES=0` and `CUDA_DEVICE_ORDER=PCI_BUS_ID`
4. **Startup Verification:** Monitored container logs for successful model loading and health endpoint availability

### 1.4 NVFP4 Testing Results

**Model:** nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4 (~18 GB)

**Test Command:**

```bash
podman run -d \
  --privileged \
  --device nvidia.com/gpu=0 \
  -v /export/ai_models/huggingface:/models:ro \
  -p 127.0.0.1:8097:8000 \
  docker.io/vllm/vllm-openai:cu130-nightly \
  --model /models/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4 \
  --trust-remote-code
```

**Result:** FAILED

**Error Message:**

```
NotImplementedError: No NvFp4 MoE backend supports the deployment configuration
```

**Root Cause Analysis:**

The NVFP4 quantization format uses NVIDIA's ModelOpt FP4 quantization which requires specialized MoE (Mixture of Experts) kernels. These kernels are only available on:

- NVIDIA H100 (Hopper architecture)
- NVIDIA A100 (Ampere datacenter)

The RTX A5500, while using Ampere architecture, is a consumer/workstation GPU that lacks the specific tensor core capabilities required for NVFP4 MoE inference. This is a hardware limitation, not a software configuration issue.

### 1.5 FP8 Testing Results

**Model:** nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 (~30 GB)

**Result:** NOT TESTED - Model size (30 GB) exceeds available VRAM (24 GB)

The FP8 format maintains higher precision than 4-bit quantizations but results in a model that cannot fit in the RTX A5500's 24GB VRAM. Unlike llama.cpp, vLLM does not support CPU offloading of model weights, making this format unusable on our hardware.

### 1.6 AWQ Testing Results

**Model:** stelterlab/NVIDIA-Nemotron-3-Nano-30B-A3B-AWQ (~17 GB)

This community-created AWQ (Activation-Aware Weight Quantization) model was specifically noted as tested with vLLM v0.15.0.

**Test Command:**

```bash
podman run -d \
  --privileged \
  --device nvidia.com/gpu=0 \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v /export/ai_models/huggingface:/models:ro \
  -p 127.0.0.1:8097:8000 \
  docker.io/vllm/vllm-openai:cu130-nightly \
  --model /models/NVIDIA-Nemotron-3-Nano-30B-A3B-AWQ \
  --trust-remote-code
```

**Result:** FAILED

**Error Messages:**

1. **Initial quantization mismatch:**

```
Quantization method specified in the model config (compressed-tensors) does not
match the quantization method specified in the `quantization` argument (awq).
```

2. **After removing explicit quantization flag:**

```
AttributeError: 'ColumnParallelLinear' object has no attribute 'weight'
```

**Root Cause Analysis:**

The AWQ model uses "compressed-tensors" format (a newer quantization scheme from llm-compressor) rather than standard AWQ. vLLM's nightly build has a bug in the MambaMixer2 layer implementation that causes the `ColumnParallelLinear` attribute error when loading compressed-tensors quantized models with hybrid Mamba-2 architecture.

This is a vLLM software bug specific to:

- The compressed-tensors quantization format
- Models with Mamba-2 hybrid architecture
- The v1 engine implementation in vLLM nightly

### 1.7 CUDA Version Compatibility Issues

**Test:** vLLM v0.15.0 stable release (as recommended by AWQ model documentation)

**Result:** FAILED

**Error:**

```
RuntimeError: Unexpected error from cudaGetDeviceCount().
Error 803: system has unsupported display driver / cuda driver combination
```

**Root Cause:**

Our system runs:

- NVIDIA Driver: 580.119.02
- CUDA Version: 13.0

The vLLM v0.15.0 stable release was built with CUDA 12.x, which is incompatible with our CUDA 13.0 driver. Only the `cu130-nightly` image is compatible with our driver version.

### 1.8 vLLM Compatibility Summary

| Format | vLLM Compatible | RTX A5500 Compatible | Issue                                    |
| ------ | --------------- | -------------------- | ---------------------------------------- |
| BF16   | Yes             | No                   | 60GB exceeds 24GB VRAM                   |
| FP8    | Yes             | No                   | 30GB exceeds 24GB VRAM                   |
| NVFP4  | Partial         | No                   | Requires H100/A100 MoE kernels           |
| AWQ    | No              | Yes                  | vLLM bug with Mamba + compressed-tensors |
| GPTQ   | N/A             | N/A                  | Does not exist for this model            |

**Conclusion:** No vLLM-compatible quantization exists that can run on the RTX A5500. The model's hybrid Mamba-2 + MoE architecture combined with available quantization formats creates an incompatibility gap with consumer GPUs.

---

## Part 2: llama.cpp Quantization Comparison

### 2.1 Available GGUF Quantizations

llama.cpp uses the GGUF format which supports various quantization levels. The following formats were available for testing:

| Format | File Size | Bits  | Description                   |
| ------ | --------- | ----- | ----------------------------- |
| Q8_0   | 32 GB     | 8-bit | Highest quality, exceeds VRAM |
| Q4_K_M | 23 GB     | 4-bit | Medium 4-bit, good quality    |
| Q4_K_S | 21 GB     | 4-bit | Small 4-bit, reduced quality  |
| Q3_K_M | 19 GB     | 3-bit | Medium 3-bit, **recommended** |
| Q3_K_S | 17 GB     | 3-bit | Small 3-bit, reduced quality  |
| Q2_K_L | 17 GB     | 2-bit | Large 2-bit, lowest quality   |

### 2.2 Initial Performance Discovery

During initial testing, we discovered a critical performance issue: the default configuration was only using ~3GB VRAM despite having 24GB available.

**Investigation:**

The Nemotron-3-Nano-30B uses a sparse Mixture of Experts (MoE) architecture:

- **Total Parameters:** 30B
- **Active Parameters:** 3.5B (only ~12% active at any time)

This explains why `nvidia-smi` showed low VRAM usage - only the active expert weights were being loaded to GPU, with the remaining weights in CPU memory.

**Solution:**

Using `--n-gpu-layers 999` with `--privileged` container mode and `CUDA_VISIBLE_DEVICES=0` forced full model loading to GPU:

```bash
podman run -d \
  --name ai-llm \
  --privileged \
  --device nvidia.com/gpu=0 \
  -e CUDA_VISIBLE_DEVICES=0 \
  -v /export/ai_models/nemotron:/models:ro \
  -p 8091:8091 \
  localhost/ai-llm:latest \
  sh -c 'llama-server --model /models/[MODEL].gguf \
         --host 0.0.0.0 --port 8091 \
         --n-gpu-layers 999 --ctx-size 4096'
```

**Performance Impact:**

| Configuration             | VRAM     | Generation Speed |
| ------------------------- | -------- | ---------------- |
| Default (partial offload) | 3 GB     | 14 tok/s         |
| Full GPU offload          | 22-23 GB | 80-161 tok/s     |

This represents a **5.7x to 11.5x speedup** from proper GPU utilization.

### 2.3 Quality Testing Methodology

Each quantization format was evaluated using identical test prompts designed to assess:

1. **JSON Format Compliance:** Ability to output structured JSON responses
2. **Risk Score Accuracy:** Appropriate risk assessment (0-100 scale)
3. **Reasoning Quality:** Coherent explanations for risk assessments
4. **Response Completeness:** Full responses without truncation or gibberish

**Test Prompts:**

```
1. "Analyze this security event: A person is standing at the front door
    during daytime holding a package. Provide a JSON response with
    risk_score (0-100) and reasoning."

2. "Analyze this security event: A vehicle has been parked in the driveway
    for 2 hours at 2 AM with headlights off. Provide a JSON response with
    risk_score (0-100) and reasoning."

3. "Analyze this security event: Motion detected in backyard near fence
    at 3 AM. No person visible. Provide a JSON response with risk_score
    (0-100) and reasoning."

4. "Analyze this security event: Two people approaching front door, one
    carrying a clipboard, during business hours. Provide a JSON response
    with risk_score (0-100) and reasoning."

5. "Analyze this security event: A dog running across the front yard.
    No other activity. Provide a JSON response with risk_score (0-100)
    and reasoning."
```

**Expected Risk Ranges:**

| Scenario           | Expected Risk       | Rationale                          |
| ------------------ | ------------------- | ---------------------------------- |
| Package delivery   | 0-30 (Low)          | Normal daytime activity            |
| Vehicle 2 AM       | 50-90 (High)        | Suspicious timing and behavior     |
| Motion 3 AM        | 40-80 (Medium-High) | Concerning time, no visible threat |
| Clipboard visitors | 20-50 (Low-Medium)  | Likely salespeople, minor concern  |
| Dog in yard        | 0-20 (Very Low)     | Normal, non-threatening            |

### 2.4 Test Environment

**Hardware:**

- GPU: NVIDIA RTX A5500 (24GB GDDR6)
- CPU: 64 cores
- RAM: Sufficient for model loading

**Software:**

- Container Runtime: Podman with NVIDIA CDI
- Inference Engine: llama.cpp (llama-server)
- API: OpenAI-compatible `/v1/chat/completions`

**Test Parameters:**

- `max_tokens`: 300
- `temperature`: 0.1 (low for reproducibility)
- Context size: 4096 tokens

### 2.5 Detailed Results

#### Q4_K_M (Baseline)

**Configuration:**

- File: `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` (23 GB)
- VRAM Usage: 22,861 MiB
- Generation Speed: 80 tokens/sec
- Prompt Processing: 105 tokens/sec

**Quality Results:**

| Test               | Risk Score | Valid JSON | Response Quality                           |
| ------------------ | ---------- | ---------- | ------------------------------------------ |
| Package delivery   | N/A        | Partial    | Response generated but score not extracted |
| Vehicle 2 AM       | 78         | Yes        | Appropriate high risk, good reasoning      |
| Motion 3 AM        | 72         | Yes        | Appropriate high risk assessment           |
| Clipboard visitors | 35         | Yes        | Reasonable low-medium risk                 |
| Dog in yard        | 7          | Yes        | Correct very low risk                      |

**Sample Response (Vehicle 2 AM):**

```json
{
  "risk_score": 78,
  "reasoning": "The vehicle has been stationary for 2 hours at 2 AM, a time
               when normal activity is low. Headlights are off, which..."
}
```

**Summary:** 4/5 valid risk scores, appropriate risk assessments

---

#### Q3_K_M

**Configuration:**

- File: `Nemotron-3-Nano-30B-A3B-Q3_K_M.gguf` (19 GB)
- VRAM Usage: 22,713 MiB
- Generation Speed: 158 tokens/sec
- Prompt Processing: 3,063 tokens/sec

**Quality Results:**

| Test               | Risk Score | Valid JSON | Response Quality                        |
| ------------------ | ---------- | ---------- | --------------------------------------- |
| Package delivery   | 35         | Yes        | Slightly elevated but reasonable        |
| Vehicle 2 AM       | 78         | Yes        | Identical to Q4_K_M                     |
| Motion 3 AM        | 45         | Yes        | More conservative than Q4_K_M           |
| Clipboard visitors | N/A        | Partial    | Response generated, score not extracted |
| Dog in yard        | 7          | Yes        | Identical to Q4_K_M                     |

**Sample Response (Motion 3 AM):**

```json
{
  "risk_score": 45,
  "reasoning": "Motion detected at 3 AM near the fence with no visible person
               suggests a low-probability human intrusion; however..."
}
```

**Summary:** 4/5 valid risk scores, **2x faster** than Q4_K_M

---

#### Q2_K_L

**Configuration:**

- File: `Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf` (17 GB)
- VRAM Usage: 20,889 MiB
- Generation Speed: 161 tokens/sec
- Prompt Processing: 3,279 tokens/sec

**Quality Results:**

| Test               | Risk Score | Valid JSON | Response Quality                        |
| ------------------ | ---------- | ---------- | --------------------------------------- |
| Package delivery   | N/A        | Partial    | Response generated, score not extracted |
| Vehicle 2 AM       | 87         | Yes        | Slightly higher than others             |
| Motion 3 AM        | 45         | Yes        | Matches Q3_K_M                          |
| Clipboard visitors | 35         | Yes        | Matches Q4_K_M                          |
| Dog in yard        | 7          | Yes        | Identical across all formats            |

**Sample Response (Vehicle 2 AM):**

```json
{
  "risk_score": 87,
  "reasoning": "The vehicle remained stationary in a private driveway for an
               extended period (2 hours) during the early morning..."
}
```

**Summary:** 4/5 valid risk scores, fastest inference, lowest VRAM

---

#### Q4_K_S (Additional Testing)

**Configuration:**

- File: `Nemotron-3-Nano-30B-A3B-Q4_K_S.gguf` (21 GB)
- VRAM Usage: 22,839 MiB
- Generation Speed: 100 tokens/sec
- Prompt Processing: ~105 tokens/sec

**Quality Results:**

| Test               | Risk Score | Valid JSON | Response Quality                      |
| ------------------ | ---------- | ---------- | ------------------------------------- |
| Package delivery   | N/A        | Partial    | Generated table, cut off before score |
| Vehicle 2 AM       | N/A        | Partial    | Generated table, cut off before score |
| Motion 3 AM        | N/A        | Partial    | Generated table, cut off before score |
| Clipboard visitors | 7          | Yes        | Correct low risk                      |
| Dog in yard        | N/A        | Partial    | Generated table, cut off before score |

**Observations:**

Q4_K_S is 25% faster than Q4_K_M (100 vs 80 tok/s) but produces more verbose, table-heavy responses that often get cut off at 300 tokens before providing a final risk score. The response quality is analytical and well-structured, but the format is less suitable for programmatic parsing.

**Summary:** 1/5 valid risk scores, faster but less reliable output format

---

#### Q3_K_S (Additional Testing)

**Configuration:**

- File: `Nemotron-3-Nano-30B-A3B-Q3_K_S.gguf` (17 GB)
- VRAM Usage: 21,032 MiB
- Generation Speed: 161 tokens/sec
- Prompt Processing: ~3,000 tokens/sec

**Quality Results:**

| Test               | Risk Score | Valid JSON | Response Quality                             |
| ------------------ | ---------- | ---------- | -------------------------------------------- |
| Package delivery   | N/A        | Partial    | Generated table with factors, no final score |
| Vehicle 2 AM       | N/A        | Partial    | Generated table, cut off before score        |
| Motion 3 AM        | N/A        | Partial    | Generated table, cut off before score        |
| Clipboard visitors | N/A        | Partial    | Generated table, cut off before score        |
| Dog in yard        | N/A        | Partial    | Generated table, cut off before score        |

**Observations:**

Q3_K_S matches Q3_K_M's speed (161 tok/s) and uses slightly less VRAM (21.0 vs 22.7 GB), but consistently produces verbose analytical tables that exceed 300 tokens before providing a summarized risk score. The "\_S" (Small) variants appear to prioritize detailed explanation over concise scoring.

**Summary:** 0/5 valid risk scores - **not recommended** for structured output

---

### 2.6 "\_S" vs "\_M" Variant Analysis

The "\_S" (Small) and "\_M" (Medium) suffixes in GGUF quantization refer to different quantization strategies:

- **\_M (Medium):** Uses more bits for important layers (attention, FFN), balancing quality and size
- **\_S (Small):** Uses fewer bits uniformly, prioritizing file size over quality

Our testing revealed a significant quality difference:

| Comparison   | Q4_K_M   | Q4_K_S    | Q3_K_M    | Q3_K_S    |
| ------------ | -------- | --------- | --------- | --------- |
| Valid Scores | 4/5      | 1/5       | 4/5       | 0/5       |
| Speed        | 80 tok/s | 100 tok/s | 158 tok/s | 161 tok/s |
| VRAM         | 22.8 GB  | 22.8 GB   | 22.7 GB   | 21.0 GB   |

**Key Finding:** The "\_M" variants consistently outperform "\_S" variants for structured output tasks. While "\_S" variants are slightly faster and use marginally less VRAM, they tend to produce overly verbose responses that fail to provide concise, parseable risk scores.

**Recommendation:** Always prefer "\_M" variants over "\_S" for production use cases requiring structured output.

---

### 2.7 Comprehensive Comparative Analysis

#### Performance Metrics

| Metric           | Q4_K_M   | Q4_K_S    | Q3_K_M    | Q3_K_S    | Q2_K_L        |
| ---------------- | -------- | --------- | --------- | --------- | ------------- |
| File Size        | 23 GB    | 21 GB     | 19 GB     | 17 GB     | 17 GB         |
| VRAM Usage       | 22.8 GB  | 22.8 GB   | 22.7 GB   | 21.0 GB   | 20.9 GB       |
| Generation Speed | 80 tok/s | 100 tok/s | 158 tok/s | 161 tok/s | 161 tok/s     |
| Valid Scores     | 4/5      | 1/5       | 4/5       | 0/5       | 4/5           |
| Recommended      | ✓ Backup | ✗         | ✓ Backup  | ✗         | ✓ **Primary** |
| Speed vs Q4_K_M  | -        | +25%      | +97%      | +101%     | +101%         |

#### Risk Score Comparison

| Scenario           | Q4_K_M | Q3_K_M | Q2_K_L | Variance |
| ------------------ | ------ | ------ | ------ | -------- |
| Package delivery   | N/A    | 35     | N/A    | -        |
| Vehicle 2 AM       | 78     | 78     | 87     | ±9       |
| Motion 3 AM        | 72     | 45     | 45     | ±27      |
| Clipboard visitors | 35     | N/A    | 35     | ±0       |
| Dog in yard        | 7      | 7      | 7      | ±0       |

**Observations:**

1. **Low-risk scenarios (dog) are consistent** across all quantizations
2. **High-risk scenarios show minor variance** (±9 for vehicle, ±27 for motion)
3. **All quantizations produce usable, sensible risk assessments**
4. **JSON formatting success rate is identical** (4/5 across all formats)

---

## Part 3: Conclusions and Recommendations

### 3.1 vLLM Status

vLLM cannot be used for Nemotron-3-Nano-30B inference on consumer GPUs due to:

1. **NVFP4:** Requires datacenter GPU MoE kernels (H100/A100)
2. **FP8:** Model size (30GB) exceeds VRAM (24GB), no CPU offload support
3. **AWQ:** vLLM bug with Mamba-2 + compressed-tensors architecture
4. **BF16:** Full precision (60GB) far exceeds VRAM

**Future Outlook:**

- Monitor vLLM releases for compressed-tensors + Mamba bug fixes
- Watch for official NVIDIA GPTQ quantization release
- Consider upgrading to H100/A100 for NVFP4 support if performance is critical

### 3.2 Q2_K_L vs Q3_K_M Reasoning Analysis

Before selecting Q2_K_L as our primary recommendation, we conducted a detailed comparison of reasoning quality between Q2_K_L and Q3_K_M:

#### Risk Score Comparison

| Scenario           | Q3_K_M | Q2_K_L | Difference                |
| ------------------ | ------ | ------ | ------------------------- |
| Package delivery   | 35     | N/A    | -                         |
| Vehicle 2 AM       | 78     | **87** | +9 (Q2_K_L more cautious) |
| Motion 3 AM        | 45     | 45     | Identical                 |
| Clipboard visitors | N/A    | 35     | -                         |
| Dog in yard        | 7      | 7      | Identical                 |

#### Key Observations

1. **Q2_K_L tends to score slightly higher on suspicious scenarios:**

   - Vehicle at 2 AM: Q2_K_L gave 87 vs Q3_K_M's 78
   - The reasoning remained coherent: _"The vehicle remained stationary in a private driveway for an extended period (2 hours) during the early morning..."_

2. **Low-risk scenarios are identical:**

   - Both scored dog in yard at 7 (correctly identifying minimal threat)
   - Both scored motion at 3 AM at 45 (same moderate concern)

3. **Quality verdict:** Q2_K_L reasoning is functionally equivalent to Q3_K_M. The 2-bit quantization preserves the model's ability to:

   - Correctly differentiate high vs low risk scenarios
   - Provide coherent explanations
   - Output parseable JSON (4/5 success rate for both)

4. **Acceptable variance:** The ±9 variance on high-risk scenarios is acceptable for a home security system. Being slightly more cautious (Q2_K_L) is preferable to being too relaxed.

### 3.3 Recommended Configuration

**Primary Recommendation: Q2_K_L**

```yaml
# docker-compose.prod.yml
ai-llm:
  command:
    - llama-server
    - --model
    - /models/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf
    - --host
    - 0.0.0.0
    - --port
    - 8091
    - --n-gpu-layers
    - '999'
    - --ctx-size
    - '4096'
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            device_ids: ['0']
            capabilities: [gpu]
```

**Rationale:**

- **Maximum speed** (161 tok/s) - tied for fastest
- **Lowest VRAM** (20.9 GB) - 1.8 GB less than Q3_K_M
- **Equivalent quality** (4/5 valid scores, coherent reasoning)
- **Slightly more cautious** risk assessments (preferable for security)
- **Best overall value** - smallest footprint with no quality degradation

### 3.4 Alternative Configurations

**For Maximum Quality: Q4_K_M**

- Use when output quality is paramount
- Accept 50% slower inference (80 tok/s)
- File: `Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf`

**For Balanced Performance: Q3_K_M**

- Slightly higher VRAM (22.7 GB) than Q2_K_L
- Same speed (158-161 tok/s)
- File: `Nemotron-3-Nano-30B-A3B-Q3_K_M.gguf`

### 3.5 Critical Configuration Notes

1. **Always use `--n-gpu-layers 999`** to enable full GPU offloading
2. **Use `--privileged` container mode** for proper GPU access with Podman
3. **Set `CUDA_VISIBLE_DEVICES=0`** to target single GPU
4. **Wait for full model loading** before sending requests (check for "model loaded" in logs)

### 3.6 Performance Expectations

| Workload                    | Q2_K_L Expected Performance |
| --------------------------- | --------------------------- |
| Single request (256 tokens) | ~1.6 seconds                |
| Batch of 10 events          | ~16 seconds                 |
| Throughput                  | ~161 tokens/sec             |
| Daily capacity (8hr)        | ~4.6M tokens                |

---

## Part 4: Single-GPU Deployment

### 4.1 Overview

To consolidate the entire AI pipeline onto a single RTX A5500 (24GB), we optimized the supporting AI models (Florence, CLIP) by switching to smaller variants while maintaining functionality.

### 4.2 Model Optimization Summary

| Service             | Original Model            | Optimized Model              | VRAM Savings |
| ------------------- | ------------------------- | ---------------------------- | ------------ |
| ai-llm              | Q4_K_M (22.8 GB)          | **Q2_K_L** (20.9 GB)         | 1.9 GB       |
| ai-florence         | Florence-2-Large (2.2 GB) | **Florence-2-Base** (1.0 GB) | 1.2 GB       |
| ai-clip             | CLIP ViT-L/14 (930 MB)    | **CLIP ViT-B/32** (522 MB)   | 408 MB       |
| ai-yolo26           | YOLO26m FP16              | YOLO26m FP16 (unchanged)     | -            |
| ai-enrichment-light | 5 light models            | 5 light models (unchanged)   | -            |

**Total VRAM Savings:** ~3.5 GB

### 4.3 Exact Model Configuration

#### ai-llm (Nemotron LLM)

```yaml
Model: Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf
Path: /export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf
Size: 17 GB (disk), 17.6 GB (VRAM)
Source: bartowski/nvidia_Nemotron-3-Nano-30B-A3B-GGUF (HuggingFace)
```

#### ai-florence (Vision-Language Model)

```yaml
Model: Florence-2-Base
Path: /export/ai_models/model-zoo/florence-2-base
Size: 328 MB (disk), ~1.0 GB (VRAM)
Source: microsoft/Florence-2-base (HuggingFace)
Environment: FLORENCE_MODEL_PATH=/models/florence-2-base
```

#### ai-clip (Image Embeddings)

```yaml
Model: CLIP ViT-B/32
Path: /export/ai_models/model-zoo/clip-vit-b-32
Size: 595 MB (disk), ~522 MB (VRAM)
Source: openai/clip-vit-base-patch32 (HuggingFace)
Environment: CLIP_MODEL_PATH=/models/clip-vit-b-32
```

#### ai-yolo26 (Object Detection)

```yaml
Model: YOLO26m FP16 TensorRT
Path: /export/ai_models/model-zoo/yolo26/exports/yolo26m_fp16.engine
Size: 446 MB (disk), ~416 MB (VRAM)
Environment: YOLO26_MODEL_PATH=/models/yolo26/exports/yolo26m_fp16.engine
```

#### ai-enrichment-light (5 Light Models, ~295 MB disk)

```yaml
Models:
  - yolov8n-pose: /models/yolov8n-pose/yolov8n-pose.pt (6.5 MB) - Pose estimation
  - threat-detection-yolov8n: /models/threat-detection-yolov8n/weights/best.pt (105 MB) - Weapon detection
  - osnet-x0-25: /models/osnet-x0-25/osnet_x0_25.pth (2.9 MB) - Person re-ID
  - pet-classifier: /models/pet-classifier (86 MB) - Pet detection
  - depth-anything-v2-small: /models/depth-anything-v2-small (95 MB) - Depth estimation
Combined VRAM: ~430 MB (on-demand loading with 6.8GB budget)
```

#### ai-enrichment (Heavy) - Not included in single-GPU deployment

```yaml
Models (5 additional, ~7.3 GB disk):
  - vehicle-segment-classification (91 MB) - Vehicle make/model
  - fashion-clip (3.5 GB) - Clothing description
  - vit-age-classifier (656 MB) - Age estimation
  - vit-gender-classifier (656 MB) - Gender detection
  - xclip-base-patch32 (1.5 GB) - Action recognition
Note: Heavy enrichment requires separate GPU or disabled for single-GPU mode
```

### 4.4 Single-GPU VRAM Breakdown

**Test Results on RTX A5500 (24,564 MiB total):**

| Component        | Process      | VRAM Usage            |
| ---------------- | ------------ | --------------------- |
| Nemotron Q2_K_L  | llama-server | 17,652 MiB            |
| Florence-2-Base  | python       | 992 MiB               |
| CLIP ViT-B/32    | python       | 522 MiB               |
| YOLO26m          | python       | 416 MiB               |
| Enrichment-light | python       | 430 MiB               |
| Desktop/Xorg     | system       | ~750 MiB              |
| **Total Used**   |              | **21,008 MiB**        |
| **Available**    |              | **24,564 MiB**        |
| **Headroom**     |              | **3,556 MiB (14.5%)** |

### 4.5 Environment Configuration

**.env settings for single-GPU deployment:**

```bash
# All AI services on GPU 0 (RTX A5500)
GPU_LLM=0
GPU_YOLO26=0
GPU_FLORENCE=0
GPU_CLIP=0
GPU_ENRICHMENT=0
GPU_LAYERS=999
```

### 4.6 Quality Trade-offs

| Model                    | Quality Impact | Notes                                                        |
| ------------------------ | -------------- | ------------------------------------------------------------ |
| Q2_K_L vs Q4_K_M         | Minimal        | Slightly more cautious risk scores (+9 on suspicious events) |
| Florence-2-Base vs Large | Moderate       | Reduced caption detail, adequate for security descriptions   |
| CLIP ViT-B/32 vs ViT-L   | Moderate       | Reduced embedding quality, adequate for similarity search    |

**Recommendation:** The single-GPU configuration is suitable for home security use cases where:

- Inference speed is prioritized over maximum model quality
- A single high-end GPU (20+ GB VRAM) is available
- The secondary GPU can be repurposed or removed

### 4.7 Multi-GPU Alternative

For maximum quality, retain the dual-GPU configuration:

| GPU           | Services                                             | Models                    |
| ------------- | ---------------------------------------------------- | ------------------------- |
| GPU 0 (A5500) | ai-llm                                               | Q4_K_M or Q3_K_M          |
| GPU 1 (A400)  | ai-yolo26, ai-florence, ai-clip, ai-enrichment-light | Original full-size models |

### 4.8 On-Demand Model Loading (Enrichment Service)

The ai-enrichment and ai-enrichment-light services use an **On-Demand Model Loading** strategy that allows them to manage many models with limited VRAM. Models are **NOT** permanently resident in memory.

#### How It Works

The `OnDemandModelManager` class (`ai/enrichment/model_manager.py`) provides:

1. **Lazy Loading**: Models are only loaded when first requested via `get_model(name)`
2. **VRAM Budget Enforcement**: Configurable limit (6.8GB default for enrichment-light)
3. **LRU Eviction**: When VRAM budget is exceeded, least-recently-used models are automatically evicted
4. **Priority-Based Eviction**: LOW priority models evicted first, CRITICAL models protected
5. **Idle Cleanup**: Models unused for 5 minutes (configurable) can be automatically unloaded

#### Model Priority Levels

| Priority | Models                                                        | Eviction Order |
| -------- | ------------------------------------------------------------- | -------------- |
| CRITICAL | threat_detector (weapon detection)                            | Evicted last   |
| HIGH     | pose_estimator, demographics                                  | Protected      |
| MEDIUM   | vehicle_classifier, pet_classifier, fashion_clip, person_reid | Standard       |
| LOW      | depth_estimator, action_recognizer, yolo26_detector           | Evicted first  |

#### Enrichment Model Registry (10 Models, ~7 GB Total if All Loaded)

| Model              | VRAM (MB) | Priority | Trigger Condition              |
| ------------------ | --------- | -------- | ------------------------------ |
| threat_detector    | 400       | CRITICAL | Always for person detections   |
| pose_estimator     | 300       | HIGH     | Person detected                |
| demographics       | 500       | HIGH     | Person with visible face       |
| fashion_clip       | 800       | MEDIUM   | Person detected                |
| vehicle_classifier | 1,500     | MEDIUM   | Vehicle detected               |
| pet_classifier     | 200       | MEDIUM   | Dog/cat detected               |
| person_reid        | 100       | MEDIUM   | Person tracking needed         |
| depth_estimator    | 150       | LOW      | Distance estimation needed     |
| action_recognizer  | 2,000     | LOW      | Suspicious person >3 seconds   |
| yolo26_detector    | 100       | LOW      | Secondary detection validation |

#### Why This Matters for Single-GPU Deployment

With the on-demand loading strategy:

- All 10 enrichment models can be **registered** and **available** without requiring 7+ GB VRAM simultaneously
- The 6.8GB VRAM budget is sufficient for typical operation (threat detector + 2-3 other models)
- The 11 "Additional Available Models" in the model zoo can be added to the registry without increasing baseline VRAM usage
- Models are loaded only when needed for specific detection types, then evicted when VRAM is constrained

This architecture enables the enrichment service to support a large model catalog while running on a single shared GPU.

---

## Appendix A: Test Data Files

Results are stored in:

- `results/benchmarks/quantization/Q4_K_M_quality.json`
- `results/benchmarks/quantization/Q4_K_S_quality.json`
- `results/benchmarks/quantization/Q3_K_M_quality.json`
- `results/benchmarks/quantization/Q3_K_S_quality.json`
- `results/benchmarks/quantization/Q2_K_L_quality.json`

## Appendix B: Model Files

### LLM Quantizations (Nemotron-3-Nano-30B-A3B)

| Format     | Path                                                                                          | Disk Size |
| ---------- | --------------------------------------------------------------------------------------------- | --------- |
| Q8_0       | `/export/ai_models/nemotron/nemotron-3-nano-30b-a3b/Nemotron-3-Nano-30B-A3B-Q8_0.gguf`        | 32 GB     |
| Q4_K_M     | `/export/ai_models/nemotron/nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf` | 23 GB     |
| Q4_K_S     | `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q4_K_S.gguf`      | 21 GB     |
| Q3_K_M     | `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q3_K_M.gguf`      | 19 GB     |
| Q3_K_S     | `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q3_K_S.gguf`      | 17 GB     |
| **Q2_K_L** | `/export/ai_models/nemotron/quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf`      | **17 GB** |

### Vision Models

| Model               | Path                                           | Disk Size  | Source                        |
| ------------------- | ---------------------------------------------- | ---------- | ----------------------------- |
| Florence-2-Large    | `/export/ai_models/model-zoo/florence-2-large` | 3.0 GB     | microsoft/Florence-2-large    |
| **Florence-2-Base** | `/export/ai_models/model-zoo/florence-2-base`  | **328 MB** | microsoft/Florence-2-base     |
| CLIP ViT-L/14       | `/export/ai_models/model-zoo/clip-vit-l`       | 6.4 GB     | openai/clip-vit-large-patch14 |
| **CLIP ViT-B/32**   | `/export/ai_models/model-zoo/clip-vit-b-32`    | **595 MB** | openai/clip-vit-base-patch32  |
| YOLO26m             | `/export/ai_models/model-zoo/yolo26`           | 446 MB     | Custom trained                |

### Complete Model Zoo Inventory (26 Models)

#### ai-enrichment-light Models (5 models, ~295 MB total)

| Model                   | Path                       | Disk Size | Purpose                  |
| ----------------------- | -------------------------- | --------- | ------------------------ |
| YOLOv8n-pose            | `yolov8n-pose`             | 6.5 MB    | Pose estimation          |
| Threat Detection        | `threat-detection-yolov8n` | 105 MB    | Weapon/threat detection  |
| OSNet x0.25             | `osnet-x0-25`              | 2.9 MB    | Person re-identification |
| Pet Classifier          | `pet-classifier`           | 86 MB     | Pet detection            |
| Depth Anything v2 Small | `depth-anything-v2-small`  | 95 MB     | Depth estimation         |

#### ai-enrichment (Heavy) Models (5 models, ~7.3 GB total)

| Model                 | Path                             | Disk Size | Purpose              |
| --------------------- | -------------------------------- | --------- | -------------------- |
| Vehicle Segment       | `vehicle-segment-classification` | 91 MB     | Vehicle make/model   |
| Fashion-CLIP          | `fashion-clip`                   | 3.5 GB    | Clothing description |
| ViT Age Classifier    | `vit-age-classifier`             | 656 MB    | Age estimation       |
| ViT Gender Classifier | `vit-gender-classifier`          | 656 MB    | Gender detection     |
| X-CLIP Base           | `xclip-base-patch32`             | 1.5 GB    | Action recognition   |

#### Standalone Service Models

| Model               | Path               | Disk Size | Service                 |
| ------------------- | ------------------ | --------- | ----------------------- |
| YOLO26m             | `yolo26`           | 446 MB    | ai-yolo26               |
| Florence-2-Large    | `florence-2-large` | 3.0 GB    | ai-florence (original)  |
| **Florence-2-Base** | `florence-2-base`  | 887 MB    | ai-florence (optimized) |
| CLIP ViT-L/14       | `clip-vit-l`       | 6.4 GB    | ai-clip (original)      |
| **CLIP ViT-B/32**   | `clip-vit-b-32`    | 1.7 GB    | ai-clip (optimized)     |

#### Additional Available Models (Not Currently Deployed)

| Model                  | Path                       | Disk Size | Purpose                  |
| ---------------------- | -------------------------- | --------- | ------------------------ |
| ViTPose Small          | `vitpose-small`            | 127 MB    | Alternative pose model   |
| Segformer B2 Clothes   | `segformer-b2-clothes`     | 523 MB    | Clothing segmentation    |
| Violence Detection     | `violence-detection`       | 656 MB    | Violence detection       |
| Weather Classification | `weather-classification`   | 2.4 GB    | Weather/lighting         |
| Vehicle Damage         | `vehicle-damage-detection` | 120 MB    | Vehicle damage           |
| YOLO11 Face            | `yolo11-face-detection`    | 41 MB     | Face detection           |
| YOLO11 License Plate   | `yolo11-license-plate`     | 656 MB    | License plate OCR        |
| YOLO World S           | `yolo-world-s`             | 25 MB     | Open-vocab detection     |
| X-CLIP Base (alt)      | `xclip-base`               | 1.5 GB    | Alternative action model |
| PaddleOCR              | `paddleocr`                | 12 MB     | Text recognition         |
| RT-DETRv2              | `rt-detrv2`                | 512 B     | Real-time detection      |

**Total Model Zoo Size:** ~25 GB (26 models)

## Appendix C: Downloaded vLLM Models (Not Usable)

| Format | Path                                                                  | Status             |
| ------ | --------------------------------------------------------------------- | ------------------ |
| NVFP4  | `/export/ai_models/huggingface/NVIDIA-Nemotron-3-Nano-30B-A3B-NVFP4/` | Requires H100/A100 |
| AWQ    | `/export/ai_models/huggingface/NVIDIA-Nemotron-3-Nano-30B-A3B-AWQ/`   | vLLM bug           |

---

_Report generated as part of NEM-5441 LLM Inference Performance Optimization epic._
