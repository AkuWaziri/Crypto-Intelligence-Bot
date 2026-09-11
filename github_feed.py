import asyncio
import logging

from scheduler import generate_feed, record_fed_items
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID is missing.")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    reports, history = await generate_feed()

    if not reports:
        logger.info("No new high-signal crypto developments found this cycle.")
        return

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🧠 <b>CRYPTO INTELLIGENCE FEED</b>\n\n"
            "Current developments worth looking at:"
        ),
        parse_mode="HTML",
    )

    sent_reports = []

    for item in reports:
        intelligence = item["report"]

        if len(intelligence) > 3900:
            intelligence = intelligence[:3900] + "\n\n[truncated]"

        try:
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=intelligence,
            )
            sent_reports.append(item)
        except Exception:
            logger.exception(
                "Telegram send failed for: %s",
                item.get("candidate", {}).get("title", "unknown"),
            )

    # Only mark a story as fed after Telegram accepted the message.
    if sent_reports:
        record_fed_items(history, sent_reports)

    logger.info(
        "GitHub intelligence feed completed. Sent %s new stories.",
        len(sent_reports),
    )


if __name__ == "__main__":
    asyncio.run(main())
