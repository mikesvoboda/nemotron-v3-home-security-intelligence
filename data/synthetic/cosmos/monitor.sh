#!/bin/bash
# Monitor Cosmos video generation progress
# Usage: ./monitor.sh [interval_seconds]

INTERVAL=${1:-30}
OUTPUT_DIR="/home/shadeform/cosmos-predict2.5/outputs/security_videos"
LOG_DIR="/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/logs"
TOTAL_VIDEOS=88

clear
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           Cosmos Video Generation Monitor                        ║"
echo "║           Press Ctrl+C to exit                                   ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

while true; do
    # Get timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Count generated videos
    VIDEO_COUNT=$(ls "${OUTPUT_DIR}"/*.mp4 2>/dev/null | wc -l)
    
    # Count running containers
    CONTAINER_COUNT=$(docker ps -q 2>/dev/null | wc -l)
    
    # Get GPU stats
    GPU_STATS=$(nvidia-smi --query-gpu=index,utilization.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null)
    
    # Calculate progress
    PERCENT=$((VIDEO_COUNT * 100 / TOTAL_VIDEOS))
    REMAINING=$((TOTAL_VIDEOS - VIDEO_COUNT))
    
    # Clear screen and print status
    clear
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║           Cosmos Video Generation Monitor                        ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📅 Time: ${TIMESTAMP}"
    echo "🐳 Containers Running: ${CONTAINER_COUNT}/8"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "📊 PROGRESS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    printf "   Videos: %d / %d (%d%%)\n" "$VIDEO_COUNT" "$TOTAL_VIDEOS" "$PERCENT"
    printf "   Remaining: %d\n" "$REMAINING"
    echo ""
    
    # Progress bar
    BAR_WIDTH=50
    FILLED=$((PERCENT * BAR_WIDTH / 100))
    EMPTY=$((BAR_WIDTH - FILLED))
    printf "   ["
    printf "%${FILLED}s" | tr ' ' '█'
    printf "%${EMPTY}s" | tr ' ' '░'
    printf "] %d%%\n" "$PERCENT"
    echo ""
    
    echo "═══════════════════════════════════════════════════════════════════"
    echo "🖥️  GPU STATUS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    printf "   %-6s %-12s %-15s\n" "GPU" "Utilization" "Memory"
    printf "   %-6s %-12s %-15s\n" "---" "-----------" "------"
    
    if [ -n "$GPU_STATS" ]; then
        echo "$GPU_STATS" | while IFS=', ' read -r idx util mem; do
            printf "   %-6s %-12s %-15s\n" "GPU $idx" "${util}%" "${mem} MiB"
        done
    else
        echo "   Unable to get GPU stats"
    fi
    echo ""
    
    echo "═══════════════════════════════════════════════════════════════════"
    echo "📝 RECENT LOG ACTIVITY (GPU 0)"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    
    # Show recent progress from GPU 0 log
    if [ -f "${LOG_DIR}/gpu0.log" ]; then
        grep -E "Processing sample|Generating samples:|SUCCESS|video with" "${LOG_DIR}/gpu0.log" 2>/dev/null | tail -5 | while read -r line; do
            echo "   $line"
        done
    else
        echo "   No log file yet"
    fi
    echo ""
    
    echo "═══════════════════════════════════════════════════════════════════"
    echo "📁 GENERATED VIDEOS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    
    # List recent videos
    if [ "$VIDEO_COUNT" -gt 0 ]; then
        ls -lt "${OUTPUT_DIR}"/*.mp4 2>/dev/null | head -5 | while read -r line; do
            fname=$(echo "$line" | awk '{print $NF}')
            fsize=$(echo "$line" | awk '{print $5}')
            ftime=$(echo "$line" | awk '{print $6, $7, $8}')
            echo "   $(basename $fname) - ${fsize} bytes - ${ftime}"
        done
        if [ "$VIDEO_COUNT" -gt 5 ]; then
            echo "   ... and $((VIDEO_COUNT - 5)) more"
        fi
    else
        echo "   No videos generated yet"
    fi
    echo ""
    
    echo "───────────────────────────────────────────────────────────────────"
    echo "   Refreshing in ${INTERVAL}s... (Ctrl+C to exit)"
    echo "───────────────────────────────────────────────────────────────────"
    
    sleep "$INTERVAL"
done
