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

    # Remove malformed citation artifacts.
    text = re.sub(
        r"ã€\d+(?:â€[^ã€‘]*)?ã€‘",
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
        "...",
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

        # Keep the prompt compact to reduce token consumption.
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
RETRY INSTRUCTION

The previous DRAFT failed validation.

Write a completely new DRAFT.

Maximum length: {draft_max} characters.

Make it shorter if necessary.

The DRAFT MUST finish naturally.

Do not end with an incomplete sentence,
unfinished thought, unfinished list, or "...".

Do not explain the retry.
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
- what second-order implications could matter
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

CONTENT ANGLE is NOT a summary of the research.

It is a professional recommendation telling the creator:

- what to write
- what perspective to take
- what part of the story deserves attention
- what evidence or examples to emphasize
- what the reader should understand
- what direction the creator can take if expanding the post

The CONTENT ANGLE should be useful even if the creator later
rewrites or expands the DRAFT using another writing tool.

A strong content angle can be:

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

The DRAFT is a short content starting point, not a full article.

Maximum length: {draft_max} characters.

There is NO minimum length.

The priority order is:

1. COMPLETE THOUGHT
2. STRONG IDEA
3. NATURAL WRITING
4. CHARACTER LIMIT

A complete 250-character draft is better than an incomplete
{draft_max}-character draft.

A complete 150-character draft is better than a cut-off
{draft_max}-character draft.

NEVER cut the DRAFT off simply because the character limit
is approaching.

NEVER end the DRAFT with:

- an unfinished sentence
- an unfinished list
- an unfinished argument
- "..."
- a dangling conjunction such as "and", "but", "because",
  "while", "which", "that", "with", or "so"
- a colon introducing information that never follows

If the idea is too large for the character limit, COMPRESS IT.

Remove secondary facts before removing the ending.

Do not try to squeeze every important fact into the DRAFT.

The DRAFT should communicate ONE strong idea clearly.

For /feed:

The DRAFT is an intelligence clue of no more than
350 characters.

It should give the creator a useful starting point that can
be expanded later.

For /create:

The DRAFT is a concise ready-to-develop content starting point
of no more than 410 characters.

For /research:

The DRAFT is a concise researched content starting point
of no more than 410 characters.

The CONTENT ANGLE should carry the deeper context, evidence,
perspective and development direction.

The DRAFT itself does NOT need to contain everything.

If the character limit is approaching, make the idea shorter.

Do NOT sacrifice completion to include another fact.

Before returning the answer, silently check:

- Is the final sentence complete?
- Is the thought complete?
- Does the ending read naturally?
- Is there any unfinished list?
- Is there any trailing conjunction?
- Is there an ellipsis?
- Is the DRAFT within the character limit?

If any answer is NO, rewrite the DRAFT shorter until all
conditions are satisfied.

Do not explain this validation process in the output.

{retry_instruction}

OUTPUT FORMAT

Return ONLY these four sections:

CATEGORY:
<short accurate category>

CONTENT ANGLE:
<professional recommendation for what the creator should
write and what perspective to take>

DRAFT:
<complete ready-to-post or ready-to-develop social-media draft>

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
        max_tokens=700,
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
def generate_content(
    request: str,
    research=None,
):
    """
    Generate finished, ready-to-post creator content.

    This is intentionally separate from generate_intelligence().
    /research and /feed continue using the intelligence pipeline.
    /create uses this creator pipeline.
    """

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    request = request.strip()

    if not request:
        raise RuntimeError(
            "Create request cannot be empty."
        )

    profile = load_writer_profile()

    research_text = ""

    if research and research.get("results"):
        research_text = build_research_text(
            research
        )

    prompt = f"""
You are the dedicated crypto/Web3 content creator for this creator brand.

The user has asked you to CREATE CONTENT.

USER REQUEST:
{request}

RESEARCH / CURRENT CONTEXT:
{research_text if research_text else "No external research was supplied."}

WRITER PROFILE

PATTERNS:
{profile["patterns"]}

RULES:
{profile["rules"]}

EXAMPLES:
{profile["examples"]}


YOUR JOB

Understand the user's actual content request before writing.

The user may ask for:

- a GM post
- good morning post
- market observation
- reaction
- opinion
- hot take
- educational post
- explainer
- breaking-news post
- funny crypto post
- meme-style post
- storytelling post
- guide
- thread
- technical explanation
- contrarian take
- community post
- or another crypto/Web3 format.


IMPORTANT: CONTENT TYPE FIRST

The requested format determines the shape of the output.

If the user says:

"GM post"

"Crypto GM post"

"write a GM"

"good morning crypto post"

then create an actual GM post.

Do NOT turn it into a research report.

Do NOT explain what GM means unless that is specifically requested.

Do NOT produce CATEGORY, CONTENT ANGLE, DRAFT, or SOURCES.

The result should feel like something the creator would actually post on crypto Twitter/X that morning.

A GM post can use a current market observation, interesting development, community sentiment, humor, a simple thought, or a timely crypto reference when useful.

It does NOT need to mention news.

Do not force research into a GM post simply because research is available.


CURRENT CONTEXT AND RESEARCH

When the request benefits from current information, use the supplied research.

Use research especially when the user asks for:

- today's market
- current events
- latest news
- reactions
- breaking news
- what is happening
- current protocols/projects
- recent launches
- recent market movements
- current narratives
- recent crypto Twitter discussions

Research is context, not a script.

Extract only information that genuinely improves the requested content.

Never dump research into the post.

Never invent facts.

Never invent personal experiences.

Never claim the creator personally did something unless the user supplied that information.


WRITING STYLE

Write like a real crypto creator.

Use the writer profile as the creator's writing DNA.

Do not mechanically copy the examples.

Do not reuse distinctive phrases from the examples.

Do not make every post sound the same.

Do not force slang.

Do not force lowercase.

Do not force emojis.

Do not force hashtags.

Do not use generic AI motivational language.

Avoid phrases such as:

"the future is here"

"game changer"

"this changes everything"

"the next big thing"

unless the context genuinely calls for them.

The writing should feel natural, specific and intentional.

Short sentences are allowed.

Fragments are allowed when they feel natural to the creator.

Line breaks may be used when they improve the post.

The output should look like a real social post, not an essay.


GM-SPECIFIC BEHAVIOR

When the request is a GM post:

- make it feel current
- make it feel human
- give it a reason to exist
- it can be casual, funny, observational, reflective, market-aware or slightly provocative
- it can reference something happening in crypto when that improves it
- avoid generic "rise and grind" language
- avoid corporate motivational language
- avoid explaining the meaning of GM
- do not make every GM post sound inspirational
- do not use the same GM structure every time

The post should be something people could naturally reply to.


FACTUAL DISCIPLINE

Do not invent:

- prices
- percentages
- dates
- launches
- partnerships
- funding
- user numbers
- token performance
- protocol activity
- quotes
- announcements
- personal experiences

If research contains uncertainty, do not present speculation as fact.

If the request is creative and does not require factual claims, creative writing is allowed.


OUTPUT RULES

Return ONLY the finished content.

Do NOT return:

CATEGORY:
CONTENT ANGLE:
DRAFT:
SOURCES:
ANALYSIS:
SUMMARY:
EXPLANATION:
NOTES:

Do not say:

"Here is your post"

"Here's a draft"

"Based on the research"

"According to the sources"

Do not explain your reasoning.

Do not wrap the post in quotation marks.

Do not use markdown code fences.

Do not include source URLs unless the user explicitly asks for them.

Make the result ready to copy and post immediately.


QUALITY CHECK

Before returning the content, silently check:

1. Did I actually follow the requested content type?
2. If this is a GM request, does it actually feel like a GM post?
3. Is it natural?
4. Does it sound like a human crypto creator?
5. Did I avoid unnecessary research?
6. Did I avoid invented facts?
7. Is the post complete?
8. Did I avoid generic AI language?
9. Did I return ONLY the content?

If any answer is NO, rewrite before returning.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.85,
        max_tokens=700,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto content creator "
                    "and editorial strategist. "
                    "Create natural, human, ready-to-post "
                    "crypto content. "
                    "Follow the requested content format exactly."
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

    return clean_model_text(text).strip()
