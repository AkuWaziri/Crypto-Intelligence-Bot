import asyncio
import html
import logging
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from niches import get_niches, add_niche
from dynamic_engine import run_dynamic_task

logging.basicConfig(
    level=logging.INFO
)

logger = logging.getLogger(__name__)


async def send_long_message(
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


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    await update.message.reply_text(
        HELP_TEXT,
        parse_mode=ParseMode.HTML,
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
        parse_mode=ParseMode.HTML,
    )


async def add_niche_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/addniche &lt;niche&gt;"
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
            f"❌ Could not add niche.\n\n"
            f"{html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
        )


async def _run_adaptive_command(update, context, command, request_text=None):
    message = update.effective_message
    if not message:
        return

    request = (
        str(request_text).strip()
        if request_text is not None
        else " ".join(context.args or []).strip()
    )
    source_message = message.reply_to_message
    if source_message is None and message.photo:
        source_message = message

    context_parts = []
    image_bytes = None

    if source_message:
        source_text = source_message.text or source_message.caption or ""
        if source_text:
            context_parts.append(source_text.strip())

        photo = source_message.photo
        if photo:
            try:
                telegram_file = await context.bot.get_file(photo[-1].file_id)
                image_bytes = bytes(await telegram_file.download_as_bytearray())
            except Exception:
                logger.exception("Could not download the attached image.")
                await message.reply_text(
                    "I could read the message, but couldn't download its image. "
                    "Please resend the image or try again."
                )
                return

    # If the command was sent as a photo caption, strip the command itself from context.
    if message.photo and message.caption:
        caption = re.sub(r"^/\w+(?:@\w+)?\s*", "", message.caption).strip()
        if caption and caption not in context_parts:
            context_parts.append(caption)

    material = "\n\n".join(part for part in context_parts if part).strip()
    status_text = {
        "research": "🔎 Interpreting your request and researching relevant sources...",
        "idea": "🧠 Finding the real story and strongest angles...",
        "create": "✍️ Working out the best format, researching, and creating...",
        "generate": "🎨 Interpreting the request and building the output...",
    }.get(command, "🧠 Working on it...")
    status = await message.reply_text(status_text)

    try:
        output = await asyncio.to_thread(
            run_dynamic_task,
            command,
            request,
            material,
            image_bytes,
        )
        try:
            await status.delete()
        except Exception:
            pass
        await send_long_message(update, output)
    except Exception as exc:
        logger.exception("Adaptive /%s task failed.", command)
        error_text = html.escape(str(exc))
        try:
            await status.edit_text(
                f"❌ {command.capitalize()} failed.\n\n{error_text}",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            await message.reply_text(
                f"❌ {command.capitalize()} failed.\n\n{error_text}",
                parse_mode=ParseMode.HTML,
            )


async def research_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_adaptive_command(update, context, "research")


async def idea_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_adaptive_command(update, context, "idea")


async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_adaptive_command(update, context, "create")


async def generate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _run_adaptive_command(update, context, "generate")


async def photo_caption_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Support commands written directly in a photo caption."""
    message = update.effective_message
    if not message or not message.photo or not message.caption:
        return
    match = re.match(r"^/(idea|create|generate|research)(?:@\w+)?(?:\s+(.*))?$", message.caption.strip(), re.I | re.S)
    if not match:
        return
    command = match.group(1).lower()
    request = (match.group(2) or "").strip()
    await _run_adaptive_command(update, context, command, request_text=request)


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
            await send_long_message(
                update,
                report,
            )

    except Exception as exc:
        logger.exception(
            "Manual feed failed."
        )

        await update.message.reply_text(
            f"❌ Feed failed.\n\n"
            f"{html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
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

    telegram_app.add_handler(CommandHandler("research", research_command))
    telegram_app.add_handler(CommandHandler("idea", idea_command))
    telegram_app.add_handler(CommandHandler("create", create_command))
    telegram_app.add_handler(CommandHandler("generate", generate_command))
    telegram_app.add_handler(
        MessageHandler(filters.PHOTO & filters.CAPTION, photo_caption_command)
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


HELP_TEXT = """
🧠 <b>Crypto Intelligence Bot</b>

Research crypto/Web3 and create content from your creator profile.

<b>Commands</b>

/start — start the bot
/help — show commands
/niches — show research niches
/research &lt;request&gt; — investigate a topic, post, claim, or screenshot
/idea &lt;request&gt; — discover angles, ideas, or investigate a post
/create &lt;request&gt; — create content, findings, rewrites, or analysis
/generate &lt;request&gt; — generate a requested artifact, including ASCII banners
/addniche &lt;niche&gt; — add a research niche
/feed — run a fresh intelligence feed now

<b>Use natural language</b>

Reply to a post or screenshot with a command, or attach a screenshot with the command in its caption.

/idea find other content angles from this post
/idea what's really happening underneath this post?
/create recreate this post as a discovery with evidence
/create analyse this post and explain the mechanism
/research investigate this claim and find primary sources
/generate make a polished ASCII banner about stablecoin payments
"""

telegram_app = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .build()
)

setup_handlers()


async def scheduler_sender(
    text: str,
):
    if not TELEGRAM_CHAT_ID:
        logger.error(
            "TELEGRAM_CHAT_ID is missing."
        )
        return

    await telegram_app.bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
    )


async def post_init(
    application: Application,
):
    logger.info(
        "Telegram application initialized."
    )


async def post_shutdown(
    application: Application,
):
    logger.info(
        "Telegram application shutting down."
    )
