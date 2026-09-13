import asyncio
import logging
import os
import re

import uvicorn
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, jsonify, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from niches import add_niche, get_niches
from research import search_web
from research_output import format_research_output
from vision import analyze_image
from writer import generate_content, generate_creative_ideas, generate_ideas, generate_intelligence

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
MAIN_LOOP = None

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

HELP_TEXT = """
🧠 <b>Crypto Intelligence Bot</b>

/research &lt;topic&gt; — research anything
/idea give meme &lt;situation&gt; — create meme ideas
/idea give me post ideas &lt;subject&gt; — create post ideas
/ideas &lt;topic&gt; — legacy idea generator
/create &lt;request&gt; — research and create content
/niches — show research niches
/addniche &lt;niche&gt; — add a research niche
/feed — run a fresh intelligence feed

Attach an image with /research, /idea, /ideas or /create in the caption for image-assisted processing.
"""


async def send_message(update: Update, text: str):
    if not update.message or not text:
        return
    for start in range(0, len(text), 3900):
        await update.message.reply_text(text[start:start + 3900])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def niches_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    niches = get_niches()
    if not niches:
        await update.message.reply_text("No research niches configured.")
        return
    text = "🧠 <b>RESEARCH NICHES</b>\n\n" + "".join(f"{i}. {n}\n" for i, n in enumerate(niches, 1))
    await update.message.reply_text(text, parse_mode="HTML")


async def add_niche_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/addniche <niche>")
        return
    try:
        niche = " ".join(context.args).strip()
        added = add_niche(niche)
        await update.message.reply_text(
            f"✅ Added niche: {niche}" if added else "⚠️ That niche already exists or is invalid."
        )
    except Exception as exc:
        logger.exception("Failed to add niche")
        await update.message.reply_text(f"❌ Could not add niche.\n\n{exc}")


async def research_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/research <topic>\n\nExample:\n/research AI agents")
        return
    query = " ".join(context.args).strip()
    status = await update.message.reply_text(f"🔎 Researching:\n{query}")
    try:
        research = await asyncio.to_thread(search_web, query)
        if not research.get("results"):
            await status.edit_text("❌ No useful crypto/Web3 results found.")
            return
        intelligence = await asyncio.to_thread(generate_intelligence, research, "manual research")
        intelligence = format_research_output(intelligence)
        await status.delete()
        await send_message(update, intelligence)
    except Exception as exc:
        logger.exception("Research failed")
        try:
            await status.edit_text(f"❌ Research failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Research failed.\n\n{exc}")


async def idea_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text(
            "Usage:\n/idea give meme <situation>\n/idea give me post ideas <subject>"
        )
        return
    raw = " ".join(context.args).strip()
    lower = raw.lower()
    if lower.startswith("give meme"):
        mode, request_text = "meme", raw[len("give meme"):].strip()
    elif lower.startswith("give me post ideas"):
        mode, request_text = "post", raw[len("give me post ideas"):].strip()
    elif lower.startswith("give post ideas"):
        mode, request_text = "post", raw[len("give post ideas"):].strip()
    elif lower.startswith("post ideas"):
        mode, request_text = "post", raw[len("post ideas"):].strip()
    else:
        await update.message.reply_text("Use /idea give meme <situation> or /idea give me post ideas <subject>.")
        return
    if not request_text:
        await update.message.reply_text("Give me the situation or subject after the command.")
        return
    status = await update.message.reply_text(
        "🎨 Researching the situation and exploring meme possibilities..."
        if mode == "meme" else "💡 Researching the subject and exploring creative directions..."
    )
    try:
        research = await asyncio.to_thread(search_web, request_text, 8)
        if not research.get("results"):
            research = {"query": request_text, "answer": "", "results": []}
        ideas = await asyncio.to_thread(generate_creative_ideas, mode, request_text, research)
        if not ideas:
            raise RuntimeError("No creative ideas were generated.")
        await status.delete()
        await send_message(update, ideas)
    except Exception as exc:
        logger.exception("Creative idea generation failed")
        try:
            await status.edit_text(f"❌ Idea generation failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Idea generation failed.\n\n{exc}")


async def ideas_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/ideas <topic or subject>")
        return
    request_text = " ".join(context.args).strip()
    status = await update.message.reply_text(f"💡 Researching ideas:\n{request_text}")
    try:
        research = await asyncio.to_thread(search_web, request_text)
        if not research.get("results"):
            await status.edit_text("❌ No useful research found for this subject.")
            return
        ideas = await asyncio.to_thread(generate_ideas, request_text, research)
        if not ideas:
            raise RuntimeError("No ideas were generated.")
        await status.delete()
        await send_message(update, ideas)
    except Exception as exc:
        logger.exception("Ideas generation failed")
        try:
            await status.edit_text(f"❌ Ideas failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Ideas failed.\n\n{exc}")


async def create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage:\n/create <what you want to create>")
        return
    request_text = " ".join(context.args).strip()
    status = await update.message.reply_text("✍️ Researching and creating your content...")
    try:
        research = await asyncio.to_thread(search_web, request_text)
        if not research:
            research = {"query": request_text, "results": []}
        content = await asyncio.to_thread(generate_content, request_text, research)
        if not content:
            raise RuntimeError("No content was generated.")
        await status.delete()
        await send_message(update, content)
    except Exception as exc:
        logger.exception("Create failed")
        try:
            await status.edit_text(f"❌ Create failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Create failed.\n\n{exc}")


