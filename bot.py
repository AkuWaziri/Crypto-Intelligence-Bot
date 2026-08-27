import asyncio
import logging
import html

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from niches import get_niches, add_niche
from research import search_web
from writer import generate_intelligence
from scheduler import scheduler_loop


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


HELP_TEXT = """
🧠 <b>Crypto Intelligence Bot</b>

Research crypto/Web3 developments and turn useful discoveries into content intelligence.

<b>COMMANDS</b>

/start — start the bot
/help — show this help
/niches — show research niches
/research &lt;topic&gt; — research anything
/addniche &lt;niche&gt; — add a new niche
/feed — run a fresh intelligence feed now

<b>RESEARCH EXAMPLES</b>

/research AI agents

/research crypto payments

/research suspicious smart contracts

/research wallets moving BTC

/research new crypto opportunities

/research airdrops ending soon

/research new crypto infrastructure

<b>TIP</b>

You can research almost anything. Just type the topic after /research.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
    )


async def niches_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    niches = get_niches()

    text = "🧠 <b>RESEARCH NICHES</b>\n\n"

    for index, niche in enumerate(niches, start=1):
        text += f"{index}. {html.escape(niche)}\n"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


async def add_niche_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addniche <niche>"
        )
        return

    niche = " ".join(context.args).strip()

    if add_niche(niche):
        await update.message.reply_text(
            f"✅ Added niche: {niche}"
        )
    else:
        await update.message.reply_text(
            "⚠️ That niche already exists or is invalid."
        )


async def research_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not context.args:
        await update.message.reply_text(
            "Usage:\n/research <topic>\n\n"
            "Example:\n"
            "/research AI agents"
        )
        return

    query = " ".join(context.args).strip()

    status = await update.message.reply_text(
        f"🔎 Researching:\n{query}"
    )

    try:
        research = await asyncio.to_thread(
            search_web,
            query,
        )

        if not research.get("results"):
            await status.edit_text(
                "❌ No useful crypto/Web3 results found."
            )
            return

        intelligence = await asyncio.to_thread(
            generate_intelligence,
            research,
            "manual research",
        )

        await status.delete()

        await send_long_message(
            update,
            intelligence,
        )

    except Exception as exc:
        logger.exception("Research failed.")

        await status.edit_text(
            "❌ Research failed.\n\n"
            f"Error: {html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
        )


async def feed_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "🧠 Running a fresh intelligence feed..."
    )

    try:
        from scheduler import generate_feed

        reports = await generate_feed()

        if not reports:
            await update.message.reply_text(
                "No useful discoveries found this cycle."
            )
            return

        for report in reports:
            await send_long_message(
                update,
                report,
            )

    except Exception as exc:
        logger.exception("Manual feed failed.")

        await update.message.reply_text(
            f"❌ Feed failed: {exc}"
        )


async def send_long_message(
    update: Update,
    text: str,
):
    """
    Telegram messages have a character limit.
    Split long intelligence reports safely.
    """

    max_length = 3900

    if len(text) <= max_length:
        await update.message.reply_text(
            text,
        )
        return

    parts = []

    while text:
        parts.append(text[:max_length])
        text = text[max_length:]

    for part in parts:
        await update.message.reply_text(part)


async def scheduler_sender(text):
    """
    Sends scheduled intelligence to the configured Telegram chat.
    """

    if not TELEGRAM_CHAT_ID:
        logger.error(
            "TELEGRAM_CHAT_ID is missing."
        )
        return

    application = scheduler_sender.application

    await application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
    )


async def post_init(application):
    scheduler_sender.application = application

    asyncio.create_task(
        scheduler_loop(
            scheduler_sender
        )
    )

    logger.info(
        "Background scheduler launched."
    )


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("niches", niches_command)
    )

    application.add_handler(
        CommandHandler("research", research_command)
    )

    application.add_handler(
        CommandHandler("addniche", add_niche_command)
    )

    application.add_handler(
        CommandHandler("feed", feed_command)
    )

    logger.info(
        "Crypto Intelligence Bot starting..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()