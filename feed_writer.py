import os

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from writer import build_research_text, load_writer_profile
from research_output import format_research_output

FEED_MAX_OUTPUT_TOKENS = 300
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
    """Generate one compact unified intelligence brief."""
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
Create ONE unified Telegram intelligence brief. Select the strongest genuinely
crypto-specific development. Do not force unrelated stories into the same feed.
If two developments are tightly related, they may be combined. Otherwise choose
one strong development rather than producing scattered mini-reports.

The brief MUST use exactly this structure and order:

SIGNAL: <the development in a few words>
WHY IT MATTERS: <why this is interesting or significant>
CONTENT ANGLE: 1. <specific content angle> 2. <specific content angle>
RABBIT HOLE: 1. <specific deeper investigation>

CONTENT ANGLE is the main creative value of the feed. Give it concrete,
content-ready angles, not generic titles. Each angle should expose a different
way to explain, question, compare, test, or frame the development.

RABBIT HOLE is the deeper investigation worth pursuing next. Make it a specific
unanswered question, mechanism, evidence gap, dependency, incentive, or implication.
It should be substantially more useful than a generic "research more" suggestion.

Budget the 500-character limit deliberately:
- SIGNAL: concise
- WHY IT MATTERS: concise
- CONTENT ANGLE: use the largest share of the available space
- RABBIT HOLE: use the second-largest share

Do not repeat facts between sections.

RULES
=====
- HARD LIMIT: 500 CHARACTERS TOTAL.
- Exactly one SIGNAL, one WHY IT MATTERS, two numbered CONTENT ANGLE items,
  and one numbered RABBIT HOLE.
- No headings other than SIGNAL, WHY IT MATTERS, CONTENT ANGLE, RABBIT HOLE.
- No introduction or conclusion.
- No emojis.
- No generic crypto commentary.
- The selected development must have a clear crypto/blockchain connection.
- Reject unrelated technology/business stories even if they appear in the research.
- Facts must be supported by research.
- Never invent facts.
- Return ONLY the final feed text.
""".strip()

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.35,
        max_tokens=FEED_MAX_OUTPUT_TOKENS,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a sharp crypto intelligence editor. Produce one unified "
                    "Telegram intelligence brief using the exact requested structure. "
                    "Never exceed 500 characters."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    return format_research_output(
        response.choices[0].message.content or ""
    )
