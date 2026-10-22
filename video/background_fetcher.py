"""
HymnFlow -- Background Video Engine
Downloads nature footage from Pixabay/Pexels matching the hymn theme.
Falls back to animated gradient if both APIs fail.
"""

import os
import logging
import requests
from config import OUTPUT_DIR

logger = logging.getLogger(__name__)

# Mood → nature search keywords
THEME_TO_KEYWORDS = {
    "Praise":           "sunrise golden light worship",
    "Worship":          "mountain clouds heaven light",
    "Lament":           "rain window reflection calm",
    "Thanksgiving":     "harvest field sunlight nature",
    "Intercession":     "ocean waves peaceful shore",
    "New Beginnings":   "sunrise dawn new day",
    "God's Love":       "sunset warm light sky",
    "Redemption":       "waterfall flowing river light",
    "Easter":           "spring flowers bloom sunrise",
    "Christmas":        "snow winter peaceful night",
    "Advent":           "candle light dark hope",
    "Holy Spirit":      "wind moving trees light",
    "God's Protection": "eagle soaring mountain sky",
    "Spiritual Warfare":"storm clouds breaking light",
    "Faithfulness":     "river flowing mountains peaceful",
    "default":          "nature peaceful worship light",
}


def get_keyword(theme: str, style: str) -> str:
    """Pick best search keyword for the hymn's theme."""
    for key in THEME_TO_KEYWORDS:
        if key.lower() in theme.lower():
            return THEME_TO_KEYWORDS[key]
    return THEME_TO_KEYWORDS["default"]


def download_pixabay_video(keyword: str, hymn_id: str, api_key: str) -> str | None:
    """
    Search Pixabay for a nature video matching the keyword.
    Downloads the medium quality MP4 (suitable for 1080p overlay).
    Returns local file path or None if failed.
    """
    try:
        url = (
            f"https://pixabay.com/api/videos/"
            f"?key={api_key}"
            f"&q={requests.utils.quote(keyword)}"
            f"&video_type=film"
            f"&category=nature"
            f"&min_duration=30"
            f"&per_page=5"
            f"&safesearch=true"
        )
        resp = requests.get(url, timeout=30)
        data = resp.json()

        hits = data.get("hits", [])
        if not hits:
            logger.warning(f"Pixabay: no results for '{keyword}'")
            return None

        # Pick the first result with a medium or large video
        for hit in hits:
            videos = hit.get("videos", {})
            video_url = (
                videos.get("medium", {}).get("url") or
                videos.get("large",  {}).get("url") or
                videos.get("small",  {}).get("url")
            )
            if video_url:
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                out_path = os.path.join(OUTPUT_DIR, f"{hymn_id}_bg.mp4")
                logger.info(f"Downloading Pixabay video: {video_url[:60]}...")
                video_data = requests.get(video_url, timeout=120)
                with open(out_path, "wb") as f:
                    f.write(video_data.content)
                logger.info(f"Background video saved: {out_path}")
                return out_path

        logger.warning("Pixabay: no usable video URL in results")
        return None

    except Exception as e:
        logger.error(f"Pixabay download error: {e}")
        return None


def download_pexels_video(keyword: str, hymn_id: str, api_key: str) -> str | None:
    """
    Fallback: search Pexels for a nature video.
    Returns local file path or None if failed.
    """
    try:
        headers = {"Authorization": api_key}
        url = (
            f"https://api.pexels.com/videos/search"
            f"?query={requests.utils.quote(keyword)}"
            f"&per_page=5"
            f"&orientation=landscape"
        )
        resp = requests.get(url, headers=headers, timeout=30)
        data = resp.json()

        videos = data.get("videos", [])
        if not videos:
            logger.warning(f"Pexels: no results for '{keyword}'")
            return None

        for video in videos:
            files = video.get("video_files", [])
            # Prefer HD 1280 or 1920 width
            hd = next(
                (f for f in files if f.get("width", 0) >= 1280
                 and f.get("quality") == "hd"),
                files[0] if files else None
            )
            if hd and hd.get("link"):
                out_path = os.path.join(OUTPUT_DIR, f"{hymn_id}_bg.mp4")
                logger.info(f"Downloading Pexels video: {hd['link'][:60]}...")
                video_data = requests.get(hd["link"], timeout=120)
                with open(out_path, "wb") as f:
                    f.write(video_data.content)
                logger.info(f"Background video saved: {out_path}")
                return out_path

        return None

    except Exception as e:
        logger.error(f"Pexels download error: {e}")
        return None


def get_background_video(hymn: dict, hymn_id: str) -> str | None:
    """
    Main entry point. Tries Pixabay first, then Pexels.
    Returns path to downloaded background video, or None.
    """
    theme   = hymn.get("theme", "")
    style   = hymn.get("style", "")
    keyword = get_keyword(theme, style)
    logger.info(f"Searching for background video: '{keyword}'")

    pixabay_key = os.getenv("PIXABAY_API_KEY", "")
    pexels_key  = os.getenv("PEXELS_API_KEY", "")

    # Try Pixabay first
    if pixabay_key:
        path = download_pixabay_video(keyword, hymn_id, pixabay_key)
        if path:
            return path
        # Retry with simpler keyword
        simple = keyword.split()[0]
        path = download_pixabay_video(simple, hymn_id, pixabay_key)
        if path:
            return path

    # Fallback to Pexels
    if pexels_key:
        path = download_pexels_video(keyword, hymn_id, pexels_key)
        if path:
            return path

    logger.warning("Both Pixabay and Pexels failed -- will use animated gradient")
    return None
