"""
HymnFlow -- Master Pipeline
This is the single script GitHub Actions runs every morning.
It does everything end to end:
  1. Generate hymn with Gemini
  2. Download matching nature background video
  3. Build the video with lyrics overlay and worship music
  4. Send the video to Telegram for your approval
  5. Update Supabase with the status

Run locally: python master_pipeline.py
Run on GitHub Actions: triggered automatically at 5am UTC daily
"""

import logging
import os
import sys
import traceback
from datetime import datetime, timezone

# Ensure project root is in path (needed for GitHub Actions)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("MasterPipeline")


def run():
    from bot.notifier import send_text_to_telegram, send_video_to_telegram
    from db.database import save_video, mark_rendered

    now = datetime.now(timezone.utc)
    logger.info(f"HymnFlow pipeline started at {now.strftime('%Y-%m-%d %H:%M UTC')}")

    # ── Step 1: Generate Hymn ─────────────────────────────────────────────────
    logger.info("STEP 1: Generating hymn with Gemini...")
    try:
        from generator.hymn_gen import generate_hymn
        hymn = generate_hymn()
        hymn_id = hymn["id"]
        logger.info(f"Hymn generated: '{hymn['title']}' (ID: {hymn_id})")
    except Exception as e:
        msg = f"STEP 1 FAILED -- Hymn generation error: {e}"
        logger.error(msg)
        send_text_to_telegram(f"*HymnFlow Error*\n\n{msg}")
        sys.exit(1)

    # ── Step 2: Download Nature Background ───────────────────────────────────
    logger.info("STEP 2: Downloading nature background video...")
    try:
        from video.background_fetcher import get_background_video
        bg_path = get_background_video(hymn, hymn_id)
        if bg_path:
            logger.info(f"Background video ready: {bg_path}")
        else:
            logger.warning("No background video found -- will use colour background")
    except Exception as e:
        logger.warning(f"Background download failed (non-fatal): {e}")
        bg_path = None

    # ── Step 3: Build Video ───────────────────────────────────────────────────
    logger.info("STEP 3: Building video...")
    try:
        from video.video_engine import build_video
        result = build_video(hymn, hymn_id, bg_video_path=bg_path)
        video_path     = result["video_path"]
        thumbnail_path = result["thumbnail_path"]
        duration       = result["duration"]
        logger.info(f"Video built: {video_path} ({duration:.1f}s)")

        # Update Supabase
        save_video(hymn_id, video_path, thumbnail_path)
        mark_rendered(hymn_id)
        logger.info("Supabase updated: status = rendered")

    except Exception as e:
        msg = f"STEP 3 FAILED -- Video build error:\n{traceback.format_exc()}"
        logger.error(msg)
        send_text_to_telegram(
            f"*HymnFlow Error*\n\nVideo build failed for '{hymn.get('title')}'.\n\n`{str(e)[:300]}`"
        )
        sys.exit(1)

    # ── Step 4: Send to Telegram ──────────────────────────────────────────────
    logger.info("STEP 4: Sending video to Telegram...")
    try:
        success = send_video_to_telegram(video_path, hymn, hymn_id)
        if success:
            logger.info("Video sent to Telegram successfully")
        else:
            logger.error("Telegram send failed")
            send_text_to_telegram(
                f"*HymnFlow*\n\nVideo was built but failed to send.\n"
                f"Hymn: '{hymn.get('title')}'\nID: `{hymn_id}`"
            )
    except Exception as e:
        logger.error(f"STEP 4 FAILED: {e}")
        send_text_to_telegram(f"*HymnFlow Error*\n\nTelegram delivery failed: {str(e)[:200]}")

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    run()
