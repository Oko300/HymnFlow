"""
HymnFlow -- Telegram Video Notifier
Sends the finished hymn video directly to your Telegram chat.
File size confirmed safe: our videos are 30-90MB, well under the 2GB limit.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)


def send_video_to_telegram(
    video_path: str,
    hymn: dict,
    hymn_id: str,
) -> bool:
    """
    Send the hymn video directly to Telegram.
    Includes caption with title, scripture, and approve/reject instructions.
    Returns True on success.
    """
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return False

    size_mb = os.path.getsize(video_path) / (1024 * 1024)
    logger.info(f"Sending video to Telegram ({size_mb:.1f} MB)...")

    title     = hymn.get("title", "Hymn")
    theme     = hymn.get("theme", "")
    style     = hymn.get("style", "")
    bible_ref = hymn.get("bible_reference", "")
    seo_title = hymn.get("seo_title", title)

    caption = (
        f"*HymnFlow -- Daily Hymn*\n\n"
        f"*{title}*\n"
        f"Theme: {theme} | Style: {style}\n"
        f"Scripture: {bible_ref}\n\n"
        f"*YouTube Title:* {seo_title}\n\n"
        f"Watch the video above, then reply:\n"
        f"/approve {hymn_id[:8]} -- to post to YouTube\n"
        f"/reject {hymn_id[:8]} -- to discard and regenerate"
    )

    url = f"https://api.telegram.org/bot{token}/sendVideo"

    try:
        with open(video_path, "rb") as f:
            response = requests.post(
                url,
                data={
                    "chat_id":              chat_id,
                    "caption":              caption,
                    "parse_mode":           "Markdown",
                    "supports_streaming":   True,
                },
                files={"video": f},
                timeout=300,   # 5 min timeout for upload
            )

        if response.status_code == 200:
            logger.info("Video sent to Telegram successfully")
            return True
        else:
            logger.error(f"Telegram send failed: {response.status_code} {response.text}")
            return False

    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


def send_text_to_telegram(message: str) -> bool:
    """Send a plain text message to Telegram (for errors/status updates)."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return False

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(
            url,
            data={
                "chat_id":    chat_id,
                "text":       message,
                "parse_mode": "Markdown",
            },
            timeout=30,
        )
        return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram message error: {e}")
        return False
