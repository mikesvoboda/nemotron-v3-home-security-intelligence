#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "httpx",
# ]
# ///
"""
Nano Mascot Video Generation Script.

Generates 8-second videos featuring Nano using Veo 3.1's image-to-video capability.
Uses the mascot image as a reference to maintain visual consistency.

Usage:
    # List all videos
    uv run scripts/generate_nano_videos.py list

    # Generate a single video
    uv run scripts/generate_nano_videos.py generate --id 01-morning-standup

    # Generate all videos in a category
    uv run scripts/generate_nano_videos.py generate --category team-hype

    # Generate all videos
    uv run scripts/generate_nano_videos.py generate --all

    # Generate in parallel (5 at a time)
    uv run scripts/generate_nano_videos.py generate --all --parallel 5

    # Preview prompt for a video
    uv run scripts/generate_nano_videos.py preview --id 01-morning-standup

Requires NVIDIA_API_KEY or NVAPIKEY environment variable.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # docs/media -> docs -> project root
SPECS_PATH = SCRIPT_DIR / "veo3-video-specs.json"  # Spec file in same directory as script
OUTPUT_ROOT = PROJECT_ROOT
MASCOT_IMAGE = SCRIPT_DIR / "nemotron-mascot.jpg"
NVIDIA_LOGO = SCRIPT_DIR / "nvidia-logo.jpeg"

# API Configuration
API_BASE_URL = "https://inference-api.nvidia.com"
VIDEO_MODEL = "gcp/google/veo-3.1-generate-001"

# Rate limiting
DELAY_BETWEEN_REQUESTS = 5  # seconds


def get_api_key() -> str:
    """Get NVIDIA API key from environment."""
    key = os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVAPIKEY")
    if not key:
        print("Error: NVIDIA_API_KEY or NVAPIKEY environment variable required", file=sys.stderr)
        sys.exit(1)
    return key


def load_specs() -> dict[str, Any]:
    """Load video specifications."""
    if not SPECS_PATH.exists():
        print(f"Error: Specs file not found at {SPECS_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(SPECS_PATH) as f:
        return json.load(f)


def load_mascot_image_base64() -> str:
    """Load and encode the mascot image as base64."""
    if not MASCOT_IMAGE.exists():
        print(f"Error: Mascot image not found at {MASCOT_IMAGE}", file=sys.stderr)
        sys.exit(1)
    with open(MASCOT_IMAGE, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def load_nvidia_logo_base64() -> str | None:
    """Load and encode the NVIDIA logo as base64 if it exists."""
    if not NVIDIA_LOGO.exists():
        return None
    with open(NVIDIA_LOGO, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def load_reference_image_base64(path: str) -> str:
    """Load and encode any reference image as base64."""
    image_path = Path(path)
    if not image_path.exists():
        print(f"Error: Reference image not found at {image_path}", file=sys.stderr)
        sys.exit(1)
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_all_videos(specs: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """Get all videos as (category_name, output_dir, video_spec) tuples."""
    videos = []
    for cat_name, cat_data in specs["categories"].items():
        output_dir = cat_data["output_dir"]
        for video in cat_data["videos"]:
            videos.append((cat_name, output_dir, video))
    return videos


def find_video_by_id(specs: dict[str, Any], video_id: str) -> tuple[str, str, dict[str, Any]] | None:
    """Find a video by its ID."""
    for cat_name, output_dir, video in get_all_videos(specs):
        if video["id"] == video_id:
            return (cat_name, output_dir, video)
    return None


def generate_video_with_reference(
    prompt: str,
    output_path: Path,
    reference_image_b64: str,
    logo_image_b64: str | None = None,
    duration: int = 8,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
) -> bool:
    """
    Generate a video using Veo with reference images.

    Args:
        prompt: Text prompt describing the video.
        output_path: Where to save the generated video.
        reference_image_b64: Base64-encoded mascot reference image.
        logo_image_b64: Base64-encoded logo reference image (optional).
        duration: Video duration in seconds.
        resolution: Video resolution.
        aspect_ratio: Aspect ratio.

    Returns:
        True if successful, False otherwise.
    """
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Build reference images list (mascot only - logo didn't work for chest placement)
    reference_images = [
        {
            "image": {
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": reference_image_b64
                }
            },
            "referenceType": "asset"
        }
    ]

    # Build request with reference images (using working /v1/videos endpoint)
    request_json = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "referenceImages": reference_images,
        "duration_seconds": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
    }

    print("    Submitting to API...", end=" ", flush=True)
    with httpx.Client(timeout=300.0) as client:
        try:
            response = client.post(
                f"{API_BASE_URL}/v1/videos",
                json=request_json,
                headers=headers,
            )

            if response.status_code in (200, 202):
                print("accepted")
                result = response.json()

                # Check for direct video data
                video_data = extract_video_data(result)
                if video_data:
                    return save_video(video_data, output_path)

                # Check for async job ID
                job_id = extract_job_id(result)
                if job_id:
                    print(f"    Job ID: {job_id}")
                    return poll_and_download(job_id, output_path, headers)

                print(f"    Unexpected response: {result}")
            else:
                print(f"failed ({response.status_code})")
                if response.status_code == 401:
                    print("    Authentication failed - check your API key")
                elif response.status_code == 404:
                    print("    Endpoint not found")
                else:
                    print(f"    Response: {response.text[:500]}")
                return False

        except httpx.RequestError as e:
            print(f"error: {e}")

    return False


def extract_video_data(response: dict[str, Any]) -> bytes | None:
    """Extract video data from API response."""
    # Direct base64 video
    if "video" in response:
        data = response["video"]
        if isinstance(data, str):
            if data.startswith("data:video"):
                _, b64 = data.split(",", 1)
                return base64.b64decode(b64)
            return base64.b64decode(data)

    # Nested in data array
    if "data" in response and isinstance(response["data"], list):
        for item in response["data"]:
            if "video" in item:
                return base64.b64decode(item["video"])
            if "b64_json" in item:
                return base64.b64decode(item["b64_json"])

    return None


def extract_job_id(response: dict[str, Any]) -> str | None:
    """Extract job ID from API response."""
    for field in ["id", "video_id", "job_id", "generation_id", "name", "requestId"]:
        if field in response:
            return str(response[field])
    if "data" in response and isinstance(response["data"], dict):
        return extract_job_id(response["data"])
    return None


def poll_and_download(job_id: str, output_path: Path, headers: dict[str, str]) -> bool:
    """Poll for job completion and download the video."""
    poll_interval = 10
    max_polls = 60  # 10 minutes max

    status_endpoints = [
        f"{API_BASE_URL}/v1/video/status/{job_id}",
        f"{API_BASE_URL}/v1/videos/{job_id}",
        f"{API_BASE_URL}/v1/video/generations/{job_id}",
        f"{API_BASE_URL}/v1/jobs/{job_id}",
    ]

    with httpx.Client(timeout=30.0) as client:
        for poll_num in range(max_polls):
            print(f"    Polling ({poll_num + 1}/{max_polls})...", end=" ", flush=True)

            for endpoint in status_endpoints:
                try:
                    response = client.get(endpoint, headers=headers)
                    if response.status_code == 200:
                        result = response.json()
                        status = result.get("status", result.get("state", "")).lower()

                        if status in ("completed", "succeeded", "success", "done"):
                            print("completed!")
                            video_data = extract_video_data(result)
                            if video_data:
                                return save_video(video_data, output_path)
                            # Try to download from URL
                            video_url = (
                                result.get("videoUrl")
                                or result.get("video_url")
                                or result.get("output", {}).get("video_url")
                                or result.get("result", {}).get("video_url")
                            )
                            # Check for GCS URI
                            gcs_uri = result.get("output", {}).get("gcsUri") or result.get("gcsUri")
                            if video_url:
                                return download_video_url(video_url, output_path, headers)
                            if gcs_uri:
                                print(f"    GCS URI: {gcs_uri}")
                                # Try converting GCS URI to HTTP URL
                                if gcs_uri.startswith("gs://"):
                                    http_url = gcs_uri.replace("gs://", "https://storage.googleapis.com/")
                                    return download_video_url(http_url, output_path, headers)
                            # Try downloading by video ID
                            print("    Trying to download video by ID...")
                            if download_video_by_id(job_id, output_path, headers):
                                return True
                            print(f"    Response keys: {list(result.keys())}")
                            return False

                        if status in ("failed", "error", "cancelled"):
                            print(f"failed: {result.get('error', 'Unknown error')}")
                            return False

                        print(f"{status}")
                        break
                except httpx.RequestError:
                    pass

            time.sleep(poll_interval)

    print("    Timeout waiting for video generation")
    return False


def download_video_url(url: str, output_path: Path, headers: dict[str, str]) -> bool:
    """Download video from URL."""
    print(f"    Downloading from URL...")
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 200:
                return save_video(response.content, output_path)
    except httpx.RequestError as e:
        print(f"    Download failed: {e}")
    return False


def download_video_by_id(video_id: str, output_path: Path, headers: dict[str, str]) -> bool:
    """Download video using dedicated download endpoints."""
    download_endpoints = [
        (f"{API_BASE_URL}/v1/videos/{video_id}/content", "stream"),
        (f"{API_BASE_URL}/v1/videos/{video_id}/download", "stream"),
        (f"{API_BASE_URL}/v1/video/{video_id}/content", "stream"),
        (f"{API_BASE_URL}/v1/video/{video_id}/download", "stream"),
    ]

    with httpx.Client(timeout=120.0) as client:
        for endpoint, _ in download_endpoints:
            print(f"    Trying: {endpoint.split('/')[-2]}/{endpoint.split('/')[-1]}...", end=" ")
            try:
                response = client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    content_type = response.headers.get("content-type", "")
                    if "video" in content_type or len(response.content) > 10000:
                        print(f"OK ({len(response.content)} bytes)")
                        return save_video(response.content, output_path)
                    else:
                        # Might be JSON with video data
                        try:
                            data = response.json()
                            video_data = extract_video_data(data)
                            if video_data:
                                print(f"OK ({len(video_data)} bytes)")
                                return save_video(video_data, output_path)
                        except Exception:
                            pass
                print(f"failed ({response.status_code})")
            except httpx.RequestError as e:
                print(f"error: {e}")
    return False


def save_video(data: bytes, output_path: Path) -> bool:
    """Save video data to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    size_mb = len(data) / (1024 * 1024)
    print(f"    Saved: {output_path} ({size_mb:.1f} MB)")
    return True


