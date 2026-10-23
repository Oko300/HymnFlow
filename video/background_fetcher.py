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

# Mood → nature search keywords (all chosen for bright, green, visible scenes)
THEME_TO_KEYWORDS = {
    "Praise":           "green forest sunlight trees",
    "Worship":          "sunlight through trees forest",
    "Lament":           "gentle river flowing green nature",
    "Thanksgiving":     "golden wheat field harvest sunlight",
    "Intercession":     "calm lake reflection trees green",
    "New Beginnings":   "sunrise meadow flowers green",
    "God's Love":       "blooming flowers garden sunlight",
    "Redemption":       "waterfall forest green light",
    "Easter":           "spring cherry blossom flowers",
    "Christmas":        "snow pine trees winter sunlight",
    "Advent":           "forest path morning light mist",
    "Holy Spirit":      "wind moving grass field sunlight",
    "God's Protection": "green valley mountains sunlight",
    "Spiritual Warfare":"sunlight breaking clouds green",
    "Faithfulness":     "flowing river green forest trees",
    "default":          "green forest nature sunlight trees",
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
                raw_path = out_path.replace("_bg.mp4", "_bg_raw.mp4")
                with open(raw_path, "wb") as f:
                    f.write(video_data.content)
                # Validate: reject files smaller than 500 KB (corrupt/redirect pages)
                size_kb = os.path.getsize(raw_path) // 1024
                if size_kb < 500:
                    logger.warning(f"Downloaded file too small ({size_kb} KB) -- skipping, likely corrupt")
                    os.remove(raw_path)
                    continue
                # Re-encode to H.264/yuv420p so MoviePy renders correctly
                # (Pixabay often uses H.265/HEVC which renders as black frames)
                logger.info(f"Re-encoding to H.264 for MoviePy compatibility...")
                import subprocess
                result = subprocess.run([
                    "ffmpeg", "-y",
                    "-i", raw_path,
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "fast",
                    "-crf", "23",
                    "-an",          # no audio needed in background
                    out_path
                ], capture_output=True, text=True)
                os.remove(raw_path)
                if result.returncode != 0:
                    logger.warning(f"Re-encode failed: {result.stderr[-200:]}")
                    continue
                final_kb = os.path.getsize(out_path) // 1024
                logger.info(f"Background video ready: {out_path} ({final_kb:,} KB)")
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
