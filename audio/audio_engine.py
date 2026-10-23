"""
HymnFlow -- Audio Engine (Sprint 3)
Converts approved hymn lyrics to speech using edge-tts (Microsoft Neural voices).
Mixes the voice with a worship instrumental from the /music folder.
Output: a single mixed .mp3 file ready for the video engine.
"""

import asyncio
import json
import logging
import os
import random
import sys

import edge_tts
from pydub import AudioSegment

from config import (
    TTS_VOICE_NAME,
    TTS_SPEAKING_RATE,
    TTS_PITCH,
    MUSIC_DIR,
    OUTPUT_DIR,
)

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_random_instrumental() -> str | None:
    """Pick a random .mp3 from the /music folder."""
    if not os.path.exists(MUSIC_DIR):
        logger.warning(f"Music folder not found: {MUSIC_DIR}")
        return None

    tracks = [
        f for f in os.listdir(MUSIC_DIR)
        if f.lower().endswith(".mp3")
    ]
    if not tracks:
        logger.warning("No .mp3 files found in /music folder.")
        return None

    chosen = random.choice(tracks)
    logger.info(f"Selected instrumental: {chosen}")
    return os.path.join(MUSIC_DIR, chosen)


def flatten_lyrics_ssml(lyrics_raw) -> str:
    """
    Build INNER SSML content only — NO <speak>, <voice>, or <prosody> wrappers.

    edge-tts wraps whatever text you give it inside:
        <speak><voice name=...><prosody rate=... pitch=...>YOUR TEXT</prosody></voice></speak>

    So we must only provide inner markup (<s> and <break> tags).
    Passing a full <speak> block causes double-wrapping and every XML tag
    gets read out loud as plain text — the bug this function fixes.
    """
    if isinstance(lyrics_raw, str):
        try:
            lyrics_raw = json.loads(lyrics_raw)
        except Exception:
            lyrics_raw = []

    parts = []
    for stanza in lyrics_raw:
        label = stanza.get("label", "")
        lines = stanza.get("lines", [])

        if label:
            safe_label = (label.replace("&", "and")
                               .replace("<", "").replace(">", "").strip())
            # Brief pause after label announcement
            parts.append(f'<s>{safe_label}</s><break time="500ms"/>')

        for line in lines:
            if line.strip():
                safe_line = (line.strip()
                                 .replace("&", "and")
                                 .replace("<", "").replace(">", ""))
                # 900ms pause after every lyric line — measured, reverent phrasing
                parts.append(f'<s>{safe_line}</s><break time="900ms"/>')

        # Longer breath between stanzas
        parts.append('<break time="1400ms"/>')

    return "\n".join(parts)


def flatten_lyrics(lyrics_raw) -> str:
    """Plain-text fallback (used only if SSML fails)."""
    if isinstance(lyrics_raw, str):
        try:
            lyrics_raw = json.loads(lyrics_raw)
        except Exception:
            return lyrics_raw
    parts = []
    for stanza in lyrics_raw:
        lines = stanza.get("lines", [])
        parts.append(". ".join(lines))
    return "\n\n".join(parts)


# ── Core TTS ──────────────────────────────────────────────────────────────────

async def _generate_voice_async(text: str, voice: str, output_path: str):
    """
    Async core: call edge-tts and save to file.
    text may contain inner SSML (<s>, <break>) — edge-tts wraps it
    in <speak><voice><prosody> automatically, so never pass a full <speak> block.
    """
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate="-20%",    # slower, more solemn — applied via edge-tts <prosody>
        pitch="-3Hz",   # slightly deeper — applied via edge-tts <prosody>
    )
    await communicate.save(output_path)
    logger.info(f"Voice audio saved: {output_path}")


def generate_voice(text: str, voice: str, output_path: str):
    """Sync wrapper around the async edge-tts call."""
    asyncio.run(_generate_voice_async(text, voice, output_path))


# ── Audio Mixing ──────────────────────────────────────────────────────────────

