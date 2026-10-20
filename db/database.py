"""
HymnFlow — Supabase Database Layer
All reads and writes to Supabase go through this module.
Tables:
  - hymns        : every generated hymn and its current status
  - videos       : rendered video metadata and file paths
  - youtube_posts: upload records and YouTube video IDs
"""

from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
from datetime import datetime, timezone
import json

# ── Client ───────────────────────────────────────────────────────────────────
def get_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ── Hymn Status Constants ────────────────────────────────────────────────────
STATUS_PENDING   = "pending"    # Generated, waiting for your review
STATUS_APPROVED  = "approved"   # You approved it
STATUS_REJECTED  = "rejected"   # You rejected it
STATUS_RENDERED  = "rendered"   # Video has been built
STATUS_SCHEDULED = "scheduled"  # Queued for YouTube upload
STATUS_POSTED    = "posted"     # Live on YouTube


# ── Create / Insert ──────────────────────────────────────────────────────────
def save_hymn(hymn_data: dict) -> dict:
    """
    Save a newly generated hymn to the database.
    hymn_data expected keys:
      title, theme, style, lyrics (JSON string), bible_verse,
      bible_reference, seo_title, seo_description, seo_tags (JSON string)
    Returns the inserted row.
    """
    client = get_client()
    row = {
        "title":           hymn_data["title"],
        "theme":           hymn_data["theme"],
        "style":           hymn_data["style"],
        "lyrics":          json.dumps(hymn_data["lyrics"]),   # list of stanzas
        "bible_verse":     hymn_data["bible_verse"],
        "bible_reference": hymn_data["bible_reference"],
        "seo_title":       hymn_data.get("seo_title", ""),
        "seo_description": hymn_data.get("seo_description", ""),
        "seo_tags":        json.dumps(hymn_data.get("seo_tags", [])),
        "status":          STATUS_PENDING,
        "created_at":      datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("hymns").insert(row).execute()
    return result.data[0] if result.data else {}


def save_video(hymn_id: str, video_path: str, thumbnail_path: str) -> dict:
    """Record a successfully rendered video."""
    client = get_client()
    row = {
        "hymn_id":        hymn_id,
        "video_path":     video_path,
        "thumbnail_path": thumbnail_path,
        "rendered_at":    datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("videos").insert(row).execute()
    return result.data[0] if result.data else {}


def save_youtube_post(hymn_id: str, video_id: str, youtube_url: str) -> dict:
    """Record a successful YouTube upload."""
    client = get_client()
    row = {
        "hymn_id":     hymn_id,
        "video_id":    video_id,
        "youtube_url": youtube_url,
        "posted_at":   datetime.now(timezone.utc).isoformat(),
    }
    result = client.table("youtube_posts").insert(row).execute()
    return result.data[0] if result.data else {}


# ── Read ─────────────────────────────────────────────────────────────────────
def get_hymn(hymn_id: str) -> dict:
    client = get_client()
    result = client.table("hymns").select("*").eq("id", hymn_id).single().execute()
    return result.data or {}


def get_pending_hymns() -> list:
    client = get_client()
    result = (
        client.table("hymns")
        .select("*")
        .eq("status", STATUS_PENDING)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data or []


def get_approved_hymns() -> list:
    """Approved but not yet rendered."""
    client = get_client()
    result = (
        client.table("hymns")
        .select("*")
        .eq("status", STATUS_APPROVED)
        .order("created_at")
        .execute()
    )
    return result.data or []


def get_rendered_hymns() -> list:
    """Rendered but not yet posted to YouTube."""
    client = get_client()
    result = (
        client.table("hymns")
        .select("*, videos(*)")
        .eq("status", STATUS_RENDERED)
        .order("created_at")
        .execute()
    )
    return result.data or []


def get_recent_hymns(limit: int = 20) -> list:
    client = get_client()
    result = (
        client.table("hymns")
        .select("*, youtube_posts(*)")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_recent_themes(limit: int = 10) -> list:
    """Returns the themes of the last N hymns to avoid repetition."""
    client = get_client()
    result = (
        client.table("hymns")
        .select("theme, style")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_video_for_hymn(hymn_id: str) -> dict:
    client = get_client()
    result = (
        client.table("videos")
        .select("*")
        .eq("hymn_id", hymn_id)
        .single()
        .execute()
    )
    return result.data or {}


# ── Update ───────────────────────────────────────────────────────────────────
def update_hymn_status(hymn_id: str, status: str) -> dict:
    client = get_client()
    result = (
        client.table("hymns")
        .update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", hymn_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def approve_hymn(hymn_id: str) -> dict:
    return update_hymn_status(hymn_id, STATUS_APPROVED)


def reject_hymn(hymn_id: str) -> dict:
    return update_hymn_status(hymn_id, STATUS_REJECTED)


def mark_rendered(hymn_id: str) -> dict:
    return update_hymn_status(hymn_id, STATUS_RENDERED)


def mark_posted(hymn_id: str) -> dict:
    return update_hymn_status(hymn_id, STATUS_POSTED)
