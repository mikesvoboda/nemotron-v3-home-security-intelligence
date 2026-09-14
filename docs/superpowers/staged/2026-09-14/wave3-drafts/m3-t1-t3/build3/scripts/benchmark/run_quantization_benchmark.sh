#!/bin/bash
# Quantization Quality Benchmark for Nemotron-3-Nano-30B
# Tests different GGUF quantization levels for quality vs VRAM tradeoff
#
# Usage: ./scripts/benchmark/run_quantization_benchmark.sh [formats...]
# Example: ./scripts/benchmark/run_quantization_benchmark.sh Q4_K_M Q3_K_M Q2_K_L

set -e

# Configuration
MODEL_BASE="/export/ai_models/nemotron"
RESULTS_DIR="results/benchmarks/quantization"
LLM_PORT=8091
GPU_ID=0
TIMEOUT=300

# Model paths for each quantization format
declare -A MODEL_PATHS=(
    ["Q8_0"]="nemotron-3-nano-30b-a3b/Nemotron-3-Nano-30B-A3B-Q8_0.gguf"
    ["Q4_K_M"]="nemotron-3-nano-30b-a3b-q4km/Nemotron-3-Nano-30B-A3B-Q4_K_M.gguf"
    ["Q4_K_S"]="quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q4_K_S.gguf"
    ["Q3_K_M"]="quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q3_K_M.gguf"
    ["Q3_K_S"]="quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q3_K_S.gguf"
    ["Q2_K_L"]="quantization-benchmarks/Nemotron-3-Nano-30B-A3B-Q2_K_L.gguf"
)

# GPU layers for each format (adjusted for 24GB VRAM)
declare -A GPU_LAYERS=(
    ["Q8_0"]="35"     # Partial offload - model too large
    ["Q4_K_M"]="45"   # Full GPU
    ["Q4_K_S"]="45"   # Full GPU
    ["Q3_K_M"]="45"   # Full GPU
    ["Q3_K_S"]="45"   # Full GPU
    ["Q2_K_L"]="45"   # Full GPU
)

# Test prompts for quality evaluation
TEST_PROMPTS=(
    "Analyze this security event: A person is standing at the front door during daytime. They appear to be holding a package. Provide a risk assessment with score 0-100."
    "Analyze this security event: A vehicle has been parked in the driveway for 30 minutes at night. The headlights are off. Provide a risk assessment with score 0-100."
    "Analyze this security event: Motion detected in the backyard near the fence. No person visible. Time is 2:30 AM. Provide a risk assessment with score 0-100."
    "Analyze this security event: Two people approaching the front door together. One is carrying a clipboard. Daytime. Provide a risk assessment with score 0-100."
    "Analyze this security event: A dog is visible in the front yard. No other activity. Provide a risk assessment with score 0-100."
)

# Expected behaviors (for quality scoring)
# Format: "keyword1,keyword2,expected_risk_range"
EXPECTED_BEHAVIORS=(
    "package,delivery,low,0-30"
    "vehicle,night,parked,medium,30-60"
    "motion,night,backyard,high,50-80"
    "people,door,clipboard,low,10-40"
    "dog,animal,low,0-20"
)

mkdir -p "$RESULTS_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

get_vram_usage() {
    nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i $GPU_ID 2>/dev/null | head -1
}

wait_for_server() {
    local max_wait=$1
    local waited=0
    log "Waiting for llama.cpp server to be ready..."
    while [ $waited -lt $max_wait ]; do
        if curl -s "http://127.0.0.1:${LLM_PORT}/v1/models" > /dev/null 2>&1; then
            log "Server ready after ${waited}s"
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
    done
    log "ERROR: Server did not become ready within ${max_wait}s"
    return 1
}

stop_llm_container() {
    log "Stopping any existing LLM containers..."
    podman stop ai-llm 2>/dev/null || true
    podman rm ai-llm 2>/dev/null || true
    # Also stop any compose-managed containers
    podman ps -a --format "{{.Names}}" | grep -E "ai-llm|llama" | xargs -r podman rm -f 2>/dev/null || true
    sleep 2
}