def mix_voice_with_instrumental(
    voice_path: str,
    instrumental_path: str,
    output_path: str,
    voice_volume_db: float = 0.0,      # Voice at full volume
    music_volume_db: float = -14.0,    # Music at -14dB (background level)
    fade_in_ms: int  = 3000,           # Music fades in over 3 seconds
    fade_out_ms: int = 4000,           # Music fades out over 4 seconds
    intro_silence_ms: int = 1500,      # 1.5s silence before voice starts
    outro_silence_ms: int = 3000,      # 3s of music-only at the end
):
    """
    Mix the TTS voice over a worship instrumental.
    - Music plays underneath at a soft background level
    - Voice is clear and in front
    - Music fades in at start and fades out at end
    """
    logger.info("Mixing voice with instrumental...")

    # Load audio files
    voice = AudioSegment.from_mp3(voice_path)
    music = AudioSegment.from_mp3(instrumental_path)

    # Adjust volumes
    voice = voice + voice_volume_db
    music = music + music_volume_db

    # Total duration needed = intro + voice + outro
    total_duration = intro_silence_ms + len(voice) + outro_silence_ms

    # Loop or trim the instrumental to fit the total duration
    if len(music) < total_duration:
        # Loop the music until it's long enough
        loops_needed = (total_duration // len(music)) + 2
        music = music * loops_needed
    music = music[:total_duration]

    # Apply fade in and fade out to the music
    music = music.fade_in(fade_in_ms).fade_out(fade_out_ms)

    # Create silence padding before the voice starts
    intro_pad = AudioSegment.silent(duration=intro_silence_ms)
    voice_padded = intro_pad + voice

    # Overlay voice on top of music
    # voice_padded is shorter than music, overlay handles the length difference
    mixed = music.overlay(voice_padded)

    # Export final mix
    mixed.export(output_path, format="mp3", bitrate="192k")
    logger.info(f"Mixed audio saved: {output_path} ({len(mixed)/1000:.1f}s)")

    return output_path, len(mixed)  # Return path and duration in ms


# ── Public API ────────────────────────────────────────────────────────────────

def build_audio(hymn: dict, hymn_id: str) -> dict:
    """
    Full audio pipeline for one hymn:
    1. Flatten lyrics to speakable text
    2. Generate TTS voice with edge-tts (Michelle)
    3. Pick random instrumental from /music
    4. Mix voice + music
    5. Return paths and duration

    Returns dict with: voice_path, music_path, mixed_path, duration_ms
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    voice_path  = os.path.join(OUTPUT_DIR, f"{hymn_id}_voice.mp3")
    mixed_path  = os.path.join(OUTPUT_DIR, f"{hymn_id}_audio.mp3")

    # Step 1 -- Build inner SSML content (only <s> and <break> tags)
    lyrics_raw    = hymn.get("lyrics", [])
    worship_voice = "en-US-GuyNeural"   # warm male, natural — best for reverent narration

    try:
        inner_ssml = flatten_lyrics_ssml(lyrics_raw)
    except Exception as e:
        logger.warning(f"SSML build failed ({e}), falling back to plain text")
        inner_ssml = flatten_lyrics(lyrics_raw)

    if not inner_ssml.strip():
        raise ValueError(f"Hymn {hymn_id} has no lyrics to speak.")

    logger.info(f"Inner SSML content length: {len(inner_ssml)} chars")

    # Step 2 -- Generate voice (edge-tts wraps inner_ssml in <speak><voice><prosody>)
    logger.info(f"Generating voice: {worship_voice} | rate=-20% | pitch=-3Hz")
    generate_voice(inner_ssml, worship_voice, voice_path)

    # Step 3 -- Pick instrumental
    instrumental_path = get_random_instrumental()

    if instrumental_path:
        # Step 4 -- Mix voice + music
        mixed_path, duration_ms = mix_voice_with_instrumental(
            voice_path=voice_path,
            instrumental_path=instrumental_path,
            output_path=mixed_path,
        )
        audio_path = mixed_path
    else:
        # No music available — use voice only
        logger.warning("No instrumental found — using voice only.")
        audio_path = voice_path
        voice_audio = AudioSegment.from_mp3(voice_path)
        duration_ms = len(voice_audio)

    return {
        "voice_path":       voice_path,
        "music_path":       instrumental_path,
        "audio_path":       audio_path,   # This is what the video engine uses
        "duration_ms":      duration_ms,
        "duration_seconds": duration_ms / 1000,
    }


if __name__ == "__main__":
    """Quick standalone test — uses the last hymn in Supabase."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    sys.stdout.reconfigure(encoding="utf-8")

    from dotenv import load_dotenv
    load_dotenv()

    from db.database import get_recent_hymns
    hymns = get_recent_hymns(limit=1)

    if not hymns:
        print("No hymns in database. Run test_sprint1.py first.")
        sys.exit(1)

    hymn = hymns[0]
    print(f"Building audio for: {hymn.get('title')}")

    result = build_audio(hymn, hymn["id"])

    print(f"\nAudio built successfully!")
    print(f"  Voice file : {result['voice_path']}")
    print(f"  Mixed file : {result['audio_path']}")
    print(f"  Duration   : {result['duration_seconds']:.1f} seconds")
    print(f"\nOpen {result['audio_path']} to listen to the full mixed audio.")
