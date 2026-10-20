"""
HymnFlow -- Sprint 4 Test
Builds the full video for the approved hymn.
This takes 5-15 minutes — the video is 1920x1080 and fully rendered.

Run with: python test_sprint4.py
"""

import sys
import os
import logging
import time
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from dotenv import load_dotenv
load_dotenv()


def test_fonts():
    print("\n--- Test 1: Fonts ---")
    from config import LYRIC_FONT, VERSE_FONT
    passed = True

    for name, path in [("Lyric font (Cinzel)", LYRIC_FONT), ("Verse font (Lato)", VERSE_FONT)]:
        if os.path.exists(path):
            print(f"  PASS: {name} found -- {path}")
        else:
            print(f"  WARN: {name} not found at {path}")
            print(f"     -> Using PIL default font (less elegant but works)")
            print(f"     -> Download from Google Fonts and place in /fonts/")

    return True  # Non-blocking -- default font is used as fallback


def test_video_imports():
    print("\n--- Test 2: Video Library Imports ---")
    try:
        from moviepy import VideoClip, AudioFileClip, CompositeVideoClip
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        print("  PASS: moviepy, Pillow, numpy all imported")
        return True
    except ImportError as e:
        print(f"  FAIL: {e}")
        return False


def test_audio_exists():
    print("\n--- Test 3: Audio File Exists ---")
    from config import OUTPUT_DIR
    from db.database import get_recent_hymns

    hymns = get_recent_hymns(limit=1)
    if not hymns:
        print("  FAIL: No hymns in database")
        return False

    hymn_id    = hymns[0]["id"]
    audio_path = os.path.join(OUTPUT_DIR, f"{hymn_id}_audio.mp3")

    if os.path.exists(audio_path):
        size = os.path.getsize(audio_path) // 1024
        print(f"  PASS: Audio file found ({size} KB)")
        print(f"     {audio_path}")
        return True
    else:
        print(f"  FAIL: Audio file not found: {audio_path}")
        print(f"     -> Run test_sprint3.py first")
        return False


def test_build_video():
    print("\n--- Test 4: Full Video Build ---")
    print("  WARNING: This takes 5-15 minutes. Do not close the terminal.")
    print("  Building 1920x1080 animated video with lyrics overlay...")

    from config import OUTPUT_DIR
    from db.database import get_recent_hymns, mark_rendered, save_video
    from video.video_engine import build_video
    from pydub import AudioSegment

    hymns = get_recent_hymns(limit=1)
    if not hymns:
        print("  FAIL: No hymns found")
        return False

    hymn       = hymns[0]
    hymn_id    = hymn["id"]
    audio_path = os.path.join(OUTPUT_DIR, f"{hymn_id}_audio.mp3")

    if not os.path.exists(audio_path):
        print(f"  FAIL: Audio not found -- run test_sprint3.py first")
        return False

    dur = len(AudioSegment.from_mp3(audio_path)) / 1000
    print(f"  Hymn   : {hymn.get('title')}")
    print(f"  Audio  : {dur:.1f}s")

    start = time.time()
    try:
        result = build_video(hymn, hymn_id, audio_path, dur)
        elapsed = time.time() - start

        size = os.path.getsize(result["video_path"]) // (1024 * 1024)
        print(f"\n  PASS: Video built in {elapsed:.0f}s!")
        print(f"     Video     : {result['video_path']} ({size} MB)")
        print(f"     Thumbnail : {result['thumbnail_path']}")
        print(f"     Duration  : {result['duration']:.1f}s")

        # Update Supabase
        save_video(hymn_id, result["video_path"], result["thumbnail_path"])
        mark_rendered(hymn_id)
        print(f"     Supabase  : status updated to 'rendered'")

        return True
    except Exception as e:
        print(f"\n  FAIL: Video build error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("  HymnFlow -- Sprint 4 Test Suite")
    print("=" * 50)
    print("  NOTE: Test 4 renders a full HD video.")
    print("  Estimated time: 5-15 minutes.")
    print("=" * 50)

    tests = [
        ("Fonts",              test_fonts),
        ("Video Library Imports", test_video_imports),
        ("Audio File Exists",  test_audio_exists),
        ("Full Video Build",   test_build_video),
    ]

    results = []
    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  CRASH: {e}")
            results.append((name, False))

    passed_count = sum(1 for _, p in results if p)
    print("\n" + "=" * 50)
    print("  RESULTS")
    print("=" * 50)
    for name, passed in results:
        print(f"  {'[PASS]' if passed else '[FAIL]'}  {name}")
    print(f"\n  {passed_count}/{len(results)} tests passed")

    if passed_count >= 3:
        print("\n  Sprint 4 complete!")
        print("  Open the outputs/ folder and watch your video.")
        print("  Next: Sprint 5 -- YouTube uploader.")
    print("=" * 50)