start_llm_container() {
    local model_path=$1
    local gpu_layers=$2

    log "Starting llama.cpp with model: $model_path"
    log "GPU layers: $gpu_layers (999 = all layers on GPU)"

    # Use --privileged for proper GPU access
    # Use 999 layers to load entire model on GPU
    # Use CUDA_VISIBLE_DEVICES to target only GPU 0
    podman run -d \
        --name ai-llm \
        --privileged \
        --device nvidia.com/gpu=$GPU_ID \
        -e CUDA_VISIBLE_DEVICES=$GPU_ID \
        -v "${MODEL_BASE}:/models:ro" \
        -p "${LLM_PORT}:8091" \
        localhost/ai-llm:latest \
        sh -c "llama-server --model /models/${model_path} --host 0.0.0.0 --port 8091 --n-gpu-layers 999 --ctx-size 4096"
}

send_prompt() {
    local prompt=$1
    curl -s "http://127.0.0.1:${LLM_PORT}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"nemotron\",
            \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}],
            \"max_tokens\": 512,
            \"temperature\": 0.1
        }" 2>/dev/null
}

extract_risk_score() {
    local response=$1
    # Extract risk score from response (looks for patterns like "risk: 45" or "score: 45" or just "45/100")
    echo "$response" | grep -oE '(risk|score)[^0-9]*([0-9]+)' | grep -oE '[0-9]+' | head -1
}

check_keywords() {
    local response=$1
    local keywords=$2
    local found=0
    local total=0

    IFS=',' read -ra KEYWORDS <<< "$keywords"
    for kw in "${KEYWORDS[@]}"; do
        total=$((total + 1))
        if echo "$response" | grep -iq "$kw"; then
            found=$((found + 1))
        fi
    done

    echo "$found/$total"
}

benchmark_format() {
    local format=$1
    local model_path="${MODEL_PATHS[$format]}"
    local gpu_layers="${GPU_LAYERS[$format]}"
    local result_file="${RESULTS_DIR}/${format}_results.json"

    if [ -z "$model_path" ]; then
        log "ERROR: Unknown format: $format"
        return 1
    fi

    if [ ! -f "${MODEL_BASE}/${model_path}" ]; then
        log "ERROR: Model file not found: ${MODEL_BASE}/${model_path}"
        return 1
    fi

    log "=========================================="
    log "Benchmarking: $format"
    log "=========================================="

    # Stop any existing container
    stop_llm_container

    # Start with new model
    start_llm_container "$model_path" "$gpu_layers"

    # Wait for server
    if ! wait_for_server $TIMEOUT; then
        log "ERROR: Failed to start server for $format"
        podman logs ai-llm 2>&1 | tail -50
        return 1
    fi

    # Measure VRAM after model is loaded
    sleep 5  # Let VRAM stabilize
    local vram_mb=$(get_vram_usage)
    log "VRAM usage: ${vram_mb} MB"

    # Run quality tests
    local total_score=0
    local test_count=0
    local coherent_count=0
    local json_valid_count=0

    log "Running quality tests..."

    for i in "${!TEST_PROMPTS[@]}"; do
        local prompt="${TEST_PROMPTS[$i]}"
        log "  Test $((i+1))/${#TEST_PROMPTS[@]}..."

        local start_time=$(date +%s%N)
        local response=$(send_prompt "$prompt")
        local end_time=$(date +%s%N)
        local latency_ms=$(( (end_time - start_time) / 1000000 ))

        # Extract the actual content
        local content=$(echo "$response" | jq -r '.choices[0].message.content // empty' 2>/dev/null)

        if [ -n "$content" ]; then
            test_count=$((test_count + 1))

            # Check for coherent response (not gibberish)
            local word_count=$(echo "$content" | wc -w)
            if [ "$word_count" -gt 10 ]; then
                coherent_count=$((coherent_count + 1))
            fi

            # Check for JSON-like structure or proper formatting
            if echo "$content" | grep -qE '(risk|score|assessment|level)'; then
                json_valid_count=$((json_valid_count + 1))
            fi

            # Extract and validate risk score
            local risk_score=$(extract_risk_score "$content")
            if [ -n "$risk_score" ] && [ "$risk_score" -ge 0 ] && [ "$risk_score" -le 100 ]; then
                total_score=$((total_score + 1))
            fi

            log "    Latency: ${latency_ms}ms, Words: ${word_count}, Risk: ${risk_score:-N/A}"
        else
            log "    ERROR: Empty or invalid response"
        fi
    done

    # Calculate quality metrics using awk for floating point
    local coherence_rate=0
    local format_rate=0
    local score_rate=0

    if [ "$test_count" -gt 0 ]; then
        coherence_rate=$(awk "BEGIN {printf \"%.1f\", $coherent_count * 100 / $test_count}")
        format_rate=$(awk "BEGIN {printf \"%.1f\", $json_valid_count * 100 / $test_count}")
        score_rate=$(awk "BEGIN {printf \"%.1f\", $total_score * 100 / $test_count}")
    fi

    # Overall quality score (weighted average)
    local quality_score=$(awk "BEGIN {printf \"%.1f\", ($coherence_rate * 0.4 + $format_rate * 0.3 + $score_rate * 0.3)}")

    log ""
    log "Results for $format:"
    log "  VRAM: ${vram_mb} MB"
    log "  Coherence: ${coherence_rate}%"
    log "  Format compliance: ${format_rate}%"
    log "  Valid risk scores: ${score_rate}%"
    log "  Overall quality: ${quality_score}%"

    # Save results
    cat > "$result_file" << EOF
{
    "format": "$format",
    "model_path": "$model_path",
    "gpu_layers": $gpu_layers,
    "vram_mb": $vram_mb,
    "tests_run": $test_count,
    "coherent_responses": $coherent_count,
    "format_compliant": $json_valid_count,
    "valid_risk_scores": $total_score,
    "coherence_rate": $coherence_rate,
    "format_rate": $format_rate,
    "score_rate": $score_rate,
    "quality_score": $quality_score,
    "timestamp": "$(date -Iseconds)"
}
EOF

    log "Results saved to: $result_file"

    # Stop container for next test
    stop_llm_container

    return 0
}

