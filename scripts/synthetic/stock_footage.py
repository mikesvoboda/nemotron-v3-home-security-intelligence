# ABOUTME: Downloads stock footage from Pexels and Pixabay APIs for synthetic data testing.
# ABOUTME: Maps scenario templates to relevant search terms and filters appropriate content.
"""
Stock Footage Downloader for Synthetic Data Generation System.

This module provides functionality to download stock footage from Pexels and Pixabay
that matches the criteria defined in scenario templates. This supplements AI-generated
content with real-world footage for more comprehensive testing.

Usage:
    from scripts.synthetic.stock_footage import StockFootageDownloader

    downloader = StockFootageDownloader()

    # Search and download videos matching a scenario
    results = await downloader.search_videos(
        scenario="vandalism",
        count=5,
        source="pixabay"
    )

    for result in results:
        await downloader.download(result, output_path)

Requires API keys:
    - PEXELS_API_KEY for Pexels
    - PIXABAY_API_KEY for Pixabay
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class StockSource(Enum):
    """Available stock footage sources."""

    PEXELS = "pexels"
    PIXABAY = "pixabay"
    ALL = "all"


@dataclass
class StockResult:
    """Result from a stock footage search."""

    id: str
    source: StockSource
    title: str
    url: str
    download_url: str
    thumbnail_url: str | None = None
    duration: int | None = None  # seconds
    width: int | None = None
    height: int | None = None
    file_size: int | None = None  # bytes
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class StockFootageError(Exception):
    """Base exception for stock footage errors."""

    pass


class APIKeyNotFoundError(StockFootageError):
    """Raised when required API key is not found."""

    pass


# Search term mappings for each scenario
# Maps scenario IDs to lists of search queries optimized for stock footage sites
SCENARIO_SEARCH_TERMS: dict[str, list[str]] = {
    # Normal activity scenarios
    "resident_arrival": [
        "person walking home entrance",
        "homeowner arriving driveway",
        "person unlocking front door",
        "residential entrance walking",
    ],
    "delivery_driver": [
        "delivery driver package porch",
        "package delivery doorstep",
        "courier delivery residential",
        "fedex ups delivery home",
    ],
    "pet_activity": [
        "dog yard residential",
        "cat porch home",
        "pet outdoor house",
        "dog front yard",
    ],
    "vehicle_parking": [
        "car parking driveway residential",
        "vehicle arriving home",
        "car driveway house",
        "parking residential garage",
    ],
    "yard_maintenance": [
        "lawn mower residential",
        "landscaping workers yard",
        "gardening yard work",
        "lawn care service residential",
        "hedge trimming landscaping",
    ],
    # Suspicious activity scenarios
    "loitering": [
        "person standing suspicious",
        "stranger waiting door",
        "person looking around house",
        "suspicious person residential",
    ],
    "prowling": [
        "person checking windows",
        "prowler residential night",
        "suspicious person walking house",
        "person looking through window",
    ],
    "casing": [
        "person watching house",
        "surveillance residential",
        "person photographing house",
        "stranger observing property",
    ],
    "tailgating": [
        "person following through gate",
        "tailgating security gate",
        "unauthorized entry door",
        "following through entrance",
        "access control breach",
    ],
    # Threat scenarios
    "break_in_attempt": [
        "break in door",
        "burglar breaking window",
        "forced entry home",
        "intruder breaking in",
        "burglary attempt",
    ],
    "package_theft": [
        "porch pirate stealing",
        "package theft doorstep",
        "stealing package porch",
        "theft delivery package",
    ],
    "vandalism": [
        "graffiti spray painting",
        "vandalism property damage",
        "breaking window vandal",
        "property destruction",
        "spray paint graffiti wall",
    ],
    "weapon_visible": [
        "security camera weapon",
        "person with knife",
        "armed intruder",
        # Note: Some searches may be filtered by stock sites
    ],
}

# Category-level search terms (used as fallback)
CATEGORY_SEARCH_TERMS: dict[str, list[str]] = {
    "normal": [
        "residential daily activity",
        "home entrance normal",
        "suburban neighborhood",
    ],
    "suspicious": [
        "suspicious person surveillance",
        "security camera suspicious",
        "prowler cctv footage",
    ],
    "threats": [
        "security breach footage",
        "crime security camera",
        "burglary cctv",
    ],
}


class StockFootageDownloader:
    """
    Downloads stock footage from Pexels and Pixabay APIs.

    Handles searching, filtering, and downloading video/image content
    that matches scenario criteria for synthetic data testing.
    """

    # API endpoints
    PEXELS_BASE_URL = "https://api.pexels.com"
    PIXABAY_BASE_URL = "https://pixabay.com/api"

    # Default settings
    DEFAULT_PER_PAGE = 20
    DEFAULT_MIN_WIDTH = 1280
    DEFAULT_MIN_HEIGHT = 720

    def __init__(
        self,
        pexels_api_key: str | None = None,
        pixabay_api_key: str | None = None,
    ):
        """
        Initialize the StockFootageDownloader.

        Args:
            pexels_api_key: Pexels API key. If not provided, reads from PEXELS_API_KEY env var.
            pixabay_api_key: Pixabay API key. If not provided, reads from PIXABAY_API_KEY env var.
        """
        self._pexels_api_key = pexels_api_key
        self._pixabay_api_key = pixabay_api_key

    @property
    def pexels_api_key(self) -> str | None:
        """Get Pexels API key from init or environment."""
        if self._pexels_api_key:
            return self._pexels_api_key
        return os.environ.get("PEXELS_API_KEY")

    @property
    def pixabay_api_key(self) -> str | None:
        """Get Pixabay API key from init or environment."""
        if self._pixabay_api_key:
            return self._pixabay_api_key
        return os.environ.get("PIXABAY_API_KEY")

    def get_search_terms(self, scenario_id: str, category: str | None = None) -> list[str]:
        """
        Get search terms for a scenario.

        Args:
            scenario_id: The scenario identifier.
            category: Optional category for fallback terms.

        Returns:
            List of search term strings.
        """
        terms = SCENARIO_SEARCH_TERMS.get(scenario_id, [])
        if not terms and category:
            terms = CATEGORY_SEARCH_TERMS.get(category, [])
        if not terms:
            # Generic fallback
            terms = ["security camera footage", "surveillance residential"]
        return terms

    async def search_pexels_videos(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
        min_width: int | None = None,
        min_height: int | None = None,
        orientation: str | None = None,
    ) -> list[StockResult]:
        """
        Search for videos on Pexels.

        Args:
            query: Search query string.
            per_page: Number of results per page (max 80).
            page: Page number for pagination.
            min_width: Minimum video width in pixels.
            min_height: Minimum video height in pixels.
            orientation: Filter by orientation (landscape, portrait, square).

        Returns:
            List of StockResult objects.
        """
        if not self.pexels_api_key:
            logger.warning("Pexels API key not found, skipping Pexels search")
            return []

        params: dict[str, Any] = {
            "query": query,
            "per_page": min(per_page, 80),
            "page": page,
        }
        if orientation:
            params["orientation"] = orientation

        headers = {
            "Authorization": self.pexels_api_key,
        }

        results: list[StockResult] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.PEXELS_BASE_URL}/videos/search",
                    params=params,
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Pexels API error: {response.status_code} - {response.text[:200]}"
                    )
                    return []

                data = response.json()
                videos = data.get("videos", [])

                for video in videos:
                    # Get the best quality video file
                    video_files = video.get("video_files", [])
                    if not video_files:
                        continue

                    # Sort by quality (width) and pick best that meets requirements
                    video_files.sort(key=lambda x: x.get("width", 0), reverse=True)

                    best_file = None
                    for vf in video_files:
                        width = vf.get("width", 0)
                        height = vf.get("height", 0)
                        if min_width and width < min_width:
                            continue
                        if min_height and height < min_height:
                            continue
                        best_file = vf
                        break

                    # Fallback to highest quality if none meet requirements
                    if not best_file and video_files:
                        best_file = video_files[0]

                    if not best_file:
                        continue

                    result = StockResult(
                        id=str(video.get("id")),
                        source=StockSource.PEXELS,
                        title=video.get("url", "").split("/")[-2]
                        if video.get("url")
                        else f"pexels_{video.get('id')}",
                        url=video.get("url", ""),
                        download_url=best_file.get("link", ""),
                        thumbnail_url=video.get("image"),
                        duration=video.get("duration"),
                        width=best_file.get("width"),
                        height=best_file.get("height"),
                        file_size=best_file.get("size"),
                        tags=[],  # Pexels doesn't return tags in search
                        metadata={
                            "user": video.get("user", {}).get("name"),
                            "quality": best_file.get("quality"),
                        },
                    )
                    results.append(result)

        except httpx.RequestError as e:
            logger.error(f"Pexels request failed: {e}")

        return results

    async def search_pixabay_videos(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
        min_width: int | None = None,
        min_height: int | None = None,
        video_type: str = "all",
        category: str | None = None,
    ) -> list[StockResult]:
        """
        Search for videos on Pixabay.

        Args:
            query: Search query string.
            per_page: Number of results per page (3-200).
            page: Page number for pagination.
            min_width: Minimum video width in pixels.
            min_height: Minimum video height in pixels.
            video_type: Filter by type (all, film, animation).
            category: Filter by category.

        Returns:
            List of StockResult objects.
        """
        if not self.pixabay_api_key:
            logger.warning("Pixabay API key not found, skipping Pixabay search")
            return []

        params: dict[str, Any] = {
            "key": self.pixabay_api_key,
            "q": query,
            "per_page": min(max(per_page, 3), 200),
            "page": page,
            "video_type": video_type,
            "safesearch": "true",
        }
        if min_width:
            params["min_width"] = min_width
        if min_height:
            params["min_height"] = min_height
        if category:
            params["category"] = category

        results: list[StockResult] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.PIXABAY_BASE_URL}/videos/",
                    params=params,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Pixabay API error: {response.status_code} - {response.text[:200]}"
                    )
                    return []

                data = response.json()
                videos = data.get("hits", [])

                for video in videos:
                    # Pixabay provides multiple sizes: large, medium, small, tiny
                    video_data = video.get("videos", {})

                    # Prefer large, then medium
                    for size in ["large", "medium", "small"]:
                        if size in video_data:
                            vd = video_data[size]
                            width = vd.get("width", 0)
                            height = vd.get("height", 0)

                            # Check minimum requirements
                            if min_width and width < min_width:
                                continue
                            if min_height and height < min_height:
                                continue

                            result = StockResult(
                                id=str(video.get("id")),
                                source=StockSource.PIXABAY,
                                title=video.get("tags", "").split(",")[0].strip()
                                if video.get("tags")
                                else f"pixabay_{video.get('id')}",
                                url=video.get("pageURL", ""),
                                download_url=vd.get("url", ""),
                                thumbnail_url=video.get("userImageURL"),
                                duration=video.get("duration"),
                                width=width,
                                height=height,
                                file_size=vd.get("size"),
                                tags=video.get("tags", "").split(", ") if video.get("tags") else [],
                                metadata={
                                    "user": video.get("user"),
                                    "views": video.get("views"),
                                    "downloads": video.get("downloads"),
                                    "quality": size,
                                },
                            )
                            results.append(result)
                            break

        except httpx.RequestError as e:
            logger.error(f"Pixabay request failed: {e}")

        return results

    async def search_pexels_images(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
        orientation: str | None = None,
    ) -> list[StockResult]:
        """
        Search for images on Pexels.

        Args:
            query: Search query string.
            per_page: Number of results per page (max 80).
            page: Page number for pagination.
            orientation: Filter by orientation (landscape, portrait, square).

        Returns:
            List of StockResult objects.
        """
        if not self.pexels_api_key:
            logger.warning("Pexels API key not found, skipping Pexels search")
            return []

        params: dict[str, Any] = {
            "query": query,
            "per_page": min(per_page, 80),
            "page": page,
        }
        if orientation:
            params["orientation"] = orientation

        headers = {
            "Authorization": self.pexels_api_key,
        }

        results: list[StockResult] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.PEXELS_BASE_URL}/v1/search",
                    params=params,
                    headers=headers,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Pexels API error: {response.status_code} - {response.text[:200]}"
                    )
                    return []

                data = response.json()
                photos = data.get("photos", [])

                for photo in photos:
                    src = photo.get("src", {})
                    # Use 'large2x' or 'original' for best quality
                    download_url = src.get("large2x") or src.get("original") or src.get("large")

                    if not download_url:
                        continue

                    result = StockResult(
                        id=str(photo.get("id")),
                        source=StockSource.PEXELS,
                        title=photo.get("alt", f"pexels_{photo.get('id')}"),
                        url=photo.get("url", ""),
                        download_url=download_url,
                        thumbnail_url=src.get("medium"),
                        width=photo.get("width"),
                        height=photo.get("height"),
                        tags=[],
                        metadata={
                            "photographer": photo.get("photographer"),
                            "avg_color": photo.get("avg_color"),
                        },
                    )
                    results.append(result)

        except httpx.RequestError as e:
            logger.error(f"Pexels request failed: {e}")

        return results

    async def search_pixabay_images(
        self,
        query: str,
        per_page: int = 20,
        page: int = 1,
        min_width: int | None = None,
        min_height: int | None = None,
        image_type: str = "photo",
        category: str | None = None,
    ) -> list[StockResult]:
        """
        Search for images on Pixabay.

        Args:
            query: Search query string.
            per_page: Number of results per page (3-200).
            page: Page number for pagination.
            min_width: Minimum image width in pixels.
            min_height: Minimum image height in pixels.
            image_type: Filter by type (all, photo, illustration, vector).
            category: Filter by category.

        Returns:
            List of StockResult objects.
        """
        if not self.pixabay_api_key:
            logger.warning("Pixabay API key not found, skipping Pixabay search")
            return []

        params: dict[str, Any] = {
            "key": self.pixabay_api_key,
            "q": query,
            "per_page": min(max(per_page, 3), 200),
            "page": page,
            "image_type": image_type,
            "safesearch": "true",
        }
        if min_width:
            params["min_width"] = min_width
        if min_height:
            params["min_height"] = min_height
        if category:
            params["category"] = category

        results: list[StockResult] = []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.PIXABAY_BASE_URL}/",
                    params=params,
                )

                if response.status_code != 200:
                    logger.error(
                        f"Pixabay API error: {response.status_code} - {response.text[:200]}"
                    )
                    return []

                data = response.json()
                images = data.get("hits", [])

                for image in images:
                    result = StockResult(
                        id=str(image.get("id")),
                        source=StockSource.PIXABAY,
                        title=image.get("tags", "").split(",")[0].strip()
                        if image.get("tags")
                        else f"pixabay_{image.get('id')}",
                        url=image.get("pageURL", ""),
                        download_url=image.get("largeImageURL", ""),
                        thumbnail_url=image.get("previewURL"),
                        width=image.get("imageWidth"),
                        height=image.get("imageHeight"),
                        file_size=image.get("imageSize"),
                        tags=image.get("tags", "").split(", ") if image.get("tags") else [],
                        metadata={
                            "user": image.get("user"),
                            "views": image.get("views"),
                            "downloads": image.get("downloads"),
                        },
                    )
                    results.append(result)

        except httpx.RequestError as e:
            logger.error(f"Pixabay request failed: {e}")

        return results

    async def search_for_scenario(
        self,
        scenario_id: str,
        category: str | None = None,
        media_type: str = "video",
        count: int = 10,
        source: StockSource = StockSource.ALL,
    ) -> list[StockResult]:
        """
        Search for stock footage matching a scenario.

        Args:
            scenario_id: The scenario identifier to search for.
            category: Optional category for fallback terms.
            media_type: Type of media to search for (video or image).
            count: Target number of results.
            source: Which stock source(s) to search.

        Returns:
            List of StockResult objects.
        """
        search_terms = self.get_search_terms(scenario_id, category)
        all_results: list[StockResult] = []
        seen_ids: set[str] = set()

        # Calculate how many results to get per term
        terms_to_use = min(len(search_terms), 3)  # Use up to 3 search terms
        per_term = max(count // terms_to_use, 5)

        for term in search_terms[:terms_to_use]:
            if len(all_results) >= count:
                break

            logger.info(f"Searching for '{term}'...")

            if media_type == "video":
                if source in (StockSource.ALL, StockSource.PEXELS):
                    pexels_results = await self.search_pexels_videos(
                        term,
                        per_page=per_term,
                        min_width=self.DEFAULT_MIN_WIDTH,
                        min_height=self.DEFAULT_MIN_HEIGHT,
                    )
                    for r in pexels_results:
                        key = f"{r.source.value}_{r.id}"
                        if key not in seen_ids:
                            seen_ids.add(key)
                            all_results.append(r)

                if source in (StockSource.ALL, StockSource.PIXABAY):
                    pixabay_results = await self.search_pixabay_videos(
                        term,
                        per_page=per_term,
                        min_width=self.DEFAULT_MIN_WIDTH,
                        min_height=self.DEFAULT_MIN_HEIGHT,
                    )
                    for r in pixabay_results:
                        key = f"{r.source.value}_{r.id}"
                        if key not in seen_ids:
                            seen_ids.add(key)
                            all_results.append(r)
            else:
                # Image search
                if source in (StockSource.ALL, StockSource.PEXELS):
                    pexels_results = await self.search_pexels_images(
                        term,
                        per_page=per_term,
                    )
                    for r in pexels_results:
                        key = f"{r.source.value}_{r.id}"
                        if key not in seen_ids:
                            seen_ids.add(key)
                            all_results.append(r)

                if source in (StockSource.ALL, StockSource.PIXABAY):
                    pixabay_results = await self.search_pixabay_images(
                        term,
                        per_page=per_term,
                        min_width=self.DEFAULT_MIN_WIDTH,
                        min_height=self.DEFAULT_MIN_HEIGHT,
                    )
                    for r in pixabay_results:
                        key = f"{r.source.value}_{r.id}"
                        if key not in seen_ids:
                            seen_ids.add(key)
                            all_results.append(r)

        logger.info(f"Found {len(all_results)} total results for scenario '{scenario_id}'")
        return all_results[:count]

    async def download(
        self,
        result: StockResult,
        output_path: Path,
    ) -> bool:
        """
        Download a stock footage file.

        Args:
            result: StockResult object containing download URL.
            output_path: Path to save the downloaded file.

        Returns:
            True if download was successful, False otherwise.
        """
        if not result.download_url:
            logger.error(f"No download URL for {result.id}")
            return False

        logger.info(f"Downloading {result.source.value} {result.id} to {output_path}...")

        try:
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                response = await client.get(result.download_url)

                if response.status_code != 200:
                    logger.error(f"Download failed: {response.status_code}")
                    return False

                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file
                output_path.write_bytes(response.content)
                size_kb = len(response.content) / 1024
                logger.info(f"Downloaded {output_path.name} ({size_kb:.1f} KB)")
                return True

        except httpx.RequestError as e:
            logger.error(f"Download failed: {e}")
            return False


# Synchronous wrapper functions
def search_stock_sync(
    scenario_id: str,
    category: str | None = None,
    media_type: str = "video",
    count: int = 10,
    source: str = "all",
) -> list[StockResult]:
    """
    Synchronous wrapper for searching stock footage.

    Args:
        scenario_id: The scenario identifier.
        category: Optional category for fallback.
        media_type: Type of media (video or image).
        count: Target number of results.
        source: Stock source (pexels, pixabay, or all).

    Returns:
        List of StockResult objects.
    """
    source_enum = StockSource(source.lower())
    downloader = StockFootageDownloader()
    return asyncio.run(
        downloader.search_for_scenario(
            scenario_id=scenario_id,
            category=category,
            media_type=media_type,
            count=count,
            source=source_enum,
        )
    )


def download_stock_sync(
    result: StockResult,
    output_path: Path,
) -> bool:
    """
    Synchronous wrapper for downloading stock footage.

    Args:
        result: StockResult to download.
        output_path: Path to save the file.

    Returns:
        True if successful, False otherwise.
    """
    downloader = StockFootageDownloader()
    return asyncio.run(downloader.download(result, output_path))


__all__ = [
    "CATEGORY_SEARCH_TERMS",
    "SCENARIO_SEARCH_TERMS",
    "APIKeyNotFoundError",
    "StockFootageDownloader",
    "StockFootageError",
    "StockResult",
    "StockSource",
    "download_stock_sync",
    "search_stock_sync",
]
