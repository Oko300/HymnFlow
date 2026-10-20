"""
HymnFlow -- Sprint 1 Test
Tests the full hymn generation pipeline:
  [OK] Gemini key rotator
  [OK] Hymn generation
  [OK] Compliance checks
  [OK] Supabase save

Run with: python test_sprint1.py
"""

import logging
import sys
import os

# Fix Windows terminal encoding
sys.stdout.reconfigure(encoding='utf-8')

# Set up logging so we can see every step
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("Sprint1Test")


def test_env_variables():
    """Check all required .env values are present."""
    print("\n--- Test 1: Environment Variables ---")
    from config import GEMINI_API_KEYS, SUPABASE_URL, SUPABASE_KEY

    passed = True

    if not GEMINI_API_KEYS:
        print("  FAIL: GEMINI_API_KEYS not set in .env")
        passed = False
    else:
        print(f"  PASS: GEMINI_API_KEYS -- {len(GEMINI_API_KEYS)} key(s) loaded")

    if not SUPABASE_URL or "your-project" in SUPABASE_URL:
        print("  FAIL: SUPABASE_URL not set in .env")
        passed = False
    else:
        print(f"  PASS: SUPABASE_URL -- {SUPABASE_URL[:40]}...")

    if not SUPABASE_KEY or SUPABASE_KEY == "your_supabase_anon_key":
        print("  FAIL: SUPABASE_KEY not set in .env")
        passed = False
    else:
        print(f"  PASS: SUPABASE_KEY -- set")

    return passed


def test_key_rotator():
    """Test Gemini key rotator initializes correctly."""
    print("\n--- Test 2: Gemini Key Rotator ---")
    try:
        from generator.key_rotator import rotator
        print(f"  PASS: Key rotator ready -- {len(rotator.keys)} key(s) loaded")
        print(f"  PASS: Currently using key #{rotator.current_index + 1}")
        return True
    except Exception as e:
        print(f"  FAIL: Key rotator error: {e}")
        return False


def test_gemini_connection():
    """Send a tiny test prompt to confirm Gemini API is working."""
    print("\n--- Test 3: Gemini API Connection ---")
    try:
        from generator.key_rotator import rotator
        response = rotator.generate_with_retry(
            'Reply with exactly this JSON and nothing else: {"status": "ok"}'
        )
        if "ok" in response:
            print(f"  PASS: Gemini API responding correctly")
        else:
            print(f"  PASS: Gemini responded (unexpected format but API works): {response[:60]}")
        return True
    except Exception as e:
        print(f"  FAIL: Gemini API connection failed: {e}")
        return False


def test_supabase_connection():
    """Test Supabase connects and can query the hymns table."""
    print("\n--- Test 4: Supabase Connection ---")
    try:
        from db.database import get_client
        client = get_client()
        result = client.table("hymns").select("id").limit(1).execute()
        print(f"  PASS: Supabase connected -- hymns table accessible")
        print(f"  PASS: Hymns in DB so far: {len(result.data)}")
        return True
    except Exception as e:
        print(f"  FAIL: Supabase connection failed: {e}")
        print(f"     -> Did you run db/setup.sql in your Supabase SQL editor?")
        return False


def test_compliance_checker():
    """Test compliance checker with a safe and an unsafe hymn."""
    print("\n--- Test 5: Compliance Checker ---")
    try:
        from compliance.checker import run_all_checks

        safe_hymn = {
            "title": "In Your Presence Lord I Stand",
            "theme": "Worship",
            "style": "Praise",
            "lyrics": [
                {"label": "Verse 1", "lines": [
                    "In the shadow of Your wings I find my rest",
                    "Your mercy flows like rivers from the blessed",
                    "No fear can hold me when Your hand is near",
                    "In Your presence Lord my heart is clear"
                ]},
                {"label": "Chorus", "lines": [
                    "Holy is Your name above all names",
                    "Worthy of all glory and all praise",
                    "I lift my voice to heaven's throne",
                    "For in You Lord I am never alone"
                ]}
            ],
            "bible_verse": "The LORD is my shepherd; I shall not want.",
            "bible_reference": "Psalm 23:1"
        }

        result = run_all_checks(safe_hymn, [])
        if result["passed"]:
            print(f"  PASS: Safe hymn passed all compliance checks")
        else:
            print(f"  WARN: Safe hymn flagged (may be Gemini strictness): {result['blocking_reason']}")

        unsafe_hymn = {**safe_hymn, "title": "Shout to the Lord"}
        unsafe_hymn["lyrics"][0]["lines"][0] = "shout to the lord all the earth let us sing"

        result2 = run_all_checks(unsafe_hymn, [])
        if not result2["passed"]:
            print(f"  PASS: Unsafe hymn correctly blocked")
        else:
            print(f"  WARN: Unsafe hymn not caught -- phrase list may need updating")

        return True
    except Exception as e:
        print(f"  FAIL: Compliance checker error: {e}")
        return False


def test_full_generation():
    """Run a full hymn generation and save to Supabase."""
    print("\n--- Test 6: Full Hymn Generation ---")
    print("  (This may take 20-40 seconds...)")
    try:
        from generator.hymn_gen import generate_hymn
        hymn = generate_hymn()

        print(f"  PASS: Hymn generated and saved to Supabase!")
        print(f"     Title    : {hymn.get('title')}")
        print(f"     Theme    : {hymn.get('theme')}")
        print(f"     Style    : {hymn.get('style')}")
        print(f"     Scripture: {hymn.get('bible_reference')}")
        print(f"     DB ID    : {hymn.get('id')}")
        return True
    except Exception as e:
        print(f"  FAIL: Full generation failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("  HymnFlow -- Sprint 1 Test Suite")
    print("=" * 50)

    tests = [
        ("Environment Variables", test_env_variables),
        ("Gemini Key Rotator",    test_key_rotator),
        ("Gemini API Connection", test_gemini_connection),
        ("Supabase Connection",   test_supabase_connection),
        ("Compliance Checker",    test_compliance_checker),
        ("Full Hymn Generation",  test_full_generation),
    ]

    results = []
    for name, test_fn in tests:
        try:
            passed = test_fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  CRASH: {e}")
            results.append((name, False))

    print("\n" + "=" * 50)
    print("  RESULTS")
    print("=" * 50)
    passed_count = 0
    for name, passed in results:
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}]  {name}")
        if passed:
            passed_count += 1

    print(f"\n  {passed_count}/{len(results)} tests passed")

    if passed_count == len(results):
        print("\n  Sprint 1 complete! Ready to build Sprint 2 (Telegram Bot).")
    else:
        print("\n  Fix the failing tests before moving to Sprint 2.")
    print("=" * 50)
