import os
import logging

from groq import Groq

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    WRITER_PROFILE_DIR,
    MIN_DRAFT_CHARACTERS,
    MAX_DRAFT_CHARACTERS,
)

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


def read_profile_file(filename: str) -> str:
    path = os.path.join(WRITER_PROFILE_DIR, filename)

    if not os.path.exists(path):
        return ""

    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception:
        logger.exception("Could not read writer profile file.")
        return ""


def load_writer_profile():
    return {
        "examples": read_profile_file("examples.txt"),
        "patterns": read_profile_file("patterns.txt"),
        "rules": read_profile_file("rules.txt"),
    }


def build_prompt(research, request_type="feed"):
    profile = load_writer_profile()

    sources = []

    for index, result in enumerate(
        research.get("results", []),
        start=1
    ):
        sources.append(
            f"SOURCE {index}\n"
            f"{result.get('title', '')}\n"
            f"{result.get('content', '')[:1500]}"
        )

    sources_text = "\n\n".join(sources)

    return f"""
You are an intelligent crypto research and content intelligence assistant.

Your job is NOT simply to summarize news.

Find things that could become useful crypto content.

Look for:

- new tools
- AI agents
- AI infrastructure
- crypto payments
- airdrops
- rewards
- campaigns
- claim opportunities
- ending-soon opportunities
- new protocols
- new products
- wallet movements
- smart-money activity
- suspicious contracts
- security issues
- exploits
- protocol updates
- new launches
- emerging narratives
- unusual developments
- things worth testing
- things worth investigating
- things the creator could build
- opportunities that other creators may have missed

Never invent facts.

Only make factual claims supported by the supplied research.

If something is uncertain, clearly say so.

WRITER PROFILE

PATTERNS:
{profile["patterns"]}

RULES:
{profile["rules"]}

EXAMPLES:
{profile["examples"]}

RESEARCH QUERY:
{research.get("query", "")}

RESEARCH RESULTS:
{sources_text}

Return exactly these sections:

CATEGORY:
<best category>

WHAT HAPPENED:
<clear explanation>

WHY IT MATTERS:
<why this is interesting>

CONTENT ANGLE:
<what the creator could post, test, investigate or build>

DRAFT:
Write a natural crypto social-media draft.

The draft MUST be between
{MIN_DRAFT_CHARACTERS} and {MAX_DRAFT_CHARACTERS} characters.

Do not write a generic news summary.

Do not begin with:
"Here's an interesting..."
"According to..."
"Breaking..."
"Today I discovered..."

Do not invent personal experiences.

Do not claim the creator personally tested something unless the research proves it.

SOURCES:
<source URLs>

REQUEST TYPE:
{request_type}
"""


def generate_intelligence(research, request_type="feed"):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    prompt = build_prompt(
        research,
        request_type=request_type,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.7,
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise crypto research "
                    "and content intelligence assistant."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    text = response.choices[0].message.content.strip()

    if len(text) < 100:
        raise RuntimeError(
            "Groq returned an unexpectedly short response."
        )

    sources = []

    for result in research.get("results", []):
        url = result.get("url", "").strip()

        if url and url not in sources:
            sources.append(url)

    if sources:
        text += "\n\nSOURCES\n"

        for index, url in enumerate(sources, start=1):
            text += f"{index}. {url}\n"

    return text