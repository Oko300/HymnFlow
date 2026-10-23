"""
HymnFlow -- Video Engine v2 (Nature Background Edition)
Builds the hymn video using:
  - Real nature footage from Pixabay/Pexels as background
  - Worship music track underneath (human vocal, from /music folder)
  - Lyrics displayed line by line with fade transitions
  - Bible verse pinned at the bottom
  - Channel watermark top-left
  - Intro title card (3s) and outro card (4s)
Output: MP4 ready for Telegram preview and YouTube upload
"""

import json
import logging
import os
import sys
import subprocess
import random
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip,
    AudioFileClip,
    VideoClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
    concatenate_audioclips,
    ColorClip,
)

from config import (
    VIDEO_WIDTH, VIDEO_HEIGHT, VIDEO_FPS,
    LYRIC_FONT, VERSE_FONT,
    OUTPUT_DIR, MUSIC_DIR,
    CHANNEL_NAME, CHANNEL_TAGLINE,
)

logger = logging.getLogger(__name__)

W = VIDEO_WIDTH    # 1920
H = VIDEO_HEIGHT   # 1080


# ── Font loader ───────────────────────────────────────────────────────────────
# System font fallbacks for GitHub Actions Ubuntu runner
_SYSTEM_SERIF_FONTS = [
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
]
_SYSTEM_SANS_FONTS = [
    "/usr/share/fonts/truetype/open-sans/OpenSans-Italic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-RI.ttf",
]

def load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    # 1. Try the requested path (custom font)
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    # 2. Try system fonts (Ubuntu GitHub Actions runner)
    fallbacks = _SYSTEM_SERIF_FONTS if "Cinzel" in path or "Serif" in path else _SYSTEM_SANS_FONTS
    for fb in fallbacks:
        if os.path.exists(fb):
            try:
                return ImageFont.truetype(fb, size)
            except Exception:
                continue
    # 3. Last resort: PIL default (tiny, but never crashes)
    logger.warning(f"Font not found: {path} -- using PIL default")
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