# ============================================================================
# Async parallel generation functions
# ============================================================================

async def async_submit_job(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    prompt: str,
    reference_image_b64: str,
    duration: int,
    resolution: str,
    aspect_ratio: str,
) -> str | None:
    """Submit a video generation job and return the job ID."""
    reference_images = [
        {
            "image": {
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": reference_image_b64
                }
            },
            "referenceType": "asset"
        }
    ]

    request_json = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "referenceImages": reference_images,
        "duration_seconds": duration,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
    }

    try:
        response = await client.post(
            f"{API_BASE_URL}/v1/videos",
            json=request_json,
            headers=headers,
        )

        if response.status_code in (200, 202):
            result = response.json()
            return extract_job_id(result)
    except httpx.RequestError:
        pass
    return None


async def async_poll_job(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    job_id: str,
    video_id: str,
) -> tuple[str, bool, bytes | None]:
    """Poll for job completion. Returns (video_id, success, video_data)."""
    poll_interval = 10
    max_polls = 60

    status_endpoints = [
        f"{API_BASE_URL}/v1/video/status/{job_id}",
        f"{API_BASE_URL}/v1/videos/{job_id}",
    ]

    for poll_num in range(max_polls):
        await asyncio.sleep(poll_interval)

        for endpoint in status_endpoints:
            try:
                response = await client.get(endpoint, headers=headers)
                if response.status_code == 200:
                    result = response.json()
                    status = result.get("status", result.get("state", "")).lower()

                    if status in ("completed", "succeeded", "success", "done"):
                        # Try to get video data
                        video_data = extract_video_data(result)
                        if video_data:
                            return (video_id, True, video_data)

                        # Try download endpoint
                        download_url = f"{API_BASE_URL}/v1/videos/{job_id}/content"
                        try:
                            dl_response = await client.get(download_url, headers=headers)
                            if dl_response.status_code == 200 and len(dl_response.content) > 10000:
                                return (video_id, True, dl_response.content)
                        except httpx.RequestError:
                            pass

                        return (video_id, False, None)

                    if status in ("failed", "error", "cancelled"):
                        return (video_id, False, None)

                    break
            except httpx.RequestError:
                pass

    return (video_id, False, None)


