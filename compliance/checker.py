"""
HymnFlow — Compliance Checker
Runs before any hymn is saved or video is built.
Checks:
  1. Copyright safety (public domain only — pre-1928 rule)
  2. YouTube policy alignment (no repetitive/mass-produced flags)
  3. Lyric variety health (not too similar to recent hymns)
"""

import json
import logging
from generator.key_rotator import rotator

logger = logging.getLogger(__name__)

# ── Known copyrighted hymn phrases to block (post-1928) ──────────────────────
# This is a starter list — system will also use Gemini to detect issues
KNOWN_COPYRIGHTED_PHRASES = [
    "shout to the lord",
    "mighty to save",
    "oceans where feet may fail",
    "what a beautiful name",
    "reckless love",
    "goodness of god",
    "way maker miracle worker",
    "build my life",
    "who you say i am",
    "living hope",
    "holy spirit you are welcome here",
    "spirit break out",
    "let it be known",
    "graves into gardens",
]

YOUTUBE_POLICY_REMINDER = """
YouTube 2025 monetization policy requires:
- Content must be original and add clear value
- No mass-produced or repetitive format videos
- AI-generated content is allowed but must be disclosed
- Must not mimic or closely copy existing copyrighted songs
"""


def check_copyright(hymn_data: dict) -> dict:
    """
    Check hymn lyrics and title against known copyrighted material.
    Returns {"safe": bool, "reason": str}
    """
    title = hymn_data.get("title", "").lower()
    lyrics_raw = hymn_data.get("lyrics", [])

    # Flatten lyrics into one string for scanning
    if isinstance(lyrics_raw, list):
        all_text = title + " " + " ".join(
            " ".join(stanza.get("lines", [])) for stanza in lyrics_raw
        ).lower()
    else:
        all_text = (title + " " + str(lyrics_raw)).lower()

    # Check against known copyrighted phrases
    for phrase in KNOWN_COPYRIGHTED_PHRASES:
        if phrase in all_text:
            return {
                "safe": False,
                "reason": f"Lyrics contain a known copyrighted phrase: '{phrase}'. Please regenerate."
            }

    return {"safe": True, "reason": "No known copyrighted phrases detected."}


def check_with_gemini(hymn_data: dict) -> dict:
    """
    Use Gemini itself to do a deeper compliance review.
    Returns {"safe": bool, "reason": str, "suggestions": list}
    """
    prompt = f"""
You are a copyright and YouTube compliance expert for Christian music.

Review this hymn and answer ONLY in valid JSON with this exact structure:
{{
  "copyright_safe": true or false,
  "youtube_policy_safe": true or false,
  "issues": ["issue1", "issue2"],
  "suggestions": ["fix1", "fix2"],
  "overall_verdict": "SAFE" or "UNSAFE"
}}

YouTube Policy Context:
{YOUTUBE_POLICY_REMINDER}

Hymn to review:
Title: {hymn_data.get('title')}
Theme: {hymn_data.get('theme')}
Style: {hymn_data.get('style')}
Bible Reference: {hymn_data.get('bible_reference')}

Lyrics:
{json.dumps(hymn_data.get('lyrics', []), indent=2)}

Check for:
1. Does this closely copy or imitate any post-1928 copyrighted hymn or worship song?
2. Is the content original enough to avoid YouTube's repetitive content flag?
3. Are there any phrases that are distinctively from a copyrighted song?

Respond with ONLY the JSON object. No explanation, no markdown.
"""

    try:
        from google.genai import types as genai_types
        compliance_schema = genai_types.Schema(
            type=genai_types.Type.OBJECT,
            properties={
                "copyright_safe":      genai_types.Schema(type=genai_types.Type.BOOLEAN),
                "youtube_policy_safe": genai_types.Schema(type=genai_types.Type.BOOLEAN),
                "issues":              genai_types.Schema(type=genai_types.Type.ARRAY, items=genai_types.Schema(type=genai_types.Type.STRING)),
                "suggestions":         genai_types.Schema(type=genai_types.Type.ARRAY, items=genai_types.Schema(type=genai_types.Type.STRING)),
                "overall_verdict":     genai_types.Schema(type=genai_types.Type.STRING),
            },
            required=["copyright_safe", "youtube_policy_safe", "issues", "suggestions", "overall_verdict"],
        )
        response_text = rotator.generate_with_retry(prompt, response_schema=compliance_schema)
        result = json.loads(response_text)

        safe = (
            result.get("copyright_safe", False)
            and result.get("youtube_policy_safe", False)
            and result.get("overall_verdict", "UNSAFE") == "SAFE"
        )

        return {
            "safe": safe,
            "reason": "; ".join(result.get("issues", [])) if not safe else "Gemini compliance check passed.",
            "suggestions": result.get("suggestions", []),
            "raw": result,
        }

    except json.JSONDecodeError as e:
        logger.error(f"Compliance check JSON parse error: {e}")
        return {
            "safe": False,
            "reason": f"Could not parse Gemini compliance response: {e}",
            "suggestions": ["Try regenerating the hymn."],
        }
    except Exception as e:
        logger.error(f"Compliance check failed: {e}")
        return {
            "safe": False,
            "reason": f"Compliance check error: {e}",
            "suggestions": [],
        }


