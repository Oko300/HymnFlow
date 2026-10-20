"""
HymnFlow -- Telegram Bot (Sprint 2)
Sends you a hymn preview every morning with Approve/Reject buttons.
All interactions happen in YOUR private chat with the bot.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from db.database import (
    get_pending_hymns,
    get_hymn,
    approve_hymn,
    reject_hymn,
    get_recent_hymns,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_PENDING,
    STATUS_RENDERED,
    STATUS_POSTED,
)

sys.stdout.reconfigure(encoding="utf-8")
logger = logging.getLogger(__name__)


# ── Security: only respond to YOUR chat ──────────────────────────────────────
def is_authorized(update: Update) -> bool:
    chat_id = str(update.effective_chat.id)
    return chat_id == str(TELEGRAM_CHAT_ID)


def unauthorized_response() -> str:
    return "Unauthorized. This bot only responds to its owner."


# ── Format a hymn as a readable Telegram message ─────────────────────────────
def format_hymn_message(hymn: dict) -> str:
    title     = hymn.get("title", "Untitled")
    theme     = hymn.get("theme", "")
    style     = hymn.get("style", "")
    verse     = hymn.get("bible_verse", "")
    ref       = hymn.get("bible_reference", "")
    seo_title = hymn.get("seo_title", title)

    # Parse lyrics
    lyrics_raw = hymn.get("lyrics", [])
    if isinstance(lyrics_raw, str):
        try:
            lyrics_raw = json.loads(lyrics_raw)
        except Exception:
            lyrics_raw = []

    lyrics_text = ""
    for stanza in lyrics_raw:
        label = stanza.get("label", "")
        lines = stanza.get("lines", [])
        lyrics_text += f"\n*{label}*\n"
        lyrics_text += "\n".join(lines)
        lyrics_text += "\n"

    seo_tags_raw = hymn.get("seo_tags", [])
    if isinstance(seo_tags_raw, str):
        try:
            seo_tags_raw = json.loads(seo_tags_raw)
        except Exception:
            seo_tags_raw = []
    tags = " ".join([f"#{t.replace(' ', '')}" for t in seo_tags_raw[:5]])

    message = (
        f"*HymnFlow -- Daily Hymn Preview*\n"
        f"{'=' * 35}\n\n"
        f"*Title:* {title}\n"
        f"*Theme:* {theme}  |  *Style:* {style}\n"
        f"*YouTube Title:* {seo_title}\n\n"
        f"{'─' * 35}\n"
        f"{lyrics_text}\n"
        f"{'─' * 35}\n\n"
        f"*Scripture:*\n_{verse}_\n-- {ref}\n\n"
        f"{tags}\n\n"
        f"_Do you want to post this hymn?_"
    )
    return message


def approve_reject_keyboard(hymn_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Approve -- Post it", callback_data=f"approve:{hymn_id}"),
            InlineKeyboardButton("Reject -- Skip it",  callback_data=f"reject:{hymn_id}"),
        ]
    ])


def regenerate_keyboard(hymn_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Generate a new hymn", callback_data=f"regenerate:{hymn_id}")]
    ])


# ── Command Handlers ──────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text(unauthorized_response())
        return

    await update.message.reply_text(
        "*Welcome to HymnFlow Bot*\n\n"
        "Every morning I will send you a new hymn to review.\n\n"
        "Commands:\n"
        "/preview -- See today's pending hymn\n"
        "/queue   -- See what's in the approval queue\n"
        "/history -- See recently posted hymns\n"
        "/status  -- System status\n"
        "/generate -- Generate a new hymn right now",
        parse_mode="Markdown"
    )


async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the most recent pending hymn for approval."""
    if not is_authorized(update):
        await update.message.reply_text(unauthorized_response())
        return

    pending = get_pending_hymns()
    if not pending:
        await update.message.reply_text(
            "No hymns pending review right now.\n"
            "Use /generate to create one, or wait for the morning generation.",
            parse_mode="Markdown"
        )
        return

    hymn = pending[0]
    msg  = format_hymn_message(hymn)
    kb   = approve_reject_keyboard(hymn["id"])

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)


