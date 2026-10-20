"""
HymnFlow -- Auto Music Downloader
Downloads worship music tracks from Pixabay at the start of each GitHub Actions run.
Searches for tracks with real human vocals when possible.
"""

import os
import sys
import requests
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("MusicDownloader")

MUSIC_DIR   = "music"
API_KEY     = os.environ.get("PIXABAY_API_KEY", "")
TRACK_LIMIT = 5   # Download 5 tracks per run (enough variety)

SEARCH_TERMS = [
    "worship gospel vocals",
    "christian hymn piano",
    "gospel choir worship",
    "worship music emotional",
    "gospel spiritual music",
]


def download_tracks():
    if not API_KEY:
        logger.warning("PIXABAY_API_KEY not set -- skipping music download")
        return

    os.makedirs(MUSIC_DIR, exist_ok=True)
    existing = [f for f in os.listdir(MUSIC_DIR) if f.endswith(".mp3")]
    if len(existing) >= TRACK_LIMIT:
        logger.info(f"Already have {len(existing)} tracks -- skipping download")
        return

    downloaded = 0
    for term in SEARCH_TERMS:
        if downloaded >= TRACK_LIMIT:
            break
        try:
            url = (
                f"https://pixabay.com/api/"
                f"?key={API_KEY}"
                f"&q={requests.utils.quote(term)}"
                f"&media_type=music"
                f"&per_page=3"
            )
            resp = requests.get(url, timeout=20)
            data = resp.json()
            hits = data.get("hits", [])

            for hit in hits:
                if downloaded >= TRACK_LIMIT:
                    break
                audio_url = hit.get("audio", {}).get("url") or hit.get("tags", "")
                # Pixabay audio API v2 format
                track_url = hit.get("audio", "")
                if not isinstance(track_url, str) or not track_url.startswith("http"):
                    continue
                fname = f"track_{downloaded+1:02d}_{term.replace(' ', '_')[:20]}.mp3"
                fpath = os.path.join(MUSIC_DIR, fname)
                logger.info(f"Downloading: {fname}")
                r = requests.get(track_url, timeout=60)
                with open(fpath, "wb") as f:
                    f.write(r.content)
                downloaded += 1
                logger.info(f"Saved: {fpath}")

        except Exception as e:
            logger.error(f"Download error for '{term}': {e}")

    if downloaded == 0:
        logger.warning(
            "Could not auto-download music via API. "
            "Please manually add .mp3 files to the /music folder in your repo."
        )
    else:
        logger.info(f"Downloaded {downloaded} music track(s)")


if __name__ == "__main__":
    download_tracks()
