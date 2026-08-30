import asyncio
import html
import logging

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
from writer import generate_intelligence, generate_content

logging.basicConfig(
level=logging.INFO
)

logger = logging.getLogger(**name**)

async def send_long_message(
update: Update,
text: str,
):
if not update.message:
return

```
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
```

async def start(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
await update.message.reply_text(
    HELP_TEXT,
    parse_mode=ParseMode.HTML,
)
```

async def help_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
await update.message.reply_text(
    HELP_TEXT,
    parse_mode=ParseMode.HTML,
)
```

async def niches_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
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
```

async def add_niche_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
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
        f"❌ Could not add niche.\n\n"
        f"{html.escape(str(exc))}",
        parse_mode=ParseMode.HTML,
    )
```

async def research_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
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

    await send_long_message(
        update,
        intelligence,
    )

except Exception as exc:
    logger.exception(
        "Research failed."
    )

    error_text = html.escape(
        str(exc)
    )

    try:
        await status.edit_text(
            f"❌ Research failed.\n\n"
            f"{error_text}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await update.message.reply_text(
            f"❌ Research failed.\n\n"
            f"{error_text}",
            parse_mode=ParseMode.HTML,
        )
```

async def create_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
if not context.args:
    await update.message.reply_text(
        "Usage:\n"
        "/create <what you want to create>\n\n"
        "Examples:\n"
        "/create Crypto GM post\n"
        "/create Monday GM post\n"
        "/create funny post about CT\n"
        "/create bullish post about AI agents\n"
        "/create post about today's BTC move\n"
        "/create explain the latest Base development"
    )
    return

request = " ".join(
    context.args
).strip()

status = await update.message.reply_text(
    "✍️ Creating your post..."
)

try:
    content = await asyncio.to_thread(
        generate_content,
        request,
    )

    if not content:
        await status.edit_text(
            "❌ I couldn't create the requested content."
        )
        return

    await status.delete()

    await send_long_message(
        update,
        content,
    )

except Exception as exc:
    logger.exception(
        "Create failed."
    )

    error_text = html.escape(
        str(exc)
    )

    try:
        await status.edit_text(
            "❌ Create failed.\n\n"
            f"{error_text}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await update.message.reply_text(
            "❌ Create failed.\n\n"
            f"{error_text}",
            parse_mode=ParseMode.HTML,
        )
```

async def feed_command(
update: Update,
context: ContextTypes.DEFAULT_TYPE,
):
if not update.message:
return

```
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
```

def setup_handlers():
telegram_app.add_handler(
CommandHandler(
"start",
start,
)
)

```
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
```

HELP_TEXT = """
🧠 <b>Crypto Intelligence Bot</b>

Research crypto/Web3 and create content from your creator profile.

<b>Commands</b>

/start — start the bot
/help — show commands
/niches — show research niches
/research <topic> — research anything
/create <request> — create ready-to-post content
/addniche <niche> — add a research niche
/feed — run a fresh intelligence feed now

<b>Create examples</b>

/create Crypto GM post

/create Monday GM post

/create funny post about CT

/create bullish post about AI agents

/create post about today's BTC move

/create explain the latest Base development

<b>Research examples</b>

/research AI agents

/research crypto payments

/research suspicious smart contracts

/research wallets moving BTC
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

```
await telegram_app.bot.send_message(
    chat_id=TELEGRAM_CHAT_ID,
    text=text,
)
```

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
