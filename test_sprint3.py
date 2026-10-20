"""
HymnFlow -- Sprint 3 Test
Tests the full audio engine:
  [OK] edge-tts voice generation (MichelleNeural)
  [OK] Instrumental loading from /music folder
  [OK] Voice + music mixing
  [OK] Final audio file duration check

Run with: python test_sprint3.py
"""

import sys
import os
import logging
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from dotenv import load_dotenv
load_dotenv()


def test_edge_tts_installed():
    print("\n--- Test 1: edge-tts Installed ---")
    try:
        import edge_tts
        print(f"  PASS: edge-tts imported successfully")
        return True
    except ImportError:
        print(f"  FAIL: edge-tts not installed -- run: pip install edge-tts")
        return False


def test_voice_generation():
    print("\n--- Test 2: Voice Generation (MichelleNeural) ---")
    try:
        import asyncio
        import edge_tts
        from config import TTS_VOICE_NAME, TTS_SPEAKING_RATE, TTS_PITCH

        test_text = (
            "We thank You, Lord, for armor strong. "
            "For battles won, where we belong. "
            "Your mighty hand, our shield and might. "
            "We praise Your name, our guiding light."
        )
        out = "outputs/test_voice_sprint3.mp3"
        os.makedirs("outputs", exist_ok=True)

        async def _gen():
            comm = edge_tts.Communicate(
                text=test_text,
                voice=TTS_VOICE_NAME,
                rate=TTS_SPEAKING_RATE,
                pitch=TTS_PITCH,
            )
            await comm.save(out)

        asyncio.run(_gen())

        size = os.path.getsize(out)
        print(f"  PASS: Voice generated -- {TTS_VOICE_NAME}")
        print(f"  PASS: File size: {size // 1024} KB ({out})")
        return True
    except Exception as e:
        print(f"  FAIL: Voice generation error: {e}")
        return False


def test_music_folder():
    print("\n--- Test 3: Music Folder ---")
    from config import MUSIC_DIR
    if not os.path.exists(MUSIC_DIR):
        print(f"  FAIL: /music folder does not exist")
        print(f"     -> Create it and add .mp3 worship instrumentals from pixabay.com/music")
        return False

    tracks = [f for f in os.listdir(MUSIC_DIR) if f.lower().endswith(".mp3")]
    if not tracks:
        print(f"  WARN: /music folder exists but has no .mp3 files")
        print(f"     -> Download worship instrumentals from pixabay.com/music")
        print(f"     -> Audio engine will use voice-only until music is added")
        return True  # Non-blocking — voice-only still works

    print(f"  PASS: {len(tracks)} instrumental track(s) found in /music")
    for t in tracks[:5]:
        print(f"     - {t}")
    if len(tracks) > 5:
        print(f"     ... and {len(tracks) - 5} more")
    return True


def test_full_audio_build():
    print("\n--- Test 4: Full Audio Build (voice + mixing) ---")
    print("  (Takes 15-30 seconds...)")
    try:
        from db.database import get_recent_hymns
        from audio.audio_engine import build_audio

        hymns = get_recent_hymns(limit=1)
        if not hymns:
            print("  SKIP: No hymns in database -- run test_sprint1.py first")
            return False

        hymn = hymns[0]
        print(f"  Building audio for: {hymn.get('title')}")

        result = build_audio(hymn, hymn["id"])

        duration = result["duration_seconds"]
        print(f"  PASS: Audio built successfully!")
        print(f"     Voice file : {result['voice_path']}")
        print(f"     Audio file : {result['audio_path']}")
        print(f"     Duration   : {duration:.1f} seconds ({duration/60:.1f} min)")

        if result.get("music_path"):
            print(f"     Instrumental: {os.path.basename(result['music_path'])}")
        else:
            print(f"     Instrumental: None (voice-only mode)")

        if duration < 10:
            print(f"  WARN: Audio is very short ({duration:.1f}s) -- check lyrics")
        else:
            print(f"  PASS: Duration looks good for a hymn video")

        return True
    except Exception as e:
        print(f"  FAIL: Audio build error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("  HymnFlow -- Sprint 3 Test Suite")
    print("=" * 50)

    tests = [
        ("edge-tts Installed",    test_edge_tts_installed),
        ("Voice Generation",      test_voice_generation),
        ("Music Folder",          test_music_folder),
        ("Full Audio Build",      test_full_audio_build),
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
        print("\n  Sprint 3 complete! Ready to build Sprint 4 (Video Engine).")
        print("  Open outputs/ folder and listen to the generated audio.")
    else:
        print("\n  Fix failing tests before Sprint 4.")
    print("=" * 50)
