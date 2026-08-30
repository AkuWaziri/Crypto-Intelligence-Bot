import asyncio
import logging
import os

import uvicorn
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, request, jsonify

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from config import TELEGRAM_BOT_TOKEN
from niches import get_niches, add_niche
from research import search_web
from writer import generate_intelligence, generate_content


logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

telegram_app = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .updater(None)
    .build()
)


HELP_TEXT = """
🧠 <b>Crypto Intelligence Bot</b>

Research crypto/Web3 and turn useful discoveries into content intelligence.

<b>Commands</b>

/start — start the bot
/help — show commands
/niches — show research niches
/research &lt;topic&gt; — research anything
/create &lt;request&gt; — research and create content
/addniche &lt;niche&gt; — add a research niche
/feed — run a fresh intelligence feed now

<b>Examples</b>

/research AI agents

/research crypto payments

/research suspicious smart contracts

/create Crypto GM post

/create write a GM post for today

/create explain AI agents simply

/create break down Binance Agent OS

/create give me a contrarian crypto idea

/create make a guide to using Base
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

    if not niches:
        await update.message.reply_text(
            "No research niches configured."
        )
        return

    text = "🧠 <b>RESEARCH NICHES</b>\n\n"

    for index, niche in enumerate(
        niches,
        start=1,
    ):
        text += f"{index}. {niche}\n"

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

    try:
        added = add_niche(niche)

        if added:
            await update.message.reply_text(
                f"✅ Added niche: {niche}"
            )
        else:
            await update.message.reply_text(
                "⚠️ That niche already exists "
                "or is invalid."
            )

    except Exception as exc:
        logger.exception(
            "Failed to add niche."
        )

        await update.message.reply_text(
            f"❌ Could not add niche.\n\n{exc}"
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

        if not research.get("results"):
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
                f"❌ Research failed.\n\n{exc}"
            )
        except Exception:
            await update.message.reply_text(
                f"❌ Research failed.\n\n{exc}"
            )


async def create_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/create <what you want to create>\n\n"
            "Examples:\n"
            "/create Crypto GM post\n"
            "/create write a GM post for today\n"
            "/create explain AI agents simply\n"
            "/create break down Binance Agent OS\n"
            "/create give me a contrarian crypto idea\n"
            "/create make a guide to using Base"
        )
        return

    request_text = " ".join(
        context.args
    ).strip()

    status = await update.message.reply_text(
        "✍️ Researching and creating your content..."
    )

    try:
        research = await asyncio.to_thread(
            search_web,
            request_text,
        )

        if not research:
            research = {
                "query": request_text,
                "results": [],
            }

        content = await asyncio.to_thread(
            generate_content,
            request_text,
            research,
        )

        if not content:
            raise RuntimeError(
                "No content was generated."
            )

        await status.delete()

        await send_message(
            update,
            content,
        )

    except Exception as exc:
        logger.exception(
            "Create failed."
        )

        try:
            await status.edit_text(
                f"❌ Create failed.\n\n{exc}"
            )
        except Exception:
            await update.message.reply_text(
                f"❌ Create failed.\n\n{exc}"
            )


async def feed_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    status = await update.message.reply_text(
        "🧠 Running a fresh intelligence feed..."
    )

    try:
        from scheduler import generate_feed

        reports = await generate_feed()

        await status.delete()

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

        try:
            await status.edit_text(
                f"❌ Feed failed.\n\n{exc}"
            )
        except Exception:
            await update.message.reply_text(
                f"❌ Feed failed.\n\n{exc}"
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

    for start in range(
        0,
        len(text),
        max_length,
    ):
        await update.message.reply_text(
            text[start:start + max_length]
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
            "create",
            create_command,
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
            "service": "crypto-intelligence-bot",
            "status": "ok",
        }
    )


@app.post("/telegram")
def telegram_webhook():
    data = request.get_json(
        force=True,
        silent=True,
    )

    if not data:
        return jsonify(
            {"status": "ignored"}
        )

    try:
        update = Update.de_json(
            data,
            telegram_app.bot,
        )

        telegram_app.update_queue.put_nowait(
            update
        )

        return jsonify(
            {"status": "ok"}
        )

    except Exception as exc:
        logger.exception(
            "Failed to queue Telegram update."
        )

        return jsonify(
            {
                "status": "error",
                "error": str(exc),
            }
        ), 500


async def startup():
    await telegram_app.initialize()

    await telegram_app.start()

    render_url = os.environ.get(
        "RENDER_EXTERNAL_URL"
    )

    if not render_url:
        raise RuntimeError(
            "RENDER_EXTERNAL_URL is not set."
        )

    webhook_url = (
        f"{render_url.rstrip('/')}"
        "/telegram"
    )

    await telegram_app.bot.set_webhook(
        url=webhook_url,
        allowed_updates=Update.ALL_TYPES,
    )

    logger.info(
        "Telegram webhook registered: %s",
        webhook_url,
    )


async def shutdown():
    try:
        await telegram_app.bot.delete_webhook()
    except Exception:
        logger.exception(
            "Failed to delete Telegram webhook."
        )

    try:
        await telegram_app.stop()
    except Exception:
        logger.exception(
            "Failed to stop Telegram application."
        )

    try:
        await telegram_app.shutdown()
    except Exception:
        logger.exception(
            "Failed to shutdown Telegram application."
        )


async def main():
    await startup()

    port = int(
        os.environ.get(
            "PORT",
            10000,
        )
    )

    asgi_app = WsgiToAsgi(app)

    config = uvicorn.Config(
        asgi_app,
        host="0.0.0.0",
        port=port,
        log_level="info",
    )

    server = uvicorn.Server(
        config
    )

    try:
        await server.serve()

    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())