async def queue_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the full approval queue."""
    if not is_authorized(update):
        await update.message.reply_text(unauthorized_response())
        return

    pending = get_pending_hymns()
    if not pending:
        await update.message.reply_text("Queue is empty -- nothing pending review.")
        return

    lines = [f"*Hymns waiting for your review ({len(pending)}):*\n"]
    for i, h in enumerate(pending, 1):
        lines.append(f"{i}. _{h.get('title', 'Untitled')}_ ({h.get('theme', '')})")

    await update.message.reply_text(
        "\n".join(lines) + "\n\nUse /preview to review the next one.",
        parse_mode="Markdown"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show recently generated hymns and their status."""
    if not is_authorized(update):
        await update.message.reply_text(unauthorized_response())
        return

    recent = get_recent_hymns(limit=10)
    if not recent:
        await update.message.reply_text("No hymns generated yet.")
        return

    status_icons = {
        STATUS_PENDING:   "Pending review",
        STATUS_APPROVED:  "Approved",
        STATUS_REJECTED:  "Rejected",
        STATUS_RENDERED:  "Video ready",
        STATUS_POSTED:    "Live on YouTube",
    }

    lines = ["*Recent Hymns:*\n"]
    for h in recent:
        st   = h.get("status", "unknown")
        icon = status_icons.get(st, st)
        date = h.get("created_at", "")[:10]
        lines.append(f"- _{h.get('title', 'Untitled')}_ -- {icon} ({date})")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show system status."""
    if not is_authorized(update):
        await update.message.reply_text(unauthorized_response())
        return

    pending  = get_pending_hymns()
    recent   = get_recent_hymns(limit=50)
    posted   = [h for h in recent if h.get("status") == STATUS_POSTED]
    approved = [h for h in recent if h.get("status") == STATUS_APPROVED]

    now = datetime.now(timezone.utc)
    msg = (
        f"*HymnFlow System Status*\n"
        f"{'─' * 30}\n"
        f"Pending review:  {len(pending)}\n"
        f"Approved (queue): {len(approved)}\n"
        f"Posted to YouTube: {len(posted)}\n"
        f"Time (UTC): {now.strftime('%Y-%m-%d %H:%M')}\n\n"
        f"_System is running normally._"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def generate_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger a hymn generation right now."""
    if not is_authorized(update):
        await update.message.reply_text(unauthorized_response())
        return

    await update.message.reply_text(
        "Generating a new hymn... This takes about 30 seconds.",
        parse_mode="Markdown"
    )

    try:
        # Run generation in executor so it doesn't block the bot
        loop = asyncio.get_event_loop()
        from generator.hymn_gen import generate_hymn
        hymn = await loop.run_in_executor(None, generate_hymn)

        msg = format_hymn_message(hymn)
        kb  = approve_reject_keyboard(hymn["id"])
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=kb)

    except Exception as e:
        logger.error(f"Manual generation failed: {e}")
        await update.message.reply_text(
            f"Generation failed: {e}\n\nTry again with /generate.",
            parse_mode="Markdown"
        )


# ── Button Callback Handler ───────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_authorized(update):
        await query.edit_message_text(unauthorized_response())
        return

    data     = query.data
    action, hymn_id = data.split(":", 1)

    if action == "approve":
        approve_hymn(hymn_id)
        hymn = get_hymn(hymn_id)
        title = hymn.get("title", "Hymn")
        await query.edit_message_text(
            f"*Approved!*\n\n"
            f"_{title}_ is queued for video rendering and YouTube upload.\n\n"
            f"The video will be built and posted automatically.",
            parse_mode="Markdown"
        )
        logger.info(f"Hymn approved: {hymn_id} -- {title}")

        # Check if there are more pending hymns
        pending = get_pending_hymns()
        if pending:
            next_hymn = pending[0]
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"You have {len(pending)} more hymn(s) waiting.\nUse /preview to review the next one."
            )

    elif action == "reject":
        reject_hymn(hymn_id)
        hymn  = get_hymn(hymn_id)
        title = hymn.get("title", "Hymn")
        await query.edit_message_text(
            f"*Rejected.*\n\n"
            f"_{title}_ has been discarded.\n\n"
            f"Use /generate to create a new hymn, or wait for tomorrow's generation.",
            parse_mode="Markdown",
            reply_markup=regenerate_keyboard(hymn_id)
        )
        logger.info(f"Hymn rejected: {hymn_id} -- {title}")

    elif action == "regenerate":
        await query.edit_message_text(
            "Generating a replacement hymn... Give me about 30 seconds."
        )
        try:
            loop = asyncio.get_event_loop()
            from generator.hymn_gen import generate_hymn
            hymn = await loop.run_in_executor(None, generate_hymn)
            msg  = format_hymn_message(hymn)
            kb   = approve_reject_keyboard(hymn["id"])
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=msg,
                parse_mode="Markdown",
                reply_markup=kb
            )
        except Exception as e:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"Regeneration failed: {e}\n\nUse /generate to try again."
            )


# ── Send morning hymn (called by scheduler) ───────────────────────────────────
async def send_morning_hymn(app: Application):
    """
    Called by APScheduler every morning.
    Generates a hymn and sends it to your Telegram for review.
    """
    logger.info("Sending morning hymn notification...")
    try:
        loop = asyncio.get_event_loop()
        from generator.hymn_gen import generate_hymn
        hymn = await loop.run_in_executor(None, generate_hymn)

        msg = (
            f"Good morning! Here is your daily hymn for review.\n\n"
            + format_hymn_message(hymn)
        )
        kb = approve_reject_keyboard(hymn["id"])

        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=msg,
            parse_mode="Markdown",
            reply_markup=kb
        )
        logger.info(f"Morning hymn sent: {hymn.get('title')}")

    except Exception as e:
        logger.error(f"Morning hymn send failed: {e}")
        await app.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=f"Morning hymn generation failed: {e}\n\nUse /generate to try manually."
        )


# ── Build and return the Application ─────────────────────────────────────────
def build_app() -> Application:
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("preview",  preview))
    app.add_handler(CommandHandler("queue",    queue_status))
    app.add_handler(CommandHandler("history",  history))
    app.add_handler(CommandHandler("status",   status_cmd))
    app.add_handler(CommandHandler("generate", generate_now))
    app.add_handler(CallbackQueryHandler(button_callback))

    return app


# ── Standalone run (for testing Sprint 2) ────────────────────────────────────
if __name__ == "__main__":
    import sys
    import os
    # Allow running from bot/ subfolder or project root
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    logger.info("Starting HymnFlow Telegram bot in standalone mode...")
    app = build_app()
    print("Bot is running. Open Telegram and message @hymnflow_bot")
    print("Commands to test: /start  /generate  /preview  /status  /queue  /history")
    print("Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True)
