import asyncio
import logging
import os
import re

import uvicorn
from asgiref.wsgi import WsgiToAsgi
from flask import Flask, request, jsonify

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

from config import TELEGRAM_BOT_TOKEN
from niches import get_niches, add_niche
from research import search_web
from writer import generate_intelligence, generate_content, generate_ideas, generate_creative_ideas
from vision import analyze_image
from research_output import format_research_output

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).updater(None).build()

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

<b>Image support</b>
Attach an image with /research, /idea, /ideas or /create in the caption.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(HELP_TEXT, parse_mode="HTML")

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
    niche = " ".join(context.args).strip()
    try:
        added = add_niche(niche)
        await update.message.reply_text(f"✅ Added niche: {niche}" if added else "⚠️ That niche already exists or is invalid.")
    except Exception as exc:
        logger.exception("Failed to add niche.")
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
        logger.exception("Research failed.")
        try:
            await status.edit_text(f"❌ Research failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Research failed.\n\n{exc}")

async def idea_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("Usage:\n\n/idea give meme <situation>\n/idea give me post ideas <subject>")
        return
    raw_request = " ".join(context.args).strip()
    lower_request = raw_request.lower()
    mode = None
    request_text = ""
    if lower_request.startswith("give meme"):
        mode, request_text = "meme", raw_request[len("give meme"):].strip()
    elif lower_request.startswith("give me post ideas"):
        mode, request_text = "post", raw_request[len("give me post ideas"):].strip()
    elif lower_request.startswith("give post ideas"):
        mode, request_text = "post", raw_request[len("give post ideas"):].strip()
    elif lower_request.startswith("post ideas"):
        mode, request_text = "post", raw_request[len("post ideas"):].strip()
    if not mode or not request_text:
        await update.message.reply_text("Use:\n/idea give meme <situation>\n/idea give me post ideas <subject>")
        return
    status = await update.message.reply_text("🎨 Researching the situation and exploring meme possibilities..." if mode == "meme" else "💡 Researching the subject and exploring creative directions...")
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
        logger.exception("Creative idea generation failed.")
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
        logger.exception("Ideas generation failed.")
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
        logger.exception("Create failed.")
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
        logger.exception("Manual feed failed.")
        try:
            await status.edit_text(f"❌ Feed failed.\n\n{exc}")
        except Exception:
            await update.message.reply_text(f"❌ Feed failed.\n\n{exc}")

async def send_message(update: Update, text: str):
    if not update.message or not text:
        return
    for start in range(0, len(text), 3900):
        await update.message.reply_text(text[start:start + 3900])

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.photo or not message.caption:
        return
    caption = message.caption.strip()
    match = re.match(r"^/(research|idea|ideas|create)(?:@\w+)?(?:\s+(.*))?$", caption, re.IGNORECASE | re.DOTALL)
    if not match:
        return
    command = match.group(1).lower()
    user_instruction = (match.group(2) or "").strip()
    status = await message.reply_text("🖼️ Reading the image and understanding your request...")
    try:
        photo = message.photo[-1]
        telegram_file = await photo.get_file()
        image_bytes = bytes(await telegram_file.download_as_bytearray())
        visual_context = await asyncio.to_thread(analyze_image, image_bytes, user_instruction)
        if not visual_context:
            raise RuntimeError("The image could not be understood.")
        combined_request = f"USER REQUEST:\n{user_instruction or 'Determine what matters in this image.'}\n\nVISUAL EVIDENCE FROM IMAGE:\n{visual_context}\n\nTreat the visual evidence as input to investigate. Verify factual claims through research."
        if command == "research":
            research = await asyncio.to_thread(search_web, combined_request)
            if not research.get("results"):
                await status.edit_text("❌ No useful crypto/Web3 research found from the image and request.")
                return
            intelligence = await asyncio.to_thread(generate_intelligence, research, "image-assisted manual research")
            intelligence = format_research_output(intelligence)
            await status.delete()
            await send_message(update, intelligence)
            return
        if command == "create":
            research = await asyncio.to_thread(search_web, combined_request)
            if not research:
                research = {"query": combined_request, "results": []}
            content = await asyncio.to_thread(generate_content, user_instruction or "Create the most useful crypto content based on what is shown in this image.", research)
            if not content:
                raise RuntimeError("No content was generated.")
            await status.delete()
            await send_message(update, content)
            return
        if command == "ideas":
            research = await asyncio.to_thread(search_web, combined_request)
            if not research.get("results"):
                await status.edit_text("❌ No useful research found for the image.")
                return
            ideas = await asyncio.to_thread(generate_ideas, user_instruction or "Generate useful crypto content ideas from this image.", research)
            if not ideas:
                raise RuntimeError("No ideas were generated.")
            await status.delete()
            await send_message(update, ideas)
            return
        lower_request = user_instruction.lower()
        if lower_request.startswith("give meme"):
            mode, idea_request = "meme", user_instruction[len("give meme"):].strip()
        elif lower_request.startswith("give me post ideas"):
            mode, idea_request = "post", user_instruction[len("give me post ideas"):].strip()
        elif lower_request.startswith("give post ideas"):
            mode, idea_request = "post", user_instruction[len("give post ideas"):].strip()
        elif lower_request.startswith("post ideas"):
            mode, idea_request = "post", user_instruction[len("post ideas"):].strip()
        else:
            await status.edit_text("Use /idea give meme <situation> or /idea give me post ideas <subject>.")
            return
        research = await asyncio.to_thread(search_web, combined_request, 8)
        if not research.get("results"):
            research = {"query": combined_request, "answer": "", "results": []}
        ideas = await asyncio.to_thread(generate_creative_ideas, mode, idea_request or user_instruction, research)
        if not ideas:
            raise RuntimeError("No creative ideas were generated.")
        await status.delete()
        await send_message(update, ideas)
    except Exception as exc:
        logger.exception("Image command failed.")
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

@app.post("/webhook")
def webhook():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"ok": False}), 400
    async def process_update():
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
    asyncio.run(process_update())
    return jsonify({"ok": True})

asgi_app = WsgiToAsgi(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(asgi_app, host="0.0.0.0", port=port)