async def feed_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    status = await update.message.reply_text("🧠 Running a fresh intelligence feed...")
    try:
        from scheduler import generate_feed
        reports = await generate_feed()
        await status.delete()
        if not reports:
            await update.message.reply_text("No useful discoveries found this cycle.")
            return
        for report in reports:
            await send_message(update, report)
    except Exception as exc:
        logger.exception("Manual feed failed")
        try:
            await status.edit_text(f"❌ Feed failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Feed failed.\n\n{exc}")


async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.photo or not message.caption:
        return
    match = re.match(
        r"^/(research|idea|ideas|create)(?:@\w+)?(?:\s+(.*))?$",
        message.caption.strip(), re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return
    command = match.group(1).lower()
    instruction = (match.group(2) or "").strip()
    status = await message.reply_text("🖼️ Reading the image and understanding your request...")
    try:
        telegram_file = await message.photo[-1].get_file()
        image_bytes = bytes(await telegram_file.download_as_bytearray())
        visual = await asyncio.to_thread(analyze_image, image_bytes, instruction)
        if not visual:
            raise RuntimeError("The image could not be understood.")
        combined = (
            f"USER REQUEST:\n{instruction or 'Determine what matters in this image.'}\n\n"
            f"VISUAL EVIDENCE FROM IMAGE:\n{visual}\n\n"
            "Treat the visual evidence as input to investigate. Verify factual claims through research."
        )
        if command == "research":
            research = await asyncio.to_thread(search_web, combined)
            if not research.get("results"):
                await status.edit_text("❌ No useful crypto/Web3 research found from the image and request.")
                return
            intelligence = await asyncio.to_thread(generate_intelligence, research, "image-assisted manual research")
            intelligence = format_research_output(intelligence)
            await status.delete()
            await send_message(update, intelligence)
            return
        if command == "create":
            research = await asyncio.to_thread(search_web, combined)
            content = await asyncio.to_thread(
                generate_content,
                instruction or "Create the most useful crypto content based on this image.",
                research or {"query": combined, "results": []},
            )
            if not content:
                raise RuntimeError("No content was generated.")
            await status.delete()
            await send_message(update, content)
            return
        if command == "ideas":
            research = await asyncio.to_thread(search_web, combined)
            if not research.get("results"):
                await status.edit_text("❌ No useful research found for the image.")
                return
            ideas = await asyncio.to_thread(generate_ideas, instruction or "Generate useful crypto content ideas from this image.", research)
            if not ideas:
                raise RuntimeError("No ideas were generated.")
            await status.delete()
            await send_message(update, ideas)
            return
        lower = instruction.lower()
        if lower.startswith("give meme"):
            mode, idea_request = "meme", instruction[len("give meme"):].strip()
        elif lower.startswith("give me post ideas"):
            mode, idea_request = "post", instruction[len("give me post ideas"):].strip()
        elif lower.startswith("give post ideas"):
            mode, idea_request = "post", instruction[len("give post ideas"):].strip()
        elif lower.startswith("post ideas"):
            mode, idea_request = "post", instruction[len("post ideas"):].strip()
        else:
            await status.edit_text("Use /idea give meme <situation> or /idea give me post ideas <subject>.")
            return
        research = await asyncio.to_thread(search_web, combined, 8)
        if not research.get("results"):
            research = {"query": combined, "answer": "", "results": []}
        ideas = await asyncio.to_thread(generate_creative_ideas, mode, idea_request or instruction, research)
        if not ideas:
            raise RuntimeError("No creative ideas were generated.")
        await status.delete()
        await send_message(update, ideas)
    except Exception as exc:
        logger.exception("Image command failed")
        try:
            await status.edit_text(f"❌ Image command failed.\n\n{exc}")
        except Exception:
            await message.reply_text(f"❌ Image command failed.\n\n{exc}")


telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("help", help_command))
telegram_app.add_handler(CommandHandler("niches", niches_command))
telegram_app.add_handler(CommandHandler("research", research_command))
telegram_app.add_handler(CommandHandler("idea", idea_command))
telegram_app.add_handler(CommandHandler("ideas", ideas_command))
telegram_app.add_handler(CommandHandler("create", create_command))
telegram_app.add_handler(CommandHandler("addniche", add_niche_command))
telegram_app.add_handler(CommandHandler("feed", feed_command))
telegram_app.add_handler(MessageHandler(filters.PHOTO & filters.CAPTION, image_command))


@app.get("/health")
def health():
    return jsonify({"ok": True, "telegram_initialized": MAIN_LOOP is not None})


@app.post("/webhook")
def webhook():
    if MAIN_LOOP is None:
        return jsonify({"ok": False, "error": "telegram application is not running"}), 503
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"ok": False}), 400
    try:
        update = Update.de_json(data, telegram_app.bot)
        future = asyncio.run_coroutine_threadsafe(
            telegram_app.update_queue.put(update),
            MAIN_LOOP,
        )
        future.result(timeout=5)
        return jsonify({"ok": True})
    except Exception as exc:
        logger.exception("Webhook update failed")
        return jsonify({"ok": False, "error": str(exc)}), 500


asgi_app = WsgiToAsgi(app)


async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip().rstrip("/")
    if webhook_url:
        await telegram_app.bot.set_webhook(url=f"{webhook_url}/webhook", allowed_updates=Update.ALL_TYPES)
        logger.info("Telegram webhook configured: %s/webhook", webhook_url)
    config = uvicorn.Config(asgi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), log_level="info")
    server = uvicorn.Server(config)
    async with telegram_app:
        await telegram_app.start()
        logger.info("Telegram application started")
        try:
            await server.serve()
        finally:
            await telegram_app.stop()
            MAIN_LOOP = None


if __name__ == "__main__":
    asyncio.run(main())
