import asyncio
import logging

from research import search_web
from writer import generate_intelligence
from scheduler import choose_research_topics, research_niche
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

from telegram import Bot


logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


async def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing.")

    if not TELEGRAM_CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID is missing.")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    topics = choose_research_topics()

    if not topics:
        logger.info("No research niches available.")
        return

    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "🧠 <b>CRYPTO INTELLIGENCE FEED</b>\n\n"
            "Fresh research worth looking at:"
        ),
        parse_mode="HTML",
    )

    for niche in topics:
        try:
            research = await research_niche(niche)

            if not research:
                continue

            intelligence = await asyncio.to_thread(
                generate_intelligence,
                research,
                "GitHub scheduled feed",
            )

            if not intelligence:
                continue

            if len(intelligence) > 3900:
                intelligence = intelligence[:3900]

            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=intelligence,
            )

        except Exception:
            logger.exception(
                "GitHub feed failed for niche: %s",
                niche,
            )

    logger.info("GitHub intelligence feed completed.")


if __name__ == "__main__":
    asyncio.run(main())