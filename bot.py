import asyncio
import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

from niches import get_niches, add_niche
from research import search_web
from writer import generate_intelligence
from scheduler import scheduler_loop


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


def authorized(update: Update):
    """
    Optional protection.

    If TELEGRAM_CHAT_ID is configured,
    only that Telegram chat can use the bot.
    """

    if not TELEGRAM_CHAT_ID:
        return True

    chat = update.effective_chat

    if not chat:
        return False

    return str(chat.id) == str(TELEGRAM_CHAT_ID)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return

    message = """
🧠 <b>Crypto Intelligence Bot</b>

I research crypto/Web3 and turn useful discoveries into content intelligence.

<b>Commands</b>

/help — show commands
/niches — show research niches
/research &lt;topic&gt; — research anything
/addniche &lt;niche&gt; — add a research niche
/feed — run a fresh intelligence feed now

Examples:

/research AI agents

/research crypto payments

/research suspicious smart contracts

/research wallets moving BTC

/research new crypto opportunities

The automatic feed runs periodically in the background.
"""

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    message = """
<b>🧠 HOW TO USE THE BOT</b>

<b>Research anything</b>

/research AI agents

/research Base payments

/research new airdrops

/research crypto infrastructure

/research interesting wallet movements

/research contract vulnerability

You can enter almost any topic.

<b>Niches</b>

/niches

<b>Add a niche</b>

/addniche prediction markets

<b>Run the feed manually</b>

/feed

<b>Automatic feed</b>

The bot automatically researches several niches and sends useful discoveries to Telegram.

The goal is not just news.

It looks for things you could:

• write about
• test
• investigate
• build
• explain
• discover early
• turn into crypto content
"""

    await update.message.reply_text(
        message,
        parse_mode=ParseMode.HTML,
    )


async def niches_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    niches = get_niches()

    text = "<b>🔎 CURRENT RESEARCH NICHES</b>\n\n"

    for index, niche in enumerate(niches, start=1):
        text += f"{index}. {niche}\n"

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
    )


async def add_niche_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addniche prediction markets"
        )
        return

    niche = " ".join(context.args)

    if add_niche(niche):
        await update.message.reply_text(
            f"✅ Added research niche:\n{niche}"
        )
    else:
        await update.message.reply_text(
            "That niche already exists or is invalid."
        )


async def research_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    if not context.args:
        await update.message.reply_text(
            "Tell me what you want researched.\n\n"
            "Example:\n"
            "/research AI agents"
        )
        return

    query = " ".join(context.args)

    status = await update.message.reply_text(
        f"🔎 Researching:\n<b>{query}</b>\n\n"
        "Looking for useful developments...",
        parse_mode=ParseMode.HTML,
    )

    try:
        research = await asyncio.to_thread(
            search_web,
            query
        )

        if not research.get("results"):
            await status.edit_text(
                "I couldn't find enough useful research for that topic."
            )
            return

        result = await asyncio.to_thread(
            generate_intelligence,
            research,
            "manual research"
        )

        if len(result) > 3900:
            result = result[:3900] + "\n\n[truncated]"

        await status.edit_text(result)

    except Exception as error:
        logger.exception("Manual research failed.")

        await status.edit_text(
            "❌ Research failed.\n\n"
            f"{str(error)[:500]}"
        )


async def feed_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    if not authorized(update):
        return

    await update.message.reply_text(
        "🧠 Starting a fresh intelligence feed..."
    )

    from scheduler import generate_feed

    try:
        reports = await generate_feed()

        if not reports:
            await update.message.reply_text(
                "No useful discoveries were found this time."
            )
            return

        for report in reports:
            if len(report) > 3900:
                report = report[:3900] + "\n\n[truncated]"

            await update.message.reply_text(report)

    except Exception as error:
        logger.exception("Manual feed failed.")

        await update.message.reply_text(
            f"❌ Feed failed:\n{str(error)[:500]}"
        )


async def scheduled_sender(application, text):
    """
    Sends scheduler messages to the configured Telegram chat.
    """

    if not TELEGRAM_CHAT_ID:
        logger.warning(
            "TELEGRAM_CHAT_ID is missing. "
            "Scheduled messages cannot be sent."
        )
        return

    await application.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode=ParseMode.HTML,
    )


async def post_init(application):
    """
    Start the background research scheduler.
    """

    async def sender(text):
        await scheduled_sender(application, text)

    application.bot_data["scheduler_task"] = asyncio.create_task(
        scheduler_loop(sender)
    )

    logger.info("Background scheduler launched.")


async def post_shutdown(application):
    task = application.bot_data.get("scheduler_task")

    if task:
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass


def main():
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing."
        )

    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
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
        CommandHandler("addniche", add_niche_command)
    )

    application.add_handler(
        CommandHandler("research", research_command)
    )

    application.add_handler(
        CommandHandler("feed", feed_command)
    )

    logger.info("Crypto Intelligence Bot starting...")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()