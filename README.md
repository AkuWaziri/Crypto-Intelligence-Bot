# Crypto Intelligence Telegram Bot

An adaptive crypto/Web3 research and creator assistant. Commands accept natural language instead of forcing you to learn rigid subcommands. The bot interprets the request, checks attached or replied-to material, decides whether fresh research is useful, searches relevant sources, and chooses an output format that matches the task.

## Adaptive commands

- `/research <request>` — investigate a topic, claim, post, screenshot, protocol, or opportunity.
- `/idea <request>` — discover different content angles, investigate what is really happening, or find the strongest story inside a post.
- `/create <request>` — write a discovery, analysis, rewrite, explainer, guide, or other requested content.
- `/generate <request>` — create the requested artifact, including text-based ASCII/Unicode banners and diagrams.
- `/feed` — run the scheduled intelligence feed manually.
- `/niches` — list configured research niches.
- `/addniche <niche>` — add a research niche.
- `/start`, `/help` — show bot help.

The command is a hint, not a fixed template. The bot uses the full sentence to infer the actual task.

### Example requests

```text
/idea find other content categories hidden in this post
/idea what's really happening underneath this post?
/idea find the overlooked mechanism and the strongest evidence
/create recreate this post as a discovery, not a news summary
/create analyse this post and explain the mechanism
/create turn these findings into a concise thread
/research investigate this claim and find primary sources
/generate make a polished ASCII banner about stablecoin payments
/generate draw a terminal-style flow diagram showing how this protocol works
```

### Use attached posts and screenshots

1. Send a post or screenshot, then reply to it with a command such as `/idea what's the real story here?`.
2. Alternatively, attach a screenshot and put the command in its caption.
3. The bot extracts visible context, searches the underlying subject when useful, and distinguishes source evidence from interpretation.

Images are analysed with the configured vision model. Research-led answers include real source links when available. The bot should state uncertainty rather than invent missing evidence.

Note: Telegram text cannot apply arbitrary font colours to plain text. ASCII/Unicode banners can use box-drawing characters, aligned rules, and coloured-block symbols to create a polished terminal-style look.

## Research coverage

The research engine searches across emerging AI tools and agents, AI infrastructure, AI + blockchain, crypto payments, airdrops and rewards, claim opportunities, new protocols and products, wallet movements, smart money, smart contracts, vulnerabilities, exploits, protocol updates, launches, emerging narratives, and crypto infrastructure.

## Automatic feed

The automatic research feed runs periodically. The default interval is controlled by `RESEARCH_INTERVAL_MINUTES`.

## Creator writing profile

The writer uses:

- `writer_profile/examples.txt`
- `writer_profile/patterns.txt`
- `writer_profile/rules.txt`

Add approved writing examples to the profile files to improve the fit of generated content.

## Environment variables

Required for core operation:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID` (for scheduled feed delivery)
- `GROQ_API_KEY` (for language and image analysis)

Configure the model names and research settings through the existing environment variables in `config.py`, `vision.py`, and `image_generator.py`.

## Local installation

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```
