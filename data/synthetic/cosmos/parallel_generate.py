#!/usr/bin/env python3
"""
Parallel video generation using 8 GPUs.

Each GPU runs an independent Cosmos inference process.
Progress is tracked in generation_status.json.
"""

import json
import subprocess
import time
import os
import signal
import sys
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

BASE_DIR = Path(__file__).parent
COSMOS_DIR = Path("/home/shadeform/cosmos-predict2.5")
OUTPUT_DIR = COSMOS_DIR / "outputs" / "security_videos"
QUEUE_FILE = BASE_DIR / "prompts" / "generated" / "generation_queue.json"
STATUS_FILE = BASE_DIR / "generation_status.json"

# Number of GPUs to use
NUM_GPUS = 8

# Lock for thread-safe status updates
status_lock = Lock()


def load_queue():
    """Load the generation queue."""
    with open(QUEUE_FILE) as f:
        return json.load(f)


def load_status():
    """Load current generation status."""
    with open(STATUS_FILE) as f:
        return json.load(f)


def save_status(status):
    """Save generation status."""
    with status_lock:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f, indent=2)


def update_video_status(video_id: str, state: str, details: dict = None):
    """Update status for a specific video."""
    status = load_status()
    
    if "videos" not in status:
        status["videos"] = {}
    
    status["videos"][video_id] = {
        "state": state,
        "updated_at": datetime.now().isoformat(),
        **(details or {})
    }
    
    # Update counters
    if state == "completed":
        status["completed"] = status.get("completed", 0) + 1
    elif state == "failed":
        status["failed"] = status.get("failed", 0) + 1
    
    status["last_updated"] = datetime.now().isoformat()
    save_status(status)


def generate_video(video_info: dict, gpu_id: int) -> dict:
    """Generate a single video using Docker on specified GPU."""
    video_id = video_info["id"]
    prompt_path = video_info["path"]
    duration = video_info.get("duration_seconds", 15)
    
    # Determine number of clips needed (Cosmos generates ~5s per clip)
    # For now, generate single 5s clips - concatenation would be a separate step
    
    print(f"[GPU {gpu_id}] Starting {video_id} ({duration}s)...")
    update_video_status(video_id, "in_progress", {"gpu": gpu_id, "started_at": datetime.now().isoformat()})
    
    # Create output directory for this video
    video_output_dir = OUTPUT_DIR / video_id
    video_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Docker command with specific GPU
    cmd_str = f"""docker run --rm \
        --gpus 'device={gpu_id}' \
        --ipc=host \
        --ulimit memlock=-1 \
        --ulimit stack=67108864 \
        -v {COSMOS_DIR}:/workspace \
        -v /home/shadeform/.cache/huggingface:/root/.cache/huggingface \
        -v {BASE_DIR}/prompts/generated:/prompts \
        -w /workspace \
        cosmos-b300 \
        python examples/inference.py \
        -i /prompts/{video_id}.json \
        -o /workspace/outputs/security_videos/{video_id} \
        --inference-type=text2world \
        --model=14B/post-trained"""
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd_str,
            shell=True,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout per video
        )
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            # Check if video was created
            video_file = video_output_dir / f"{video_id}.mp4"
            if video_file.exists():
                print(f"[GPU {gpu_id}] ✓ Completed {video_id} in {elapsed/60:.1f} min")
                update_video_status(video_id, "completed", {
                    "gpu": gpu_id,
                    "elapsed_seconds": elapsed,
                    "output_path": str(video_file)
                })
                return {"id": video_id, "status": "completed", "elapsed": elapsed}
            else:
                print(f"[GPU {gpu_id}] ✗ {video_id} - no output file")
                update_video_status(video_id, "failed", {
                    "gpu": gpu_id,
                    "error": "No output file generated",
                    "stdout": result.stdout[-1000:] if result.stdout else "",
                    "stderr": result.stderr[-1000:] if result.stderr else ""
                })
                return {"id": video_id, "status": "failed", "error": "No output file"}
        else:
            print(f"[GPU {gpu_id}] ✗ {video_id} - exit code {result.returncode}")
            update_video_status(video_id, "failed", {
                "gpu": gpu_id,
                "exit_code": result.returncode,
                "stderr": result.stderr[-1000:] if result.stderr else ""
            })
            return {"id": video_id, "status": "failed", "error": result.stderr[-500:]}
            
    except subprocess.TimeoutExpired:
        print(f"[GPU {gpu_id}] ✗ {video_id} - timeout")
        update_video_status(video_id, "failed", {"gpu": gpu_id, "error": "Timeout"})
        return {"id": video_id, "status": "failed", "error": "Timeout"}
    except Exception as e:
        print(f"[GPU {gpu_id}] ✗ {video_id} - error: {e}")
        update_video_status(video_id, "failed", {"gpu": gpu_id, "error": str(e)})
        return {"id": video_id, "status": "failed", "error": str(e)}


