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

    # Remove markdown code fences.
    text = re.sub(
        r"```(?:text|markdown)?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = text.replace("```", "")

    # Remove citation artifacts.
    text = re.sub(
        r"【\d+(?:†[^】]*)?】",
        "",
        text,
    )

    # Remove markdown links but keep visible text.
    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    return text.strip()


def extract_section(text: str, section_name: str, next_sections):
    pattern = (
        rf"{re.escape(section_name)}\s*:\s*"
        rf"(.*?)(?=\n\s*(?:"
        + "|".join(re.escape(item) for item in next_sections)
        + r")\s*:|\Z)"
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

    # Obvious unfinished endings.
    bad_endings = (
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

    lower = stripped.lower()

    if lower.endswith(bad_endings):
        return True

    # Unclosed brackets.
    if stripped.count("(") > stripped.count(")"):
        return True

    if stripped.count("[") > stripped.count("]"):
        return True

    # If the final character is a letter or number, it may still be
    # perfectly valid, so don't automatically reject it.
    return False


def build_prompt(
    research,
    request_type="feed",
    retry=False,
):
    profile = load_writer_profile()

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
            f"CONTENT: {content[:1800]}\n"
            f"URL: {url}"
        )

    sources_text = "\n\n".join(sources)

    if request_type == "create":
        draft_requirement = """
The DRAFT may be anywhere from 0 to 1400 characters.

Do not force the draft to be long.

Use the length that naturally fits the idea.

A short post is better than padded writing.

Never cut the draft off mid-sentence.
"""
    else:
        draft_requirement = f"""
The DRAFT MUST be between
{MIN_DRAFT_CHARACTERS} and {MAX_DRAFT_CHARACTERS} characters.

Do not cut the draft off mid-sentence.
"""

    retry_instruction = ""

    if retry:
        retry_instruction = """
IMPORTANT RETRY:

The previous generation appeared to end before the thought was complete.

Write a completely finished draft this time.

Make sure the final sentence is complete.
Do not stop because of token limits.
Do not leave a sentence, list or thought unfinished.
"""

    return f"""
You are an intelligent crypto research and content intelligence assistant.

Your job is to understand the supplied research and identify the most
interesting content opportunity.

You are NOT a generic news summarizer.

Think independently about what the research actually means.

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
- opportunities other creators may have missed
- contradictions
- second-order effects
- hidden opportunities
- risks
- implications for builders, traders or users

WRITING STYLE INSTRUCTIONS

The writing profile is a GUIDE, not a template.

Do NOT repeatedly reproduce the same hook.

Do NOT repeatedly use the same paragraph structure.

Do NOT force the same tone onto every topic.

Do NOT copy phrases from the examples simply because they appear
frequently.

Instead, understand the underlying characteristics of the author's
writing.

The final draft should feel consistent with the author's natural
writing while still being appropriate for the actual topic.

The topic determines the shape of the writing.

The writing profile influences HOW the idea is expressed.

Different topics should produce genuinely different drafts.

For example:

- serious security research may be direct and analytical
- a funny market observation may be casual
- a major opportunity may be energetic
- technical research may require explanation
- a surprising discovery may use a strong hook
- a personal-looking market observation may be reflective

Do not mechanically imitate the examples.

Never invent personal experiences.

Never claim the creator personally tested something unless the research
proves it.

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

OUTPUT FORMAT

Return ONLY these four sections:

CATEGORY:
<short category>

CONTENT ANGLE:
<the strongest original angle for the creator>

DRAFT:
<ready-to-post social media draft>

SOURCES:
<source URLs, one per line>

Do NOT include:

WHAT HAPPENED:
WHY IT MATTERS:
ANALYSIS:
SUMMARY:
NOTES:

or any other sections.

Do NOT put source citations such as:

【1†https://example.com】

inside the draft.

Do not use markdown citation syntax.

The SOURCES section must contain plain URLs only.

Do not begin every post with the same type of hook.

Avoid generic openings such as:

"Here's an interesting..."
"According to..."
"Breaking..."
"Today I discovered..."

Use the strongest opening for the specific subject.

{draft_requirement}

{retry_instruction}

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
                    "You are a precise crypto research and "
                    "content intelligence assistant. "
                    "Follow the requested output structure exactly "
                    "and always finish your draft."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return response.choices[0].message.content.strip()


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
        content_angle = "Explore the strongest opportunity revealed by the research."

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
        f"CATEGORY:\n"
        f"{category}\n\n"
        f"CONTENT ANGLE:\n"
        f"{content_angle}\n\n"
        f"DRAFT:\n"
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

    # Retry only when the draft appears unfinished.
    if draft_looks_cut_off(draft):
        logger.warning(
            "Writer draft appears incomplete. Retrying once."
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
            logger.warning(
                "Writer draft still appears incomplete after retry."
            )

    # Enforce the existing feed/research minimum.
    if request_type != "create":
        if len(draft) < MIN_DRAFT_CHARACTERS:
            logger.warning(
                "Draft is below configured minimum: %d characters.",
                len(draft),
            )

    # Never allow an oversized draft to pass through.
    if len(draft) > MAX_DRAFT_CHARACTERS:
        logger.warning(
            "Draft exceeds maximum length (%d).",
            MAX_DRAFT_CHARACTERS,
        )

    return output