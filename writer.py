import os
import re
import logging

from groq import Groq

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    WRITER_PROFILE_DIR,
    MIN_DRAFT_CHARACTERS,
    MAX_DRAFT_CHARACTERS,
    MAX_FEED_DRAFT_CHARACTERS,
)

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


def read_profile_file(filename: str) -> str:
    path = os.path.join(
        WRITER_PROFILE_DIR,
        filename,
    )

    if not os.path.exists(path):
        return ""

    try:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            return file.read()
    except Exception:
        logger.exception(
            "Could not read writer profile file: %s",
            filename,
        )
        return ""


def load_writer_profile():
    return {
        "examples": read_profile_file("examples.txt"),
        "patterns": read_profile_file("patterns.txt"),
        "rules": read_profile_file("rules.txt"),
    }


def clean_model_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(
        r"```(?:text|markdown|json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace("```", "")

    text = re.sub(
        r"ã€\d+(?:â€ [^ã€‘]*)?ã€‘",
        "",
        text,
    )

    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    return text.strip()


def extract_section(
    text: str,
    section_name: str,
    next_sections,
):
    next_pattern = "|".join(
        re.escape(item)
        for item in next_sections
    )

    pattern = (
        rf"{re.escape(section_name)}\s*:\s*"
        rf"(.*?)(?=\n\s*(?:{next_pattern})\s*:|\Z)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return ""

    return match.group(1).strip()


def parse_output(text: str):
    text = clean_model_text(text)

    category = extract_section(
        text,
        "CATEGORY",
        [
            "CONTENT ANGLE",
            "DRAFT",
            "SOURCES",
        ],
    )

    content_angle = extract_section(
        text,
        "CONTENT ANGLE",
        [
            "DRAFT",
            "SOURCES",
        ],
    )

    draft = extract_section(
        text,
        "DRAFT",
        [
            "SOURCES",
        ],
    )

    return {
        "category": category,
        "content_angle": content_angle,
        "draft": draft,
    }


def draft_looks_cut_off(draft: str) -> bool:
    if not draft:
        return True

    stripped = draft.strip()

    if len(stripped) < 20:
        return True

    lower = stripped.lower()

    unfinished_endings = (
        " and",
        " or",
        " but",
        " because",
        " that",
        " which",
        " with",
        " for",
        " to",
        " of",
        " in",
        " on",
        " at",
        " into",
        " from",
        " as",
        " than",
        " is",
        " are",
        " was",
        " were",
        " the",
        " a",
        " an",
        ",",
        ":",
        "-",
        "â€“",
        "â€”",
        "(",
        "[",
    )

    if lower.endswith(unfinished_endings):
        return True

    if stripped.count("(") > stripped.count(")"):
        return True

    if stripped.count("[") > stripped.count("]"):
        return True

    return False


def build_research_text(research):
    sources = []

    for index, result in enumerate(
        research.get("results", []),
        start=1,
    ):
        title = result.get("title", "").strip()
        content = result.get("content", "").strip()
        url = result.get("url", "").strip()

        # Keep the writer prompt compact.
        # We do not need the full article content.
        compact_content = content[:1000]

        sources.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"CONTENT: {compact_content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sources)


def get_draft_max(request_type):
    if request_type == "feed":
        return MAX_FEED_DRAFT_CHARACTERS

    return MAX_DRAFT_CHARACTERS


def build_prompt(
    research,
    request_type="feed",
    retry=False,
):
    profile = load_writer_profile()

    sources_text = build_research_text(research)

    draft_max = get_draft_max(request_type)

    retry_instruction = ""

    if retry:
        retry_instruction = f"""
RETRY INSTRUCTION:

The previous draft failed validation.

Write a new draft.

The new DRAFT must be no more than
{draft_max} characters.

It must be a complete thought.

Never end mid-sentence.

Do not pad the draft.

Do not explain that you are retrying.
"""

    return f"""
You are a senior crypto research editor and content strategist.

Your job is to transform current research into useful,
fact-grounded content intelligence for a crypto creator.

REQUEST TYPE:
{request_type}

You have TWO responsibilities.

RESPONSIBILITY 1 — EDITORIAL INTELLIGENCE

Understand what the research actually establishes.

Determine:

- what is confirmed
- what is uncertain
- what is genuinely important
- what is surprising
- what is changing
- what people may be overlooking
- what the second-order implications could be
- whether there is a meaningful opportunity
- whether there is a meaningful risk
- whether the story is bullish, bearish, neutral, skeptical,
  funny, controversial, educational, practical or simply interesting

Do NOT force every story into a bullish opportunity.

Do NOT force every story into a bearish warning.

Do NOT manufacture urgency.

Do NOT manufacture controversy.

Do NOT manufacture a creator opportunity when the evidence
does not support one.

The research determines the editorial stance.

If evidence is weak or speculative, say so.

If something is confirmed, distinguish it from speculation.

Never turn a possibility into a fact.

Never invent information.

RESPONSIBILITY 2 — CREATOR CONTENT STRATEGY

Determine the SINGLE strongest content angle a crypto creator
could use.

CONTENT ANGLE is NOT a summary.

It is a professional recommendation telling the creator:

- what to write
- what perspective to take
- what part of the story deserves attention
- what evidence or examples to emphasize
- what the reader should understand

The CONTENT ANGLE should be useful even if the creator later
rewrites the DRAFT using another writing tool.

Examples of strong angles:

- contrarian observation
- overlooked implication
- practical explainer
- comparison
- warning
- market thesis
- builder opportunity
- user-focused observation
- case study
- actionable post
- skeptical take
- trend analysis
- surprising fact
- debate/question

Do NOT automatically recommend:

"first mover advantage"

"start building now"

"this is a game changer"

"the future is here"

Only use such framing when the research genuinely supports it.

WRITING PROFILE

The profile describes HOW the creator naturally writes.

Use it flexibly.

Do not mechanically copy examples.

Do not repeatedly use the same hooks.

Do not repeatedly use the same paragraph structure.

Do not force slang.

Do not force all-caps.

Do not deliberately insert mistakes.

Different subjects should produce different writing.

The topic determines the shape.

The research determines the stance.

The writing profile influences the expression.

Never copy complete sentences or distinctive phrases
from the examples.

Never invent personal experiences.

WRITER PATTERNS:
{profile["patterns"]}

WRITER RULES:
{profile["rules"]}

WRITER EXAMPLES:
{profile["examples"]}

RESEARCH QUERY:
{research.get("query", "")}

RESEARCH:

{sources_text}

FACTUAL DISCIPLINE

Only make factual claims supported by the supplied research.

Do not add facts merely because they sound plausible.

Do not assume a company launched something if the sources
only describe a possibility.

Do not convert "potential" into "confirmed."

Do not make price, funding, user-count, adoption, launch,
performance or security claims unless supported.

Do not predict financial outcomes as facts.

Do not claim something is live, new, confirmed, official,
guaranteed or already happening unless the research supports it.

If sources conflict, reflect the uncertainty.

Be especially careful with absolute claims.

Do not claim that nobody, no project, no protocol, no company,
or nothing has done something unless the supplied research
explicitly establishes that.

Do not turn absence of evidence into evidence of absence.

The scope of the conclusion must match the scope of the research.

DRAFT REQUIREMENTS

The DRAFT must be no more than {draft_max} characters.

There is NO minimum draft length.

A short draft is acceptable.

Do NOT pad the DRAFT.

The DRAFT must communicate the strongest useful idea
from the research.

The DRAFT should feel like a real social-media post,
not a research report.

Do not simply repeat the CONTENT ANGLE.

Do not mention "the research" or "the sources" inside the DRAFT.

Do not begin every post with the same hook.

Choose the opening based on the actual subject.

Possible openings:

- direct observation
- surprising fact
- strong opinion
- question
- contrast
- blunt statement
- unusual detail
- practical takeaway

Avoid generic AI openings such as:

"Here's an interesting..."

"According to..."

"Breaking..."

"Today I discovered..."

"In the ever-evolving world of..."

MOST IMPORTANT:

The DRAFT must finish naturally.

Never deliberately cut a sentence in half.

Never stop mid-list.

Never end with an incomplete thought.

If the character limit is approaching, make the idea shorter.

The CONTENT ANGLE contains the deeper direction that the
creator can use to expand the idea elsewhere.

{retry_instruction}

OUTPUT FORMAT

Return ONLY these four sections:

CATEGORY:
<short accurate category>

CONTENT ANGLE:
<professional recommendation for what the creator should
write and what perspective to take>

DRAFT:
<complete ready-to-post social-media draft>

SOURCES:
<plain source URLs, one per line>

Do NOT return:

WHAT HAPPENED:
WHY IT MATTERS:
ANALYSIS:
SUMMARY:
EDITORIAL JUDGMENT:
FACT CHECK:
NOTES:

Do not include citation markers inside the DRAFT.

Do not use markdown links in the DRAFT.
"""


def call_writer(
    research,
    request_type="feed",
    retry=False,
):
    prompt = build_prompt(
        research,
        request_type=request_type,
        retry=retry,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.75,
        max_tokens=500,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto research editor "
                    "and content strategist. "
                    "Be fact-grounded, editorially intelligent, "
                    "adaptive and concise. "
                    "Always complete the requested draft."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    text = response.choices[0].message.content

    if not text:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return text.strip()


def format_output(
    model_text,
    research,
):
    parsed = parse_output(model_text)

    category = parsed["category"]
    content_angle = parsed["content_angle"]
    draft = parsed["draft"]

    if not category:
        category = "Crypto intelligence"

    if not content_angle:
        content_angle = (
            "Identify the strongest evidence-based perspective "
            "from this development and explain why it matters."
        )

    if not draft:
        raise RuntimeError(
            "Groq did not return a usable DRAFT section."
        )

    sources = []

    for result in research.get("results", []):
        url = result.get("url", "").strip()

        if url and url not in sources:
            sources.append(url)

    output = (
        "CATEGORY:\n"
        f"{category}\n\n"
        "CONTENT ANGLE:\n"
        f"{content_angle}\n\n"
        "DRAFT:\n"
        f"{draft}"
    )

    if sources:
        output += "\n\nSOURCES:\n"

        for url in sources:
            output += f"{url}\n"

    return output.strip(), draft


def generate_intelligence(
    research,
    request_type="feed",
):
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    draft_max = get_draft_max(request_type)

    model_text = call_writer(
        research,
        request_type=request_type,
        retry=False,
    )

    output, draft = format_output(
        model_text,
        research,
    )

    needs_retry = (
        draft_looks_cut_off(draft)
        or len(draft) > draft_max
    )

    if needs_retry:
        logger.warning(
            "Generated draft failed validation. "
            "Length: %d. Maximum: %d.",
            len(draft),
            draft_max,
        )

        model_text = call_writer(
            research,
            request_type=request_type,
            retry=True,
        )

        output, draft = format_output(
            model_text,
            research,
        )

    if draft_looks_cut_off(draft):
        raise RuntimeError(
            "Generated draft appears incomplete."
        )

    if len(draft) > draft_max:
        raise RuntimeError(
            f"Generated draft is too long: "
            f"{len(draft)} characters. "
            f"Maximum allowed: {draft_max}."
        )

    return output