import asyncio
import logging
import os

from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN
from niches import get_niches, add_niche
from research import search_web
from writer import generate_intelligence


logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)


telegram_app = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)


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

<b>EXAMPLES</b>

/research AI agents

/research crypto payments

/research suspicious smart contracts

/research wallets moving BTC

/research new crypto opportunities

/research airdrops ending soon
"""


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="HTML",
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="HTML",
    )


async def niches_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    niches = get_niches()

    text = "🧠 <b>RESEARCH NICHES</b>\n\n"

    for index, niche in enumerate(
        niches,
        start=1,
    ):
        text += (
            f"{index}. {niche}\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="HTML",
    )


async def add_niche_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addniche <niche>"
        )
        return

    niche = " ".join(
        context.args
    ).strip()

    if add_niche(niche):
        await update.message.reply_text(
            f"✅ Added niche: {niche}"
        )
    else:
        await update.message.reply_text(
            "⚠️ That niche already exists "
            "or is invalid."
        )


async def research_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/research <topic>\n\n"
            "Example:\n"
            "/research AI agents"
        )
        return

    query = " ".join(
        context.args
    ).strip()

    status = await update.message.reply_text(
        f"🔎 Researching:\n{query}"
    )

    try:
        research = await asyncio.to_thread(
            search_web,
            query,
        )

        if not research.get(
            "results"
        ):
            await status.edit_text(
                "❌ No useful crypto/Web3 "
                "results found."
            )
            return

        intelligence = await asyncio.to_thread(
            generate_intelligence,
            research,
            "manual research",
        )

        await status.delete()

        await send_message(
            update,
            intelligence,
        )

    except Exception as exc:
        logger.exception(
            "Research failed."
        )

        try:
            await status.edit_text(
                "❌ Research failed.\n\n"
                f"{str(exc)}"
            )
        except Exception:
            await update.message.reply_text(
                "❌ Research failed."
            )


async def feed_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        "🧠 Running a fresh intelligence feed..."
    )

    try:
        from scheduler import generate_feed

        reports = await generate_feed()

        if not reports:
            await update.message.reply_text(
                "No useful discoveries "
                "found this cycle."
            )
            return

        for report in reports:
            await send_message(
                update,
                report,
            )

    except Exception as exc:
        logger.exception(
            "Manual feed failed."
        )

        await update.message.reply_text(
            "❌ Feed failed.\n\n"
            f"{str(exc)}"
        )


async def send_message(
    update: Update,
    text: str,
):
    if not update.message:
        return

    if not text:
        return

    max_length = 3900

    if len(text) <= max_length:
        await update.message.reply_text(
            text
        )
        return

    for start in range(
        0,
        len(text),
        max_length,
    ):
        await update.message.reply_text(
            text[
                start:start + max_length
            ]
        )


def setup_handlers():
    telegram_app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "niches",
            niches_command,
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "research",
            research_command,
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "addniche",
            add_niche_command,
        )
    )

    telegram_app.add_handler(
        CommandHandler(
            "feed",
            feed_command,
        )
    )


setup_handlers()


@app.get("/")
def health():
    return jsonify(
        {
            "status": "ok",
            "service": (
                "crypto-intelligence-bot"
            ),
        }
    )


@app.post("/telegram")
async def telegram_webhook():
    data = request.get_json(
        force=True,
        silent=True,
    )

    if not data:
        return jsonify(
            {"status": "ignored"}
        )

    bot = Bot(
        TELEGRAM_BOT_TOKEN
    )

    update = (
        Update.de_json(
            data,
            bot,
        )
    )

    await telegram_app.process_update(
        update
    )

    return jsonify(
        {"status": "ok"}
    )


if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            10000,
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
    )