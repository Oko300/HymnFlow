"""
HymnFlow — Central Configuration
All API keys, settings, and constants live here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini API Keys (rotate across 10 Google accounts) ──────────────────────
GEMINI_API_KEYS = [
    key.strip()
    for key in os.getenv("GEMINI_API_KEYS", "").split(",")
    if key.strip()
]

# ── Edge TTS (Microsoft Neural — free, no API key, no billing) ───────────────
# Chosen voice: MichelleNeural — pleasant, smooth, reverent
TTS_VOICE_NAME  = os.getenv("TTS_VOICE_NAME",  "en-US-MichelleNeural")
TTS_SPEAKING_RATE = os.getenv("TTS_SPEAKING_RATE", "+0%")
TTS_PITCH       = os.getenv("TTS_PITCH",        "-2Hz")

# ── Telegram ─────────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")  # Your personal chat ID

# ── YouTube ──────────────────────────────────────────────────────────────────
YOUTUBE_CLIENT_SECRETS_FILE = os.getenv("YOUTUBE_CLIENT_SECRETS_FILE", "client_secrets.json")
YOUTUBE_CREDENTIALS_FILE = os.getenv("YOUTUBE_CREDENTIALS_FILE", "youtube_token.json")

# ── Supabase ─────────────────────────────────────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# ── Scheduler ────────────────────────────────────────────────────────────────
# Time to generate and send the daily hymn for your review (24h format, UTC)
DAILY_GENERATION_HOUR = int(os.getenv("DAILY_GENERATION_HOUR", "6"))
DAILY_GENERATION_MINUTE = int(os.getenv("DAILY_GENERATION_MINUTE", "0"))

# ── Video Settings ───────────────────────────────────────────────────────────
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 24
VIDEO_DURATION_PER_LINE = 4       # Seconds each lyric line stays on screen
BIBLE_VERSE_DISPLAY_DURATION = 8  # Seconds the closing bible verse stays

# ── Fonts ────────────────────────────────────────────────────────────────────
# These will be downloaded on first run if not present
LYRIC_FONT = os.getenv("LYRIC_FONT", "fonts/Cinzel-Regular.ttf")
VERSE_FONT = os.getenv("VERSE_FONT", "fonts/Lato-Italic.ttf")

# ── Background Video APIs ────────────────────────────────────────────────────
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
PEXELS_API_KEY  = os.getenv("PEXELS_API_KEY",  "")

# ── Output paths ─────────────────────────────────────────────────────────────
OUTPUT_DIR = "outputs"
MUSIC_DIR = "music"

# ── Web Dashboard ────────────────────────────────────────────────────────────
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "hymnflow-dev-secret-change-in-prod")
DASHBOARD_PORT = int(os.getenv("PORT", "5000"))

# ── Channel Branding ─────────────────────────────────────────────────────────
CHANNEL_NAME = "HymnFlow"
CHANNEL_TAGLINE = "Ancient words. Living worship."

# ── Compliance ───────────────────────────────────────────────────────────────
# Hymns written before this year are safely public domain
PUBLIC_DOMAIN_CUTOFF_YEAR = 1928
