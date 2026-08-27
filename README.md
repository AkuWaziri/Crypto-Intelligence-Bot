# Crypto Intelligence Telegram Bot

A simple crypto/Web3 research bot that researches emerging developments and sends useful intelligence to Telegram.

## What it does

The bot researches:

- AI tools
- AI agents
- AI infrastructure
- AI + blockchain
- Crypto payments
- Airdrops
- Rewards
- Campaigns
- Claim opportunities
- Ending-soon opportunities
- Crypto opportunities
- New protocols
- New products
- Wallet movements
- Smart money
- Smart contracts
- Contract vulnerabilities
- Security issues
- Exploits
- Protocol updates
- New launches
- Emerging narratives
- Crypto infrastructure

It also accepts arbitrary research requests through Telegram.

## Telegram commands

/start

/help

/niches

/research <topic>

/addniche <niche>

/feed

Examples:

/research AI agents

/research crypto payments

/research new crypto opportunities

/research wallet movements

/research suspicious smart contracts

## Automatic feed

The bot automatically researches several niches periodically.

Default interval:

45 minutes

The interval can be changed with:

RESEARCH_INTERVAL_MINUTES

## Writing system

The writer uses:

writer_profile/examples.txt

writer_profile/patterns.txt

writer_profile/rules.txt

Add your own posts to examples.txt to progressively improve the writing style.

## Required environment variables

TELEGRAM_BOT_TOKEN

TELEGRAM_CHAT_ID

TAVILY_API_KEY

GEMINI_API_KEY

GEMINI_MODEL

## Local installation

Create a virtual environment:

python -m venv .venv

Activate it on Windows:

.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Create a .env file and add the required API keys.

Run:

python bot.py