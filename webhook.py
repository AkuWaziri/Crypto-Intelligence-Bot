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
from writer import (
    generate_intelligence,
    generate_content,
    generate_ideas,
    generate_creative_ideas,
)


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
/idea — discover creative content ideas
/ideas &lt;topic&gt; — legacy idea generator
/create &lt;request&gt; — research and create content
/addniche &lt;niche&gt; — add a research niche
/feed — run a fresh intelligence feed now

<b>Creative Ideas</b>

/idea give meme &lt;situation&gt;
/idea give me post ideas &lt;subject&gt;

<b>Examples</b>

/research AI agents

/research crypto payments

/research suspicious smart contracts

/idea give meme Elon replied to an unknown account and its token exploded

/idea give me post ideas Arc mainnet is on September 16 and what investors or degens should do before launch

/idea give me post ideas stablecoins

/idea give me post ideas AI agents

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


# ============================================================
# NEW CREATIVE IDEA COMMAND
# ============================================================

async def idea_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n\n"
            "/idea give meme <situation>\n"
            "/idea give me post ideas <subject>\n\n"
            "Examples:\n"
            "/idea give meme Elon replied to an unknown account and its token exploded\n\n"
            "/idea give me post ideas Arc mainnet is on September 16 and what investors should do before launch"
        )
        return

    raw_request = " ".join(
        context.args
    ).strip()

    lower_request = raw_request.lower()

    mode = None
    request_text = ""

    # --------------------------------------------------------
    # MEME MODE
    # --------------------------------------------------------

    if lower_request.startswith(
        "give meme"
    ):
        mode = "meme"

        request_text = raw_request[
            len("give meme"):
        ].strip()

    # --------------------------------------------------------
    # POST MODE
    # --------------------------------------------------------

    elif lower_request.startswith(
        "give me post ideas"
    ):
        mode = "post"

        request_text = raw_request[
            len("give me post ideas"):
        ].strip()

    elif lower_request.startswith(
        "give post ideas"
    ):
        mode = "post"

        request_text = raw_request[
            len("give post ideas"):
        ].strip()

    elif lower_request.startswith(
        "post ideas"
    ):
        mode = "post"

        request_text = raw_request[
            len("post ideas"):
        ].strip()

    # --------------------------------------------------------
    # INVALID MODE
    # --------------------------------------------------------

    if not mode:
        await update.message.reply_text(
            "I need to know what kind of idea you want.\n\n"
            "Use:\n"
            "/idea give meme <situation>\n"
            "/idea give me post ideas <subject>"
        )
        return

    if not request_text:
        await update.message.reply_text(
            "Give me the situation or subject after the command.\n\n"
            "Example:\n"
            "/idea give meme Elon replied to an unknown account and its token exploded"
        )
        return

    if mode == "meme":
        status_text = (
            "🎨 Researching the situation "
            "and exploring meme possibilities..."
        )
    else:
        status_text = (
            "💡 Researching the subject "
            "and exploring creative directions..."
        )

    status = await update.message.reply_text(
        status_text
    )

    try:
        # ----------------------------------------------------
        # BROADER RESEARCH FOR /idea
        # ----------------------------------------------------

        research = await asyncio.to_thread(
            search_web,
            request_text,
            8,
        )

        if not research.get("results"):
            await status.edit_text(
                "❌ I couldn't find enough useful "
                "research for this idea."
            )
            return

        # ----------------------------------------------------
        # CREATIVE ENGINE
        # ----------------------------------------------------

        ideas = await asyncio.to_thread(
            generate_creative_ideas,
            mode,
            request_text,
            research,
        )

        if not ideas:
            raise RuntimeError(
                "No creative ideas were generated."
            )

        await status.delete()

        await send_message(
            update,
            ideas,
        )

    except Exception as exc:
        logger.exception(
            "Creative idea generation failed."
        )

        try:
            await status.edit_text(
                f"❌ Idea generation failed.\n\n{exc}"
            )
        except Exception:
            await update.message.reply_text(
                f"❌ Idea generation failed.\n\n{exc}"
            )


# ============================================================
# LEGACY IDEAS COMMAND
# ============================================================

async def ideas_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/ideas <topic or subject>\n\n"
            "Examples:\n"
            "/ideas on Base\n"
            "/ideas on Arc\n"
            "/ideas on Uniswap\n"
            "/ideas on the Plum hack\n"
            "/ideas on stablecoins\n"
            "/ideas on Arc agentic economy\n"
            '/ideas on "we are so back"'
        )
        return

    request_text = " ".join(
        context.args
    ).strip()

    status = await update.message.reply_text(
        f"💡 Researching ideas:\n{request_text}"
    )

    try:
        research = await asyncio.to_thread(
            search_web,
            request_text,
        )

        if not research.get("results"):
            await status.edit_text(
                "❌ No useful research found "
                "for this subject."
            )
            return

        ideas = await asyncio.to_thread(
            generate_ideas,
            request_text,
            research,
        )

        if not ideas:
            raise RuntimeError(
                "No ideas were generated."
            )

        await status.delete()

        await send_message(
            update,
            ideas,
        )

    except Exception as exc:
        logger.exception(
            "Ideas generation failed."
        )

        try:
            await status.edit_text(
                f"❌ Ideas failed.\n\n{exc}"
            )
        except Exception:
            await update.message.reply_text(
                f"❌ Ideas failed.\n\n{exc}"
            )


# ============================================================
# CREATE
# ============================================================

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


# ============================================================
# FEED
# ============================================================

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


# ============================================================
# TELEGRAM MESSAGE SENDER
# ============================================================

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


# ============================================================
# HANDLERS
# ============================================================

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

    # New creative idea engine.
    telegram_app.add_handler(
        CommandHandler(
            "idea",
            idea_command,
        )
    )

    # Existing legacy idea engine.
    telegram_app.add_handler(
        CommandHandler(
            "ideas",
            ideas_command,
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


# ============================================================
# FLASK HEALTH CHECK
# ============================================================

@app.get("/")
def health():
    return jsonify(
        {
            "service": "crypto-intelligence-bot",
            "status": "ok",
        }
    )


# ============================================================
# TELEGRAM WEBHOOK
# ============================================================

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


# ============================================================
# STARTUP
# ============================================================

async def startup():
    await telegram_app.initialize()

    await telegram_app.start()

    render_url = os.environ.get(
        "RENDER_EXTERNAL_URL"
    )

    if render_url:
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

    else:
        logger.info(
            "RENDER_EXTERNAL_URL not set. "
            "Running without webhook registration "
            "for local testing."
        )


# ============================================================
# SHUTDOWN
# ============================================================

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


# ============================================================
# MAIN
# ============================================================

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