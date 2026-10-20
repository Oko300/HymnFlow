"""
HymnFlow -- Hymn Generator (Sprint 1 Core)
Uses Gemini API structured output (response_schema) to guarantee
valid JSON every time -- no more truncation or parse failures.
"""

import json
import logging
import random
from datetime import datetime, timezone

from google.genai import types
from generator.key_rotator import rotator
from compliance.checker import run_all_checks
from db.database import save_hymn, get_recent_themes

logger = logging.getLogger(__name__)


# ── Theme Calendar ────────────────────────────────────────────────────────────
THEME_CALENDAR = {
    1:  ["New Beginnings", "God's Faithfulness", "Hope in the New Year"],
    2:  ["God's Love", "Redemption", "Faithfulness"],
    3:  ["Lent", "Repentance", "God's Mercy", "Cross of Christ"],
    4:  ["Easter", "Resurrection", "Victory over Death", "New Life"],
    5:  ["Holy Spirit", "Pentecost", "God's Power", "Praise"],
    6:  ["God's Creation", "Gratitude", "Worship"],
    7:  ["Freedom in Christ", "God's Sovereignty", "Trust"],
    8:  ["God's Word", "Spiritual Strength", "Perseverance"],
    9:  ["Harvest", "God's Provision", "Thanksgiving"],
    10: ["God's Protection", "Spiritual Warfare", "Faith"],
    11: ["Thanksgiving", "God's Blessings", "Gratitude"],
    12: ["Advent", "Christmas", "Birth of Christ", "Emmanuel"],
}

HYMN_STYLES = ["Praise", "Worship", "Lament", "Thanksgiving", "Intercession"]

HYMN_LENGTHS = [
    {"label": "standard", "verses": 3, "has_bridge": False},
    {"label": "extended", "verses": 4, "has_bridge": True},
    {"label": "short",    "verses": 2, "has_bridge": False},
]


# ── Structured Output Schema ──────────────────────────────────────────────────
# Gemini uses this schema to guarantee valid JSON -- no truncation possible
STANZA_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "label": types.Schema(type=types.Type.STRING),
        "lines": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
        ),
    },
    required=["label", "lines"],
)

HYMN_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "title":           types.Schema(type=types.Type.STRING),
        "theme":           types.Schema(type=types.Type.STRING),
        "style":           types.Schema(type=types.Type.STRING),
        "lyrics":          types.Schema(
                               type=types.Type.ARRAY,
                               items=STANZA_SCHEMA,
                           ),
        "bible_verse":     types.Schema(type=types.Type.STRING),
        "bible_reference": types.Schema(type=types.Type.STRING),
        "seo_titles":      types.Schema(
                               type=types.Type.ARRAY,
                               items=types.Schema(type=types.Type.STRING),
                           ),
        "seo_description": types.Schema(type=types.Type.STRING),
        "seo_tags":        types.Schema(
                               type=types.Type.ARRAY,
                               items=types.Schema(type=types.Type.STRING),
                           ),
    },
    required=[
        "title", "theme", "style", "lyrics",
        "bible_verse", "bible_reference",
        "seo_titles", "seo_description", "seo_tags",
    ],
)


def get_theme_for_today(recent_hymns: list) -> tuple:
    month = datetime.now(timezone.utc).month
    available_themes = THEME_CALENDAR.get(month, ["God's Love", "Praise", "Worship"])

    recent_theme_names = {h.get("theme", "").lower() for h in recent_hymns}
    recent_style_names = {h.get("style", "").lower() for h in recent_hymns[:5]}

    fresh_themes = [t for t in available_themes if t.lower() not in recent_theme_names]
    if not fresh_themes:
        fresh_themes = available_themes

    fresh_styles = [s for s in HYMN_STYLES if s.lower() not in recent_style_names]
    if not fresh_styles:
        fresh_styles = HYMN_STYLES

    return random.choice(fresh_themes), random.choice(fresh_styles)