generate_summary() {
    local summary_file="${RESULTS_DIR}/summary_$(date +%Y%m%d_%H%M%S).md"

    log "Generating summary report..."

    cat > "$summary_file" << 'EOF'
# Quantization Comparison Summary

## Results

| Format | VRAM (GB) | Quality Score | Coherence | Format | Risk Scores |
|--------|-----------|---------------|-----------|--------|-------------|
EOF

    for result_file in "${RESULTS_DIR}"/*_results.json; do
        if [ -f "$result_file" ]; then
            local format=$(jq -r '.format' "$result_file")
            local vram=$(jq -r '.vram_mb' "$result_file")
            local vram_gb=$(awk "BEGIN {printf \"%.1f\", $vram / 1024}")
            local quality=$(jq -r '.quality_score' "$result_file")
            local coherence=$(jq -r '.coherence_rate' "$result_file")
            local fmt_rate=$(jq -r '.format_rate' "$result_file")
            local score_rate=$(jq -r '.score_rate' "$result_file")

            echo "| $format | ${vram_gb} | ${quality}% | ${coherence}% | ${fmt_rate}% | ${score_rate}% |" >> "$summary_file"
        fi
    done

    cat >> "$summary_file" << 'EOF'

## Recommendations

Based on quality scores and VRAM usage:

- **Best Quality**: Q8_0 or Q4_K_M (if VRAM allows)
- **Best Balance**: Q4_K_S or Q3_K_M (good quality, moderate VRAM)
- **Minimum VRAM**: Q3_K_S or Q2_K_L (may have quality degradation)

## Notes

- Quality score is weighted: 40% coherence, 30% format compliance, 30% valid risk scores
- Tests run with temperature=0.1 for reproducibility
- VRAM measured after model fully loaded
EOF

    log "Summary saved to: $summary_file"
    cat "$summary_file"
}

# Main execution
log "Quantization Quality Benchmark"
log "=============================="

# Default formats to test (skip Q8_0 by default as it needs CPU offloading)
FORMATS_TO_TEST=("${@:-Q4_K_M Q4_K_S Q3_K_M Q3_K_S Q2_K_L}")

if [ ${#FORMATS_TO_TEST[@]} -eq 0 ] || [ "${FORMATS_TO_TEST[0]}" == "" ]; then
    FORMATS_TO_TEST=(Q4_K_M Q4_K_S Q3_K_M Q3_K_S Q2_K_L)
fi

log "Formats to test: ${FORMATS_TO_TEST[*]}"

for format in ${FORMATS_TO_TEST[@]}; do
    if ! benchmark_format "$format"; then
        log "WARNING: Failed to benchmark $format, continuing..."
    fi
done

generate_summary

log ""
log "Benchmark complete!"
