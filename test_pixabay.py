"""
HymnFlow — Pixabay Video Download Test
Tests that the Pixabay API key works and that we can download
a nature/worship background video successfully.

Run with: python test_pixabay.py
"""

import os
import sys
import logging
sys.stdout.reconfigure(encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

from dotenv import load_dotenv
load_dotenv()


def test_api_key_loaded():
    print("\n--- Test 1: Pixabay API Key ---")
    key = os.getenv("PIXABAY_API_KEY", "").strip()
    if not key or key == "your_pixabay_api_key_here":
        print("  FAIL: PIXABAY_API_KEY is not set in .env")
        return False
    # Only show first 8 chars for safety
    print(f"  PASS: Key loaded — {key[:8]}...{key[-4:]}")
    return True


def test_pixabay_api_search():
    print("\n--- Test 2: Pixabay API Search ---")
    import requests
    key = os.getenv("PIXABAY_API_KEY", "").strip()
    keyword = "sunrise worship nature"

    url = (
        f"https://pixabay.com/api/videos/"
        f"?key={key}"
        f"&q={requests.utils.quote(keyword)}"
        f"&video_type=film"
        f"&category=nature"
        f"&min_duration=30"
        f"&per_page=5"
        f"&safesearch=true"
    )

    try:
        print(f"  Searching for: '{keyword}'")
        resp = requests.get(url, timeout=20)

        if resp.status_code != 200:
            print(f"  FAIL: HTTP {resp.status_code}")
            print(f"  Response: {resp.text[:300]}")
            return False

        data = resp.json()
        total = data.get("totalHits", 0)
        hits  = data.get("hits", [])

        print(f"  PASS: API responded — {total} total hits, {len(hits)} returned")
        for i, hit in enumerate(hits[:3]):
            vid   = hit.get("videos", {})
            med   = vid.get("medium", {})
            dur   = hit.get("duration", "?")
            vurl  = med.get("url", "N/A")[:60]
            print(f"    [{i+1}] duration={dur}s  url={vurl}...")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        return False


def test_download_one_video():
    print("\n--- Test 3: Download a Real Video ---")
    import requests

    key     = os.getenv("PIXABAY_API_KEY", "").strip()
    keyword = "sunrise nature worship light"
    out_dir = "outputs"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "pixabay_test_download.mp4")

    url = (
        f"https://pixabay.com/api/videos/"
        f"?key={key}"
        f"&q={requests.utils.quote(keyword)}"
        f"&video_type=film"
        f"&category=nature"
        f"&min_duration=30"
        f"&per_page=5"
        f"&safesearch=true"
    )

    try:
        resp  = requests.get(url, timeout=20)
        data  = resp.json()
        hits  = data.get("hits", [])

        if not hits:
            print(f"  FAIL: No videos returned for '{keyword}'")
            return False

        # Pick first usable video
        video_url = None
        for hit in hits:
            videos    = hit.get("videos", {})
            video_url = (
                videos.get("medium", {}).get("url") or
                videos.get("large",  {}).get("url") or
                videos.get("small",  {}).get("url")
            )
            if video_url:
                dur = hit.get("duration", "?")
                print(f"  Found video: duration={dur}s")
                print(f"  URL: {video_url[:70]}...")
                break

        if not video_url:
            print("  FAIL: No usable video URL found in results")
            return False

        print(f"  Downloading to: {out_path}")
        print("  (This may take 10–30 seconds...)")
        video_data = requests.get(video_url, timeout=120)
        with open(out_path, "wb") as f:
            f.write(video_data.content)

        size_kb = os.path.getsize(out_path) // 1024
        print(f"  PASS: Downloaded! File size: {size_kb:,} KB")
        print(f"  Saved to: {out_path}")
        return True

    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_background_fetcher_module():
    print("\n--- Test 4: Background Fetcher Module ---")
    from video.background_fetcher import get_keyword, download_pixabay_video
    import os

    key = os.getenv("PIXABAY_API_KEY", "").strip()

    # Test keyword picker
    kw = get_keyword("Praise", "Worship")
    print(f"  Keyword for 'Praise' theme: '{kw}'")

    # Test download via the module
    print("  Calling download_pixabay_video(...)...")
    path = download_pixabay_video(kw, "module_test", key)

    if path and os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f"  PASS: Module download succeeded — {size_kb:,} KB at {path}")
        return True
    else:
        print("  FAIL: Module returned None or file not found")
        return False


if __name__ == "__main__":
    print("=" * 55)
    print("  HymnFlow — Pixabay Video Download Test")
    print("=" * 55)

    tests = [
        ("API Key Loaded",             test_api_key_loaded),
        ("Pixabay API Search",         test_pixabay_api_search),
        ("Download a Real Video",      test_download_one_video),
        ("Background Fetcher Module",  test_background_fetcher_module),
    ]

    results = []
    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
            if not passed:
                print(f"\n  ⚠️  '{name}' failed — continuing to next test.\n")
        except Exception as e:
            print(f"  CRASH in '{name}': {e}")
            results.append((name, False))

    passed_count = sum(1 for _, p in results if p)
    print("\n" + "=" * 55)
    print("  RESULTS")
    print("=" * 55)
    for name, passed in results:
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}]  {name}")

    print(f"\n  {passed_count}/{len(results)} tests passed")

    if passed_count == 4:
        print("\n  ✅ Pixabay is fully working!")
        print("  Your outputs/ folder now has a sample background video.")
        print("  Next step: run test_sprint4.py to build the full video.")
    elif passed_count >= 2:
        print("\n  ⚠️  API works but download had issues. Check outputs/.")
    else:
        print("\n  ❌ API key or network issue. Double-check .env.")
    print("=" * 55)