def build_hymn_prompt(theme: str, style: str, length: dict) -> str:
    verse_count = length["verses"]
    has_bridge  = length["has_bridge"]

    structure = f"{verse_count} verses (4 lines each), a chorus (4 lines) repeated after each verse"
    if has_bridge:
        structure += ", and a bridge (4 lines) before the final chorus"

    return f"""Write an original Christian hymn with these specifications:

Theme: {theme}
Style: {style}
Structure: {structure}

Rules:
1. ALL lyrics must be 100% original -- do NOT copy any existing hymn
2. Language should be reverent, poetic, and accessible
3. Each verse should build spiritually -- tell a journey of faith
4. Chorus must be singable, memorable, and theologically rich
5. Choose the Bible verse that best fits the theme
6. Write 3 SEO-optimized YouTube title options
7. Write a 2-sentence YouTube description with natural keywords
8. Write 8 relevant search tags

Theme for this hymn: {theme}
Style: {style}"""


def generate_hymn(force_theme: str = None, force_style: str = None) -> dict:
    """
    Full hymn generation pipeline using Gemini structured output.
    Guaranteed valid JSON -- no parse failures.
    """
    logger.info("Starting hymn generation...")

    # Step 1 -- Get recent hymns for context and variety checking
    recent_hymns = get_recent_themes(limit=10)

    # Step 2 -- Pick theme and style
    if force_theme and force_style:
        theme, style = force_theme, force_style
    else:
        theme, style = get_theme_for_today(recent_hymns)
    logger.info(f"Theme='{theme}', Style='{style}'")

    # Step 3 -- Pick hymn length
    length = random.choice(HYMN_LENGTHS)
    logger.info(f"Length: {length['label']} ({length['verses']} verses)")

    # Step 4 -- Build prompt and call Gemini with structured output schema
    prompt = build_hymn_prompt(theme, style, length)
    logger.info("Calling Gemini with structured output schema...")

    raw_response = rotator.generate_with_retry(
        prompt=prompt,
        response_schema=HYMN_SCHEMA,
    )

    # Step 5 -- Parse (should always succeed with structured output)
    hymn_data = json.loads(raw_response)
    logger.info(f"Hymn generated: '{hymn_data['title']}'")

    # Add theme/style if Gemini didn't include them (schema guarantees they exist)
    hymn_data.setdefault("theme", theme)
    hymn_data.setdefault("style", style)

    # Flatten seo_titles list to single seo_title string
    seo_titles = hymn_data.get("seo_titles", [hymn_data.get("title", "")])
    hymn_data["seo_title"] = seo_titles[0] if seo_titles else hymn_data["title"]

    # Step 6 -- Compliance checks
    logger.info("Running compliance checks...")
    compliance = run_all_checks(hymn_data, recent_hymns)

    if not compliance["passed"]:
        logger.warning(f"Compliance failed: {compliance['blocking_reason']}")
        logger.info("Retrying with same theme/style...")
        raw_response = rotator.generate_with_retry(
            prompt=prompt,
            response_schema=HYMN_SCHEMA,
        )
        hymn_data = json.loads(raw_response)
        hymn_data["seo_title"] = hymn_data.get("seo_titles", [""])[0]
        compliance = run_all_checks(hymn_data, recent_hymns)
        if not compliance["passed"]:
            raise RuntimeError(
                f"Hymn failed compliance after retry: {compliance['blocking_reason']}"
            )

    logger.info("Compliance checks passed")

    # Step 7 -- Save to Supabase
    saved = save_hymn(hymn_data)
    logger.info(f"Saved to Supabase with ID: {saved.get('id')}")

    return saved


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("Testing HymnFlow hymn generator...")
    try:
        hymn = generate_hymn()
        print(f"\nHymn generated successfully!")
        print(f"   Title    : {hymn.get('title')}")
        print(f"   Theme    : {hymn.get('theme')}")
        print(f"   Style    : {hymn.get('style')}")
        print(f"   Scripture: {hymn.get('bible_reference')}")
        print(f"   DB ID    : {hymn.get('id')}")
    except Exception as e:
        print(f"\nGeneration failed: {e}")
