import os

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from writer import build_research_text, load_writer_profile

FEED_MAX_OUTPUT_TOKENS = 260
FEED_MAX_CHARACTERS = 500


def _fit_feed(text):
    text = (text or "").strip()
    if len(text) <= FEED_MAX_CHARACTERS:
        return text
    clipped = text[:FEED_MAX_CHARACTERS].rstrip()
    cut = max(clipped.rfind("\n"), clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if cut >= 300:
        return clipped[:cut + 1].strip()
    return clipped.rstrip(" ,;:-")


def generate_feed_intelligence(research):
    """Generate a compact feed capped at 500 characters."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    writer_profile = load_writer_profile()
    research_text = build_research_text(research, max_results=5, max_content_chars=500)

    prompt = f"""
You are the intelligence editor behind a distinctive crypto creator.

FINAL OUTPUT MUST BE 500 CHARACTERS OR FEWER, INCLUDING SPACES.

CREATOR DNA
===========
{writer_profile}

RESEARCH
========
{research_text}

PRIORITY
========
CONTENT OPPORTUNITIES and RABBIT HOLES are the main value of this feed.

CONTENT OPPORTUNITIES:
Give 1–2 useful angles. Each must say what could be explored and why it matters. Never reduce an angle to a title.

RABBIT HOLES:
Give 1–2 investigation paths. Each must identify the deeper question or missing evidence and why it matters. Never give vague questions.

If space is tight, shorten these sections but never replace them with summary sections. Only add a tiny SIGNAL if room remains.

RULES
=====
- HARD LIMIT: 500 CHARACTERS TOTAL.
- Count characters before answering.
- Never exceed 500 characters.
- Never truncate a sentence or bullet.
- Dense, plain language.
- No introduction or conclusion.
- No generic commentary.
- Facts must be supported by research.
- Never invent facts.
- Return ONLY the final feed text.
""".strip()

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.55,
        max_tokens=FEED_MAX_OUTPUT_TOKENS,
        messages=[
            {
                "role": "system",
                "content": "You are a sharp crypto intelligence editor. Never exceed 500 characters in the final answer.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    return _fit_feed(response.choices[0].message.content or "")