async def generate_videos_parallel(
    videos: list[tuple[str, str, dict[str, Any]]],
    mascot_b64: str,
    defaults: dict[str, Any],
    parallel: int,
    force: bool,
) -> tuple[int, int, int]:
    """Generate videos in parallel batches. Returns (success, failed, skipped)."""
    api_key = get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    success = 0
    failed = 0
    skipped = 0

    # Filter already existing videos
    to_generate = []
    for cat_name, output_dir, video in videos:
        video_id = video["id"]
        output_path = OUTPUT_ROOT / output_dir / f"{video_id}.mp4"
        if output_path.exists() and not force:
            print(f"[{video_id}] Skipping (exists)")
            skipped += 1
        else:
            to_generate.append((cat_name, output_dir, video, output_path))

    if not to_generate:
        return success, failed, skipped

    async with httpx.AsyncClient(timeout=300.0) as client:
        # Process in batches
        for batch_start in range(0, len(to_generate), parallel):
            batch = to_generate[batch_start:batch_start + parallel]
            batch_num = batch_start // parallel + 1
            total_batches = (len(to_generate) + parallel - 1) // parallel

            print(f"\n{'='*60}")
            print(f"BATCH {batch_num}/{total_batches}: Submitting {len(batch)} jobs...")
            print(f"{'='*60}")

            # Submit all jobs in batch
            jobs = {}  # job_id -> (video_id, output_path)
            for cat_name, output_dir, video, output_path in batch:
                video_id = video["id"]

                # Use per-video reference image if specified, otherwise use mascot
                reference_b64 = mascot_b64
                if "reference_image" in video:
                    reference_b64 = load_reference_image_base64(video["reference_image"])

                # Use per-video duration if specified, otherwise use default
                duration = video.get("duration_seconds", defaults["duration_seconds"])

                print(f"  [{video_id}] Submitting...", end=" ", flush=True)

                job_id = await async_submit_job(
                    client,
                    headers,
                    video["prompt"],
                    reference_b64,
                    duration,
                    defaults["resolution"],
                    defaults["aspect_ratio"],
                )

                if job_id:
                    print(f"OK (job: {job_id[:30]}...)")
                    jobs[job_id] = (video_id, output_path)
                else:
                    print("FAILED")
                    failed += 1

                # Small delay between submissions to avoid rate limit
                await asyncio.sleep(1.5)

            if not jobs:
                continue

            # Poll all jobs in parallel
            print(f"\nPolling {len(jobs)} jobs...")
            poll_tasks = [
                async_poll_job(client, headers, job_id, video_id)
                for job_id, (video_id, _) in jobs.items()
            ]

            results = await asyncio.gather(*poll_tasks)

            # Process results
            job_id_list = list(jobs.keys())
            for i, (video_id, ok, video_data) in enumerate(results):
                job_id = job_id_list[i]
                _, output_path = jobs[job_id]

                if ok and video_data:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(video_data)
                    size_mb = len(video_data) / (1024 * 1024)
                    print(f"  [{video_id}] SUCCESS - {output_path.name} ({size_mb:.1f} MB)")
                    success += 1
                else:
                    print(f"  [{video_id}] FAILED")
                    failed += 1

    return success, failed, skipped


