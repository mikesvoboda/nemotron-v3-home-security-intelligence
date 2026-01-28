#!/bin/bash
# Monitor Cosmos video generation progress with auto-sync to git
# Usage: ./monitor.sh [interval_seconds]

INTERVAL=${1:-30}
OUTPUT_DIR="/home/shadeform/cosmos-predict2.5/outputs/security_videos"
LOG_DIR="/home/shadeform/nemotron-v3-home-security-intelligence/data/synthetic/cosmos/logs"
GIT_REPO="/home/shadeform/nemotron-v3-home-security-intelligence"
VIDEO_DEST="${GIT_REPO}/data/synthetic/cosmos/videos"
TOTAL_VIDEOS=501

# Ensure destination exists
mkdir -p "${VIDEO_DEST}"

# Function to sync new videos to git
sync_to_git() {
    local new_files=()
    
    # Find videos in output that aren't in git repo yet
    for video in "${OUTPUT_DIR}"/*.mp4; do
        [ -f "$video" ] || continue
        local basename=$(basename "$video")
        if [ ! -f "${VIDEO_DEST}/${basename}" ]; then
            new_files+=("$basename")
        fi
    done
    
    if [ ${#new_files[@]} -eq 0 ]; then
        echo "   No new videos to sync"
        return 0
    fi
    
    echo "   Found ${#new_files[@]} new video(s) to sync..."
    
    # Copy new files
    local copied=0
    for fname in "${new_files[@]}"; do
        cp "${OUTPUT_DIR}/${fname}" "${VIDEO_DEST}/${fname}" 2>/dev/null && ((copied++))
        echo "   ✓ Copied ${fname}"
    done
    
    if [ $copied -eq 0 ]; then
        echo "   No files copied"
        return 1
    fi
    
    # Git add, commit, push
    cd "${GIT_REPO}" || return 1
    
    git add data/synthetic/cosmos/videos/*.mp4 2>/dev/null
    
    if git diff --cached --quiet; then
        echo "   No changes to commit"
        return 0
    fi
    
    local commit_msg="Add ${copied} synthetic video(s): ${new_files[*]}"
    
    echo "   Committing ${copied} video(s)..."
    if git commit --no-verify -m "${commit_msg}" >/dev/null 2>&1; then
        echo "   ✓ Committed"
        
        echo "   Pushing to origin..."
        if git push --no-verify >/dev/null 2>&1; then
            echo "   ✓ Pushed to origin"
            LAST_SYNC=$(date '+%H:%M:%S')
            LAST_SYNC_COUNT=$copied
            return 0
        else
            echo "   ✗ Push failed"
            return 1
        fi
    else
        echo "   ✗ Commit failed"
        return 1
    fi
}

# Track sync status
LAST_SYNC="Never"
LAST_SYNC_COUNT=0
TOTAL_SYNCED=0

clear
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║     Cosmos Video Generation Monitor (Auto-Sync Enabled)         ║"
echo "║     Press Ctrl+C to exit                                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

while true; do
    # Get timestamp
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Count generated videos
    VIDEO_COUNT=$(ls "${OUTPUT_DIR}"/*.mp4 2>/dev/null | wc -l)
    
    # Count synced videos
    SYNCED_COUNT=$(ls "${VIDEO_DEST}"/*.mp4 2>/dev/null | wc -l)
    
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
    echo "║     Cosmos Video Generation Monitor (Auto-Sync Enabled)         ║"
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "📅 Time: ${TIMESTAMP}"
    echo "🐳 Containers Running: ${CONTAINER_COUNT}/8"
    echo ""
    echo "═══════════════════════════════════════════════════════════════════"
    echo "📊 PROGRESS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    printf "   Generated: %d / %d (%d%%)\n" "$VIDEO_COUNT" "$TOTAL_VIDEOS" "$PERCENT"
    printf "   Synced to Git: %d / %d\n" "$SYNCED_COUNT" "$VIDEO_COUNT"
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
    echo "🎬 GPU GENERATION STATUS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    printf "   %-6s %-12s %-10s %-20s\n" "GPU" "Video#" "Progress" "Current Video"
    printf "   %-6s %-12s %-10s %-20s\n" "---" "------" "--------" "-------------"
    
    for gpu in 0 1 2 3 4 5 6 7; do
        log_file="${LOG_DIR}/gpu${gpu}.log"
        if [ -f "$log_file" ]; then
            # Get current video being processed
            current_video=$(grep "Processing sample" "$log_file" 2>/dev/null | tail -1 | sed -E 's/.*Processing sample ([^ ]+).*/\1/')
            
            # Get video number (e.g., [5/63])
            video_num=$(grep "Processing sample" "$log_file" 2>/dev/null | tail -1 | sed -E 's/.*\[([0-9]+\/[0-9]+)\].*/\1/')
            
            # Get generation progress percentage from the last "Generating samples" line
            progress=$(grep "Generating samples:" "$log_file" 2>/dev/null | tail -1 | sed -E 's/.*Generating samples:[[:space:]]*([0-9]+)%.*/\1/')
            
            # Check if video just completed (look for SUCCESS)
            last_success=$(grep "SUCCESS" "$log_file" 2>/dev/null | tail -1 | sed -E 's/.*SUCCESS.*saved to.*\/([^\/]+\.mp4).*/\1/')
            
            if [ -z "$current_video" ]; then
                printf "   %-6s %-12s %-10s %-20s\n" "GPU $gpu" "-" "-" "Starting..."
            elif [ -n "$progress" ] && [ "$progress" -lt 100 ] 2>/dev/null; then
                # Build progress bar (10 chars)
                filled=$((progress / 10))
                empty=$((10 - filled))
                bar=$(printf "%${filled}s" | tr ' ' '█')$(printf "%${empty}s" | tr ' ' '░')
                printf "   %-6s %-12s [%s] %3d%%  %s\n" "GPU $gpu" "$video_num" "$bar" "$progress" "$current_video"
            else
                printf "   %-6s %-12s %-10s %-20s\n" "GPU $gpu" "$video_num" "[██████████]" "$current_video"
            fi
        else
            printf "   %-6s %-12s %-10s %-20s\n" "GPU $gpu" "-" "-" "No log yet"
        fi
    done
    echo ""
    
    echo "═══════════════════════════════════════════════════════════════════"
    echo "📁 RECENT VIDEOS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    
    # List recent videos
    if [ "$VIDEO_COUNT" -gt 0 ]; then
        ls -lt "${OUTPUT_DIR}"/*.mp4 2>/dev/null | head -5 | while read -r line; do
            fname=$(echo "$line" | awk '{print $NF}')
            fsize=$(echo "$line" | awk '{print $5}')
            ftime=$(echo "$line" | awk '{print $6, $7, $8}')
            echo "   $(basename "$fname") - ${fsize} bytes - ${ftime}"
        done
        if [ "$VIDEO_COUNT" -gt 5 ]; then
            echo "   ... and $((VIDEO_COUNT - 5)) more"
        fi
    else
        echo "   No videos generated yet"
    fi
    echo ""
    
    echo "═══════════════════════════════════════════════════════════════════"
    echo "🔄 GIT SYNC STATUS"
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""
    printf "   Last sync: %s\n" "$LAST_SYNC"
    printf "   Videos in git: %d\n" "$SYNCED_COUNT"
    echo ""
    
    # Sync new videos to git
    sync_to_git
    
    # Update synced count after sync
    SYNCED_COUNT=$(ls "${VIDEO_DEST}"/*.mp4 2>/dev/null | wc -l)
    
    echo ""
    echo "───────────────────────────────────────────────────────────────────"
    echo "   Refreshing in ${INTERVAL}s... (Ctrl+C to exit)"
    echo "───────────────────────────────────────────────────────────────────"
    
    sleep "$INTERVAL"
done