# ── Text helpers ──────────────────────────────────────────────────────────────
def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list:
    words   = text.split()
    lines   = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def draw_text_centered(draw, text, font, y, width, color, shadow_color=(0, 0, 0, 180)):
    """Draw centered text with drop shadow."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    x    = (width - tw) // 2
    # Shadow
    draw.text((x + 2, y + 2), text, font=font, fill=shadow_color)
    draw.text((x,     y),     text, font=font, fill=color)


# ── Single overlay frame builder ──────────────────────────────────────────────
def make_overlay_image(
    line: str,
    label: str,
    bible_verse: str,
    bible_ref: str,
    width: int,
    height: int,
    lyric_font,
    label_font,
    verse_font,
    channel_font,
    alpha: float = 1.0,
) -> np.ndarray:
    """
    Returns an RGBA numpy image with:
    - Semi-transparent dark band behind lyrics (center)
    - Lyric line centered
    - Stanza label above (small)
    - Bible verse strip at the bottom
    - Channel name watermark top-left
    """
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    a    = int(255 * max(0.0, min(1.0, alpha)))

    # ── Center dark band ──────────────────────────────────────────────────────
    band_h   = 220
    band_top = (height - band_h) // 2 - 20
    band     = Image.new("RGBA", (width, band_h), (0, 0, 0, int(165 * alpha)))
    img.paste(band, (0, band_top), band)

    # ── Stanza label ──────────────────────────────────────────────────────────
    if label:
        draw.text(
            (width // 2, band_top + 14),
            label.upper(),
            font=label_font,
            fill=(200, 200, 200, a),
            anchor="mt",
        )

    # ── Main lyric line (wrapped) ─────────────────────────────────────────────
    max_w   = int(width * 0.82)
    wrapped = wrap_text(line, lyric_font, max_w, draw)
    lh      = lyric_font.size + 10
    total_h = len(wrapped) * lh
    text_y  = band_top + (band_h - total_h) // 2 + 10

    for i, wl in enumerate(wrapped):
        bbox = draw.textbbox((0, 0), wl, font=lyric_font)
        tw   = bbox[2] - bbox[0]
        x    = (width - tw) // 2
        # Shadow
        draw.text((x + 2, text_y + i * lh + 2), wl, font=lyric_font,
                  fill=(0, 0, 0, int(160 * alpha)))
        draw.text((x,     text_y + i * lh),      wl, font=lyric_font,
                  fill=(255, 255, 255, a))

    # ── Bible verse strip at bottom ───────────────────────────────────────────
    strip_h   = 90
    strip_top = height - strip_h - 10
    strip     = Image.new("RGBA", (width, strip_h), (0, 0, 0, int(140 * alpha)))
    img.paste(strip, (0, strip_top), strip)

    # Truncate verse text if too long
    verse_text = f'"{bible_verse}"'
    if len(verse_text) > 100:
        verse_text = verse_text[:97] + '..."'

    draw.text(
        (width // 2, strip_top + 12),
        verse_text,
        font=verse_font,
        fill=(230, 210, 160, a),
        anchor="mt",
    )
    draw.text(
        (width // 2, strip_top + 52),
        f"— {bible_ref}",
        font=verse_font,
        fill=(190, 170, 120, a),
        anchor="mt",
    )

    # ── Channel watermark ─────────────────────────────────────────────────────
    draw.text((20, 20), CHANNEL_NAME, font=channel_font,
              fill=(255, 255, 255, int(130 * alpha)))

    return np.array(img)


# ── Title card ────────────────────────────────────────────────────────────────
def make_title_card(title, style, width, height, title_font, sub_font, chan_font, duration=3.0):
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 200))
    draw = ImageDraw.Draw(img)
    draw_text_centered(draw, CHANNEL_NAME,    chan_font,  height // 2 - 90, width, (210, 185, 100, 255))
    draw_text_centered(draw, title,           title_font, height // 2 - 20, width, (255, 255, 255, 255))
    draw_text_centered(draw, CHANNEL_TAGLINE, sub_font,   height // 2 + 65, width, (180, 180, 180, 255))
    arr = np.array(img)[:, :, :3]
    return ImageClip(arr, duration=duration)


# ── Outro card ────────────────────────────────────────────────────────────────
def make_outro_card(width, height, sub_font, chan_font, duration=4.0):
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 190))
    draw = ImageDraw.Draw(img)
    draw_text_centered(draw, CHANNEL_NAME,                  chan_font, height // 2 - 55, width, (210, 185, 100, 255))
    draw_text_centered(draw, "Subscribe for more hymns",    sub_font,  height // 2 + 10, width, (255, 255, 255, 255))
    draw_text_centered(draw, "Like & share to bless others", sub_font, height // 2 + 60, width, (180, 180, 180, 255))
    arr = np.array(img)[:, :, :3]
    return ImageClip(arr, duration=duration)


# ── Pick music track ──────────────────────────────────────────────────────────
def get_music_track() -> str | None:
    if not os.path.exists(MUSIC_DIR):
        return None
    tracks = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(".mp3")]
    if not tracks:
        return None
    return os.path.join(MUSIC_DIR, random.choice(tracks))


# ── Main video builder ────────────────────────────────────────────────────────
def build_video(hymn: dict, hymn_id: str, bg_video_path: str | None = None, audio_path: str | None = None) -> dict:
    """
    Build the complete hymn video.
    bg_video_path: path to downloaded nature footage (or None for colour bg)
    Returns: {video_path, thumbnail_path, duration}
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    title       = hymn.get("title", "Hymn")
    style       = hymn.get("style", "Worship")
    bible_verse = hymn.get("bible_verse", "")
    bible_ref   = hymn.get("bible_reference", "")
    lyrics_raw  = hymn.get("lyrics", [])

    if isinstance(lyrics_raw, str):
        try:
            lyrics_raw = json.loads(lyrics_raw)
        except Exception:
            lyrics_raw = []

    # Flatten lyrics to list of (label, line)
    lyric_lines = []
    for stanza in lyrics_raw:
        label = stanza.get("label", "")
        for line in stanza.get("lines", []):
            if line.strip():
                lyric_lines.append((label, line.strip()))

    if not lyric_lines:
        raise ValueError("No lyric lines found")

    logger.info(f"Building video: {len(lyric_lines)} lines, style={style}")

    # ── Fonts ──────────────────────────────────────────────────────────────────
    lyric_font   = load_font(LYRIC_FONT,  72)   # was 54 — bigger for readability
    label_font   = load_font(LYRIC_FONT,  32)
    verse_font   = load_font(VERSE_FONT,  28)
    channel_font = load_font(VERSE_FONT,  24)
    title_font   = load_font(LYRIC_FONT,  72)
    sub_font     = load_font(VERSE_FONT,  36)

    # ── Timing ─────────────────────────────────────────────────────────────────
    INTRO_DUR     = 3.0
    OUTRO_DUR     = 4.0
    SECS_PER_LINE = 4.5          # Each lyric line shows for 4.5 seconds
    FADE          = 0.4
    lyric_dur     = len(lyric_lines) * SECS_PER_LINE
    total_dur     = INTRO_DUR + lyric_dur + OUTRO_DUR

    logger.info(f"Total duration: {total_dur:.1f}s ({total_dur/60:.1f} min)")

    # ── Background ─────────────────────────────────────────────────────────────
    if bg_video_path and os.path.exists(bg_video_path):
        logger.info(f"Using nature footage: {bg_video_path}")
        bg_clip = VideoFileClip(bg_video_path).resized((W, H))
        # Loop if shorter than needed
        if bg_clip.duration < total_dur:
            loops = int(total_dur / bg_clip.duration) + 2
            bg_clip = concatenate_videoclips([bg_clip] * loops)
        bg_clip = bg_clip.subclipped(0, total_dur)
    else:
        logger.warning("No nature footage -- using dark colour background")
        bg_clip = ColorClip(size=(W, H), color=(20, 25, 50), duration=total_dur)

    bg_clip = bg_clip.with_fps(VIDEO_FPS)

    # ── Overlay VideoClip (lyrics + bible verse) ───────────────────────────────
    def make_overlay_frame(t):
        if t < INTRO_DUR or t >= INTRO_DUR + lyric_dur:
            # No overlay during intro/outro — those are handled separately
            return np.zeros((H, W, 3), dtype=np.uint8)

        lt       = t - INTRO_DUR
        idx      = min(int(lt / SECS_PER_LINE), len(lyric_lines) - 1)
        label, line = lyric_lines[idx]

        line_t = lt - idx * SECS_PER_LINE
        if line_t < FADE:
            a = line_t / FADE
        elif line_t > SECS_PER_LINE - FADE:
            a = max(0.0, (SECS_PER_LINE - line_t) / FADE)
        else:
            a = 1.0

        rgba = make_overlay_image(
            line=line, label=label,
            bible_verse=bible_verse, bible_ref=bible_ref,
            width=W, height=H,
            lyric_font=lyric_font, label_font=label_font,
            verse_font=verse_font, channel_font=channel_font,
            alpha=a,
        )
        # Blend RGBA overlay onto black frame
        rgb   = rgba[:, :, :3].astype(float)
        alpha = rgba[:, :, 3:4].astype(float) / 255.0
        out   = (rgb * alpha).astype(np.uint8)
        return out

    overlay_clip = VideoClip(make_overlay_frame, duration=total_dur).with_fps(VIDEO_FPS)

    # ── Composite background + overlay ────────────────────────────────────────
    main_clip = CompositeVideoClip([bg_clip, overlay_clip], size=(W, H))

    # ── Title card and outro ──────────────────────────────────────────────────
    title_card = make_title_card(title, style, W, H, title_font, sub_font, channel_font, INTRO_DUR)
    outro_card = make_outro_card(W, H, sub_font, channel_font, OUTRO_DUR)

    # Composite title/outro over the background
    title_bg = bg_clip.subclipped(0, INTRO_DUR)
    outro_bg = bg_clip.subclipped(total_dur - OUTRO_DUR, total_dur)

    title_composite = CompositeVideoClip([title_bg, title_card], size=(W, H))
    outro_composite = CompositeVideoClip([outro_bg, outro_card], size=(W, H))
    lyric_section   = main_clip.subclipped(INTRO_DUR, INTRO_DUR + lyric_dur)

    final = concatenate_videoclips([title_composite, lyric_section, outro_composite])

    # ── Audio (TTS voice + music from audio engine, or fallback music-only) ───
    if audio_path and os.path.exists(audio_path):
        logger.info(f"Attaching audio: {os.path.basename(audio_path)}")
        audio_clip = AudioFileClip(audio_path)
        # If audio is longer than video, trim it
        if audio_clip.duration > final.duration:
            audio_clip = audio_clip.subclipped(0, final.duration)
        # Fade out last 3 seconds (MoviePy 2.x renamed the method)
        try:
            from moviepy.audio.fx import AudioFadeOut
            audio_clip = audio_clip.with_effects([AudioFadeOut(3.0)])
        except Exception:
            pass  # Fadeout is cosmetic — skip if API unavailable
        final = final.with_audio(audio_clip)
        logger.info(f"Audio attached ({audio_clip.duration:.1f}s)")
    else:
        # Fallback: try a raw music track from /music folder
        music_path = get_music_track()
        if music_path:
            logger.info(f"Fallback: adding music track {os.path.basename(music_path)}")
            music = AudioFileClip(music_path)
            if music.duration < final.duration:
                loops = int(final.duration / music.duration) + 2
                music = concatenate_audioclips([music] * loops)
            music = music.subclipped(0, final.duration)
            try:
                from moviepy.audio.fx import AudioFadeOut
                music = music.with_effects([AudioFadeOut(3.0)])
            except Exception:
                pass
            final = final.with_audio(music)
        else:
            logger.warning("No audio available -- video will be silent")

    # ── Render ────────────────────────────────────────────────────────────────
    video_path = os.path.join(OUTPUT_DIR, f"{hymn_id}.mp4")
    logger.info(f"Rendering to {video_path}...")
    final.write_videofile(
        video_path,
        fps=VIDEO_FPS,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=os.path.join(OUTPUT_DIR, f"{hymn_id}_tmp.m4a"),
        remove_temp=True,
        preset="fast",        # Faster render, slightly larger file
        threads=4,
        logger=None,
    )
    logger.info(f"Video saved: {video_path}")

    # ── Thumbnail ─────────────────────────────────────────────────────────────
    thumb_path  = os.path.join(OUTPUT_DIR, f"{hymn_id}_thumb.jpg")
    thumb_frame = final.get_frame(INTRO_DUR + 3.0)
    thumb_img   = Image.fromarray(thumb_frame)

    # Add title text on thumbnail
    td = ImageDraw.Draw(thumb_img)
    draw_text_centered(td, title,        title_font,   H // 2 - 40, W, (255, 255, 255, 255))
    draw_text_centered(td, CHANNEL_NAME, channel_font, H // 2 + 40, W, (210, 185, 100, 255))
    thumb_img.save(thumb_path, "JPEG", quality=92)
    logger.info(f"Thumbnail saved: {thumb_path}")

    return {
        "video_path":     video_path,
        "thumbnail_path": thumb_path,
        "duration":       final.duration,
    }