def cmd_list(args: argparse.Namespace) -> int:
    """List all videos."""
    specs = load_specs()

    for cat_name, cat_data in specs["categories"].items():
        print(f"\n{cat_name.upper().replace('-', ' ')}")
        print("=" * 40)
        for video in cat_data["videos"]:
            print(f"  {video['id']}: {video['title']}")
            if "use_case" in video:
                print(f"    Use: {video['use_case']}")
            if "reference_image" in video:
                print(f"    Ref: {video['reference_image']}")

    total = sum(len(c["videos"]) for c in specs["categories"].values())
    print(f"\nTotal: {total} videos")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """Preview a video's prompt."""
    specs = load_specs()

    result = find_video_by_id(specs, args.id)
    if not result:
        print(f"Error: Video not found: {args.id}", file=sys.stderr)
        return 1

    cat_name, output_dir, video = result

    print(f"Video: {video['title']}")
    print(f"ID: {video['id']}")
    print(f"Category: {cat_name}")
    if "use_case" in video:
        print(f"Use case: {video['use_case']}")
    if "reference_image" in video:
        print(f"Reference: {video['reference_image']}")
    print(f"\nPrompt:\n{video['prompt']}")

    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate videos."""
    specs = load_specs()
    defaults = specs["defaults"]

    # Determine which videos to generate
    videos_to_generate = []

    if args.all:
        videos_to_generate = get_all_videos(specs)
    elif args.category:
        if args.category not in specs["categories"]:
            print(f"Error: Unknown category: {args.category}", file=sys.stderr)
            print(f"Available: {list(specs['categories'].keys())}", file=sys.stderr)
            return 1
        cat_data = specs["categories"][args.category]
        for video in cat_data["videos"]:
            videos_to_generate.append((args.category, cat_data["output_dir"], video))
    elif args.id:
        result = find_video_by_id(specs, args.id)
        if not result:
            print(f"Error: Video not found: {args.id}", file=sys.stderr)
            return 1
        videos_to_generate.append(result)
    else:
        print("Error: Specify --all, --category, or --id", file=sys.stderr)
        return 1

    print(f"Generating {len(videos_to_generate)} video(s)...")

    # Load reference images once
    print("Loading reference images...")
    mascot_b64 = load_mascot_image_base64()
    print(f"  Mascot: {len(mascot_b64)} bytes (base64)")

    logo_b64 = load_nvidia_logo_base64()
    if logo_b64:
        print(f"  NVIDIA logo: {len(logo_b64)} bytes (base64)")
    else:
        print("  NVIDIA logo: not found (optional)")

    if args.dry_run:
        for cat_name, output_dir, video in videos_to_generate:
            print(f"  [{video['id']}] {video['title']} - DRY RUN")
        return 0

    # Use parallel generation if requested
    if args.parallel and args.parallel > 1:
        print(f"\nUsing parallel generation with {args.parallel} concurrent jobs...")
        success, failed, skipped = asyncio.run(
            generate_videos_parallel(
                videos_to_generate,
                mascot_b64,
                defaults,
                args.parallel,
                args.force,
            )
        )
        print(f"\n{'='*40}")
        print(f"Complete: {success} succeeded, {failed} failed, {skipped} skipped")
        return 0 if failed == 0 else 1

    # Sequential generation (original behavior)
    success = 0
    failed = 0
    skipped = 0

    for cat_name, output_dir, video in videos_to_generate:
        video_id = video["id"]
        output_path = OUTPUT_ROOT / output_dir / f"{video_id}.mp4"

        if output_path.exists() and not args.force:
            print(f"\n[{video_id}] Skipping (exists, use --force)")
            skipped += 1
            continue

        print(f"\n[{video_id}] {video['title']}")
        print(f"  Category: {cat_name}")
        print(f"  Output: {output_path}")

        # Use per-video reference image if specified, otherwise use mascot
        reference_b64 = mascot_b64
        if "reference_image" in video:
            ref_path = video["reference_image"]
            print(f"  Reference: {ref_path}")
            reference_b64 = load_reference_image_base64(ref_path)

        # Use per-video duration if specified, otherwise use default
        duration = video.get("duration_seconds", defaults["duration_seconds"])

        ok = generate_video_with_reference(
            prompt=video["prompt"],
            output_path=output_path,
            reference_image_b64=reference_b64,
            logo_image_b64=logo_b64,
            duration=duration,
            resolution=defaults["resolution"],
            aspect_ratio=defaults["aspect_ratio"],
        )

        if ok:
            success += 1
        else:
            failed += 1

        # Rate limiting
        if videos_to_generate.index((cat_name, output_dir, video)) < len(videos_to_generate) - 1:
            print(f"  Waiting {DELAY_BETWEEN_REQUESTS}s before next request...")
            time.sleep(DELAY_BETWEEN_REQUESTS)

    print(f"\n{'='*40}")
    print(f"Complete: {success} succeeded, {failed} failed, {skipped} skipped")

    return 0 if failed == 0 else 1


def cmd_custom(args: argparse.Namespace) -> int:
    """Generate a custom video with provided prompt."""
    output_path = Path(args.output)

    # Load reference image if provided
    reference_b64 = None
    if args.reference_image:
        print(f"Loading reference image: {args.reference_image}")
        reference_b64 = load_reference_image_base64(args.reference_image)
        print(f"  Reference: {len(reference_b64)} bytes (base64)")

    print(f"\nGenerating custom video...")
    print(f"  Output: {output_path}")
    print(f"  Duration: {args.duration}s")
    print(f"  Prompt: {args.prompt[:100]}{'...' if len(args.prompt) > 100 else ''}")

    ok = generate_video_with_reference(
        prompt=args.prompt,
        output_path=output_path,
        reference_image_b64=reference_b64,
        logo_image_b64=None,
        duration=args.duration,
        resolution="720p",
        aspect_ratio="16:9",
    )

    if ok:
        print(f"✓ Successfully generated: {output_path}")
        return 0
    else:
        print(f"✗ Failed to generate video", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Nano mascot videos using Veo 3.1"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List command
    subparsers.add_parser("list", help="List all videos")

    # Preview command
    preview_parser = subparsers.add_parser("preview", help="Preview a video's prompt")
    preview_parser.add_argument("--id", required=True, help="Video ID to preview")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generate videos")
    gen_parser.add_argument("--all", action="store_true", help="Generate all videos")
    gen_parser.add_argument("--category", help="Generate all videos in category")
    gen_parser.add_argument("--id", help="Generate a specific video by ID")
    gen_parser.add_argument("--force", action="store_true", help="Regenerate existing")
    gen_parser.add_argument("--dry-run", action="store_true", help="Preview without generating")
    gen_parser.add_argument("--parallel", type=int, default=1, help="Number of concurrent jobs (default: 1)")

    # Custom command for ad-hoc video generation
    custom_parser = subparsers.add_parser("custom", help="Generate custom video with prompt")
    custom_parser.add_argument("--prompt", required=True, help="Video generation prompt")
    custom_parser.add_argument("--output", required=True, help="Output video path")
    custom_parser.add_argument("--duration", type=int, default=8, help="Video duration in seconds (default: 8)")
    custom_parser.add_argument("--reference-image", help="Optional reference image path")

    args = parser.parse_args()

    if args.command == "list":
        return cmd_list(args)
    elif args.command == "preview":
        return cmd_preview(args)
    elif args.command == "generate":
        return cmd_generate(args)
    elif args.command == "custom":
        return cmd_custom(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
