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

    # Remove code fences.
    text = re.sub(
        r"```(?:text|markdown|json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = text.replace("```", "")

    # Remove AI citation artifacts.
    text = re.sub(
        r"【\d+(?:†[^】]*)?】",
        "",
        text,
    )

    # Remove markdown hyperlinks while preserving visible text.
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
        "–",
        "—",
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

        sources.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"CONTENT: {content[:2000]}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sources)


def build_prompt(
    research,
    request_type="feed",
    retry=False,
):
    profile = load_writer_profile()

    sources_text = build_research_text(research)

    if request_type == "create":
        draft_requirement = f"""
The DRAFT can be between 0 and {MAX_DRAFT_CHARACTERS} characters.

Do not make it longer just to fill space.

Choose the natural length for the idea.

A concise strong post is better than padded writing.
"""
    else:
        draft_requirement = f"""
The DRAFT MUST be between
{MIN_DRAFT_CHARACTERS} and {MAX_DRAFT_CHARACTERS} characters.

Do not pad the draft with unnecessary information.
"""

    retry_instruction = ""

    if retry:
        retry_instruction = """
RETRY INSTRUCTION:

The previous draft appeared to end before the thought was complete.

Write a new, complete draft.

Make sure every sentence is finished.
Do not end on a fragment.
Do not stop in the middle of a list or argument.
"""

    return f"""
You are a senior crypto research editor and content strategist.

Your job is to transform current research into a strong,
fact-grounded content opportunity for a crypto content creator.

You have TWO separate responsibilities.

RESPONSIBILITY 1 — EDITORIAL INTELLIGENCE

First understand what the research actually says.

Determine:

- what is confirmed
- what is uncertain
- what is genuinely important
- what is surprising
- what is changing
- what people may be overlooking
- what the second-order implications could be
- whether there is a real opportunity
- whether there is a meaningful risk
- whether the story is bullish, bearish, neutral, skeptical, funny,
  controversial, educational, practical or simply interesting
- whether the research deserves a post at all

Do NOT force every story into a bullish opportunity.

Do NOT force every story into a bearish warning.

Do NOT manufacture urgency.

Do NOT manufacture controversy.

Do NOT manufacture a creator opportunity if the evidence does not
support one.

The research determines the editorial stance.

If the evidence is weak or speculative, make that clear.

If something is confirmed, distinguish it from speculation.

Never turn a possibility into a fact.

Never invent information.

RESPONSIBILITY 2 — CREATOR CONTENT STRATEGY

After understanding the research, determine the SINGLE strongest
content angle a crypto creator could use.

CONTENT ANGLE is NOT a summary of the research.

CONTENT ANGLE is a professional recommendation telling the creator
WHAT KIND OF POST TO WRITE and WHAT PERSPECTIVE TO TAKE.

A strong content angle can be:

- a contrarian observation
- an overlooked implication
- a practical explainer
- a comparison
- a warning
- a market thesis
- a creator-focused opportunity
- a builder-focused opportunity
- a user-focused observation
- a question or debate
- a surprising fact
- a case study
- a "why this matters" narrative
- a trend analysis
- a personal-perspective-style post, without inventing personal
  experiences
- an actionable post
- a skeptical take
- a bullish thesis when genuinely justified

The CONTENT ANGLE should answer:

"What should I, as a crypto content creator, actually write about
from this research?"

Make it specific enough that the creator immediately understands
the post they should write.

Bad:

"Write about AI agents and crypto."

Better:

"Write a contrarian post questioning whether AI agents are actually
ready to control wallets, using the gap between autonomous decision
making and transaction security as the central argument."

Bad:

"Talk about crypto payments."

Better:

"Write a practical comparison showing how the new payment tools remove
different merchant barriers, then focus on the overlooked settlement
and compliance decisions merchants still have to make."

Do NOT automatically recommend "first mover advantage."

Do NOT automatically recommend "start building now."

Do NOT automatically recommend "this is a game changer."

Only use those ideas when the research genuinely supports them.

WRITING PROFILE

The writing profile describes HOW the creator naturally writes.

It does NOT determine the editorial conclusion.

Do not mechanically reproduce the examples.

Do not repeatedly use the same hooks.

Do not repeatedly use the same paragraph structure.

Do not force all-caps into every post.

Do not force slang into every post.

Do not deliberately insert mistakes.

Use the profile as a flexible understanding of:

- tone
- rhythm
- sentence length
- paragraph spacing
- vocabulary
- confidence
- directness
- use of numbers
- use of questions
- use of contrasts
- use of lists
- capitalization
- punctuation
- natural conversational patterns

Different subjects should produce different writing.

The topic determines the shape.

The research determines the stance.

The writing profile influences the expression.

Never copy complete sentences or distinctive phrases from the
examples.

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

Do not assume a company has launched something if the source only
describes a possibility.

Do not convert "potential" into "confirmed."

Do not make price, funding, user-count, adoption, launch or
performance claims unless supported.

Do not predict financial outcomes as facts.

Do not claim something is "live", "new", "confirmed", "official",
"guaranteed" or "already happening" unless the research supports it.

If the research contains conflicting information, reflect the
uncertainty.

Be especially careful with absolute or universal claims.

Do not claim that nobody, no project, no protocol, no company, or
nothing has done something unless the supplied research explicitly
establishes that.

Avoid unsupported claims such as:

"No one is doing this."
"No protocol has this."
"This is the first."
"Nothing like this exists."
"Everyone is adopting this."
"This guarantees..."
"This will definitely..."

When evidence is incomplete, use precise language such as:

"So far, the supplied research shows..."
"The sources reviewed here do not show..."
"This appears to be early..."
"The evidence points toward..."
"At least from these sources..."

Do not turn an absence of evidence into evidence of absence.
The scope of your conclusion must match the scope of the research.

If the supplied sources only describe a technology, do not use them
to make claims about industry-wide adoption, availability, deployment,
market size, or the absence of competing implementations.

Instead say what the sources actually establish and identify what
they do not establish.

Never use a limited source set to make a broad industry conclusion.

Do not invent personal testing, conversations, experiences or results.
DRAFT REQUIREMENTS

The draft should feel like a real social-media post written by the
creator, not a research report.

Do not write a generic news summary.

Do not simply repeat the CONTENT ANGLE.

Do not mention "the research" or "the sources" inside the draft.

Do not begin every post with the same hook.

Choose the opening based on the actual subject.

Possible openings include:

- a direct observation
- a surprising fact
- a strong opinion
- a question
- a personal-style observation without inventing experience
- a contrast
- a blunt statement
- a short setup
- an unusual detail

Do not use generic AI openings such as:

"Here's an interesting..."
"According to..."
"Breaking..."
"Today I discovered..."
"In the ever-evolving world of..."

{draft_requirement}

Never cut the draft off mid-sentence.

{retry_instruction}

OUTPUT FORMAT

Return ONLY these four sections:

CATEGORY:
<short, accurate category>

CONTENT ANGLE:
<professional recommendation for what content the creator should
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

Do not include citation markers such as:

【1†...】

inside the draft.

Do not use markdown links in the DRAFT.

REQUEST TYPE:
{request_type}
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
        max_tokens=1400,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto research editor and "
                    "content strategist. "
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

    # First generation.
    model_text = call_writer(
        research,
        request_type=request_type,
        retry=False,
    )

    output, draft = format_output(
        model_text,
        research,
    )

    # Retry if the draft appears incomplete,
    # too short, or too long.
    needs_retry = (
        draft_looks_cut_off(draft)
        or len(draft) < MIN_DRAFT_CHARACTERS
        or len(draft) > MAX_DRAFT_CHARACTERS
    )

    if needs_retry:
        logger.warning(
            "Generated draft failed validation."
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

    # If the retry still fails, return the result
    # rather than modifying or truncating the draft.
    if draft_looks_cut_off(draft):
        logger.warning(
            "Final draft still appears incomplete."
        )

    if len(draft) < MIN_DRAFT_CHARACTERS:
        logger.warning(
            "Final draft is below configured minimum: %d characters.",
            len(draft),
        )

    if len(draft) > MAX_DRAFT_CHARACTERS:
        logger.warning(
            "Final draft exceeds configured maximum: %d characters.",
            len(draft),
        )

    return output
