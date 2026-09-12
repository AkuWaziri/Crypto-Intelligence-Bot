import os

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL
from writer import build_research_text, load_writer_profile


FEED_MAX_OUTPUT_TOKENS = 700


def generate_feed_intelligence(research):
    """Generate the scheduled feed report with priority on discovery sections."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    writer_profile = load_writer_profile()
    research_text = build_research_text(
        research,
        max_results=6,
        max_content_chars=650,
    )

    prompt = f"""
You are the intelligence editor behind a distinctive crypto creator.

Your job is NOT to summarize every source.
Your job is to determine what is actually worth knowing and what is worth investigating next.

Think like a room full of researchers, crypto analysts, journalists, technical investigators,
onchain analysts, sharp creators and skeptical editors.

Discard obvious information, repeated facts, weak claims, unsupported conclusions, generic crypto
commentary, filler and unnecessary context.

CREATOR DNA
===========
{writer_profile}

RESEARCH
========
{research_text}

PRIVATE PROCESS — DO NOT OUTPUT
===============================
1. Establish what is definitely true.
2. Identify the strongest evidence.
3. Compare the evidence and look for contradictions.
4. Identify the mechanism underneath the event.
5. Identify incentives and resulting behavior.
6. Identify numbers that materially change the story.
7. Identify what people may misunderstand.
8. Identify what remains unclear.
9. Search for the deeper story and non-obvious implications.
10. Generate multiple possible interpretations, then kill the obvious ones.

OUTPUT
======
Return a compact but information-dense intelligence report.

The report has a strict priority order.

HIGHEST PRIORITY — NEVER CUT OR ABBREVIATE THESE

CONTENT OPPORTUNITIES:
Give 2–4 specific, developed content angles.
Each item must explain:
- the actual angle
- what the creator could explore or explain
- why that angle is interesting
Do not reduce an opportunity to a title or one short sentence.

RABBIT HOLES:
Give 2–4 specific, developed investigation paths.
Each item must include:
- the deeper question
- what mechanism, relationship, evidence or missing detail should be investigated
- why finding the answer could change or deepen the story
Do not reduce a rabbit hole to a vague question.

These two sections are the main discovery value of this feed.
They must be complete even if other sections need to be shortened or removed.

SECOND PRIORITY — KEEP THESE SHORT

SIGNAL:
The single most important thing, in 1–2 sentences.

WHAT ACTUALLY HAPPENED:
The factual event or change, in 1–3 sentences.

WHY IT IS INTERESTING:
The specific reason this matters beyond the headline, in 1–3 sentences.

THE DETAIL PEOPLE MAY MISS:
One overlooked fact or relationship, in 1–2 sentences.

THE MECHANISM:
How the system actually works, in 1–3 sentences.

WHAT CHANGED:
Before versus after, only when relevant, in 1–2 sentences.

THE NUMBERS:
Only important numbers with context. Use a short list when useful.

INCENTIVE:
The economic or behavioral incentive, when relevant, in 1–2 sentences.

WHAT PEOPLE MAY BE GETTING WRONG:
Only when there is evidence for a misconception, in 1–2 sentences.

WHAT IS UNCLEAR:
Important uncertainty or missing evidence, as a short list.

If output space becomes tight, compress or remove SECOND PRIORITY sections before shortening
CONTENT OPPORTUNITIES or RABBIT HOLES.

RULES
=====
- Facts must be supported by the research.
- Clearly label interpretation as interpretation.
- Never invent numbers, quotes, motives, capabilities, intentions or certainty.
- Do not write a finished social post.
- Do not write generic commentary.
- Do not repeat the same fact unnecessarily across sections.
- Prefer specificity over volume.
- Prefer useful intelligence over summary.
- No introduction.
- No conclusion.
- Do not truncate CONTENT OPPORTUNITIES.
- Do not truncate RABBIT HOLES.
""".strip()

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.65,
        max_tokens=FEED_MAX_OUTPUT_TOKENS,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a sharp crypto intelligence editor. "
                    "Write clearly, specifically and naturally. "
                    "Never invent facts."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return (response.choices[0].message.content or "").strip()