def check_variety(hymn_data: dict, recent_hymns: list) -> dict:
    """
    Ensure the new hymn isn't too similar to recent ones.
    recent_hymns: list of dicts with 'theme' and 'style' keys.
    Returns {"safe": bool, "reason": str}
    """
    if not recent_hymns:
        return {"safe": True, "reason": "No recent hymns to compare against."}

    new_theme = hymn_data.get("theme", "").lower()
    new_style = hymn_data.get("style", "").lower()

    recent_themes = [h.get("theme", "").lower() for h in recent_hymns]
    recent_styles = [h.get("style", "").lower() for h in recent_hymns]

    # Count how many of the last 5 hymns share the same theme
    last_five_themes = recent_themes[:5]
    same_theme_count = last_five_themes.count(new_theme)

    if same_theme_count >= 3:
        return {
            "safe": False,
            "reason": (
                f"The theme '{new_theme}' has appeared {same_theme_count} times "
                f"in the last 5 hymns. YouTube may flag this as repetitive. "
                f"Please regenerate with a different theme."
            )
        }

    # Check style — don't do more than 4 of the same style in last 7
    last_seven_styles = recent_styles[:7]
    same_style_count = last_seven_styles.count(new_style)

    if same_style_count >= 4:
        return {
            "safe": False,
            "reason": (
                f"The style '{new_style}' has been used {same_style_count} times "
                f"in the last 7 hymns. Mix in a different style for variety."
            )
        }

    return {"safe": True, "reason": "Variety check passed."}


def run_all_checks(hymn_data: dict, recent_hymns: list = None) -> dict:
    """
    Master compliance runner — runs all checks in order.
    Returns {"passed": bool, "checks": dict, "blocking_reason": str or None}
    """
    results = {}

    # 1. Fast local copyright scan
    results["copyright_local"] = check_copyright(hymn_data)
    if not results["copyright_local"]["safe"]:
        return {
            "passed": False,
            "checks": results,
            "blocking_reason": results["copyright_local"]["reason"],
        }

    # 2. Variety health check
    if recent_hymns is not None:
        results["variety"] = check_variety(hymn_data, recent_hymns)
        if not results["variety"]["safe"]:
            return {
                "passed": False,
                "checks": results,
                "blocking_reason": results["variety"]["reason"],
            }

    # 3. Deep Gemini compliance scan (uses 1 API call)
    logger.info("Running Gemini compliance check...")
    results["gemini_compliance"] = check_with_gemini(hymn_data)
    if not results["gemini_compliance"]["safe"]:
        return {
            "passed": False,
            "checks": results,
            "blocking_reason": results["gemini_compliance"]["reason"],
        }

    return {
        "passed": True,
        "checks": results,
        "blocking_reason": None,
    }
