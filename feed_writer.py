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
    cut = max(
        clipped.rfind("\n"),
        clipped.rfind("."),
        clipped.rfind("!"),
        clipped.rfind("?"),
    )
    if cut >= 300:
        return clipped[:cut + 1].strip()
    return clipped.rstrip(" ,;:-")


def generate_feed_intelligence(research):
    """Generate one compact, non-repetitive feed from one or more candidates."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    writer_profile = load_writer_profile()

    if isinstance(research, list):
        research_text = "\n\n--- DISTINCT CANDIDATE ---\n\n".join(
            build_research_text(item, max_results=1, max_content_chars=450)
            for item in research
        )
    else:
        research_text = build_research_text(
            research,
            max_results=5,
            max_content_chars=500,
        )

    prompt = f"""
You are the intelligence editor behind a distinctive crypto creator.

FINAL OUTPUT MUST BE 500 CHARACTERS OR FEWER, INCLUDING SPACES.

CREATOR DNA
===========
{writer_profile}

RESEARCH CANDIDATES
===================
{research_text}

TASK
====
Create ONE Telegram feed message from the strongest distinct developments above.
Do not write one mini-report per source. Do not repeat the same idea, story, mechanism,
question, or wording across sections.

Use this compact structure:
1. One or two strongest CONTENT OPPORTUNITIES. Each must state what could be explored
   and why it matters.
2. One or two RABBIT HOLES. Each must identify a deeper question or missing evidence
   worth investigating.

Prefer two genuinely different developments when the evidence supports it. If the
candidates overlap, merge them and use the space for a deeper angle instead.

OUTPUT FORMAT
=============
OPP: <useful content angle and why it matters>
RABBIT: <specific deeper investigation and why it matters>

Add a second OPP/RABBIT pair only if it remains useful and fits under the hard limit.
Do not add Signal, What happened, Mechanism, Numbers, or other repeated summary sections.

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
        temperature=0.45,
        max_tokens=FEED_MAX_OUTPUT_TOKENS,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a sharp crypto intelligence editor. "
                    "Produce one unified Telegram feed, never repeated sections, "
                    "and never exceed 500 characters."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    return _fit_feed(response.choices[0].message.content or "")
