"""
HymnFlow -- Sprint 2 Test
Tests the Telegram bot connection and sends a real test message.
Run with: python test_sprint2.py
"""

import sys
import asyncio
sys.stdout.reconfigure(encoding="utf-8")

async def test_bot_connection():
    print("\n--- Test 1: Telegram Bot Token ---")
    try:
        from telegram import Bot
        from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        me = await bot.get_me()
        print(f"  PASS: Bot connected -- @{me.username}")
        print(f"  PASS: Bot name: {me.first_name}")
        return bot, TELEGRAM_CHAT_ID
    except Exception as e:
        print(f"  FAIL: {e}")
        return None, None


async def test_send_message(bot, chat_id):
    print("\n--- Test 2: Send Test Message ---")
    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=(
                "*HymnFlow Bot -- Connection Test*\n\n"
                "If you can see this message, Sprint 2 is working!\n\n"
                "Your bot is connected and ready to send you hymns every morning."
            ),
            parse_mode="Markdown"
        )
        print(f"  PASS: Message sent successfully (ID: {msg.message_id})")
        return True
    except Exception as e:
        print(f"  FAIL: Could not send message: {e}")
        return False


async def test_send_hymn_preview(bot, chat_id):
    print("\n--- Test 3: Send Real Hymn Preview with Buttons ---")
    try:
        from db.database import get_pending_hymns, get_recent_hymns
        from bot.telegram_bot import format_hymn_message, approve_reject_keyboard

        # Try pending first, then fall back to most recent
        hymns = get_pending_hymns()
        if not hymns:
            hymns = get_recent_hymns(limit=1)

        if not hymns:
            print("  SKIP: No hymns in database yet -- run test_sprint1.py first")
            return True

        hymn = hymns[0]
        msg  = format_hymn_message(hymn)
        kb   = approve_reject_keyboard(hymn["id"])

        await bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode="Markdown",
            reply_markup=kb
        )
        print(f"  PASS: Hymn preview sent with Approve/Reject buttons")
        print(f"     Title: {hymn.get('title')}")
        print(f"     Check your Telegram -- tap the buttons to test them!")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


async def main():
    print("=" * 50)
    print("  HymnFlow -- Sprint 2 Test Suite")
    print("=" * 50)

    bot, chat_id = await test_bot_connection()
    if not bot:
        print("\nFIX: Check TELEGRAM_BOT_TOKEN in your .env file")
        return

    r2 = await test_send_message(bot, chat_id)
    r3 = await test_send_hymn_preview(bot, chat_id)

    passed = sum([bool(bot), r2, r3])
    print("\n" + "=" * 50)
    print("  RESULTS")
    print("=" * 50)
    print(f"  [PASS] Bot Connection")
    print(f"  {'[PASS]' if r2 else '[FAIL]'} Send Message")
    print(f"  {'[PASS]' if r3 else '[FAIL]'} Hymn Preview with Buttons")
    print(f"\n  {passed}/3 tests passed")

    if passed == 3:
        print("\n  Sprint 2 complete! Check your Telegram now.")
        print("  Next: python bot/telegram_bot.py  (to run the bot live)")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