def get_pending_videos(queue: dict, status: dict) -> list:
    """Get list of videos that haven't been completed yet."""
    completed = set()
    for vid_id, vid_status in status.get("videos", {}).items():
        if vid_status.get("state") == "completed":
            completed.add(vid_id)
    
    pending = []
    for video in queue["files"]:
        if video["id"] not in completed:
            pending.append(video)
    
    return pending


def run_parallel_generation(max_videos: int = None, start_from: int = 0):
    """Run parallel generation across all GPUs."""
    
    # Load queue and status
    queue = load_queue()
    status = load_status()
    
    # Get pending videos
    pending = get_pending_videos(queue, status)
    
    if start_from > 0:
        pending = pending[start_from:]
    
    if max_videos:
        pending = pending[:max_videos]
    
    if not pending:
        print("No pending videos to generate!")
        return
    
    print(f"Starting parallel generation of {len(pending)} videos across {NUM_GPUS} GPUs")
    print(f"Output directory: {OUTPUT_DIR}")
    print("-" * 60)
    
    # Update status
    status["started_at"] = status.get("started_at") or datetime.now().isoformat()
    status["in_progress"] = len(pending)
    save_status(status)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track GPU assignments
    gpu_queue = list(range(NUM_GPUS))
    results = []
    
    # Process videos in parallel using thread pool
    with ThreadPoolExecutor(max_workers=NUM_GPUS) as executor:
        # Submit initial batch
        futures = {}
        video_idx = 0
        
        # Start with one video per GPU
        for gpu_id in range(min(NUM_GPUS, len(pending))):
            video = pending[video_idx]
            future = executor.submit(generate_video, video, gpu_id)
            futures[future] = (video, gpu_id)
            video_idx += 1
        
        # Process completions and submit new work
        while futures:
            # Wait for next completion
            done_futures = []
            for future in as_completed(futures, timeout=None):
                done_futures.append(future)
                break  # Process one at a time
            
            for future in done_futures:
                video, gpu_id = futures.pop(future)
                result = future.result()
                results.append(result)
                
                # Submit next video if available
                if video_idx < len(pending):
                    next_video = pending[video_idx]
                    new_future = executor.submit(generate_video, next_video, gpu_id)
                    futures[new_future] = (next_video, gpu_id)
                    video_idx += 1
    
    # Final summary
    completed = sum(1 for r in results if r["status"] == "completed")
    failed = sum(1 for r in results if r["status"] == "failed")
    
    print("\n" + "=" * 60)
    print(f"Generation complete!")
    print(f"  Completed: {completed}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(results)}")
    
    # Update final status
    status = load_status()
    status["in_progress"] = 0
    save_status(status)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parallel video generation")
    parser.add_argument("--max", type=int, help="Maximum videos to generate")
    parser.add_argument("--start", type=int, default=0, help="Start from video index")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    args = parser.parse_args()
    
    if args.dry_run:
        queue = load_queue()
        status = load_status()
        pending = get_pending_videos(queue, status)
        print(f"Would generate {len(pending)} videos:")
        for v in pending[:20]:
            print(f"  {v['id']}: {v.get('category')}/{v.get('subcategory')}")
        if len(pending) > 20:
            print(f"  ... and {len(pending) - 20} more")
        return
    
    run_parallel_generation(max_videos=args.max, start_from=args.start)


if __name__ == "__main__":
    main()
