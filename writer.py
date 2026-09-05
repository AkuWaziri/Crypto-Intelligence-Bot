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


# ============================================================
# PROFILE
# ============================================================

def read_profile_file(filename):
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
            return file.read().strip()

    except Exception:
        logger.exception(
            "Failed to read writer profile file: %s",
            filename,
        )

        return ""


def load_writer_profile():
    files = [
        "examples.txt",
        "patterns.txt",
        "rules.txt",
    ]

    sections = []

    for filename in files:
        content = read_profile_file(filename)

        if not content:
            continue

        sections.append(
            f"--- {filename} ---\n{content}"
        )

    return "\n\n".join(sections)


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_model_text(text):
    if not text:
        return ""

    text = str(text).strip()

    text = re.sub(
        r"^```(?:text|markdown)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


def extract_section(text, section_name):
    pattern = (
        rf"{re.escape(section_name)}\s*:\s*"
        rf"(.*?)(?=\n[A-Z][A-Z /_-]*:\s*|\Z)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if not match:
        return ""

    return match.group(1).strip()


def parse_output(text):
    text = clean_model_text(text)

    if not text:
        return []

    blocks = re.split(
        r"\n(?=IDEA\s+\d+\s*:?)",
        text,
        flags=re.IGNORECASE,
    )

    results = []

    for block in blocks:
        block = block.strip()

        if not block:
            continue

        results.append(block)

    return results


# ============================================================
# DRAFT VALIDATION
# ============================================================

def draft_looks_cut_off(text):
    if not text:
        return True

    text = text.strip()

    if not text:
        return True

    if text.endswith(
        (
            ":",
            ",",
            "-",
            "—",
            "...",
            "and",
            "or",
            "but",
        )
    ):
        return True

    last_character = text[-1]

    if last_character not in ".!?\"')]}":
        return True

    return False


# ============================================================
# RESEARCH FORMATTING
# ============================================================

def build_research_text(research):
    if not research:
        return ""

    sections = []

    answer = research.get("answer", "")

    if answer:
        sections.append(
            f"RESEARCH SUMMARY:\n{answer}"
        )

    results = research.get("results", [])

    for index, result in enumerate(
        results,
        start=1,
    ):
        title = (
            result.get("title", "")
            or "Untitled"
        )

        content = (
            result.get("content", "")
            or ""
        ).strip()

        url = (
            result.get("url", "")
            or ""
        ).strip()

        if not content:
            continue

        sections.append(
            f"SOURCE {index}:\n"
            f"TITLE: {title}\n"
            f"CONTENT: {content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sections)


def get_draft_max(mode="normal"):
    if mode == "feed":
        return MAX_FEED_DRAFT_CHARACTERS

    return MAX_DRAFT_CHARACTERS


# ============================================================
# STANDARD CONTENT GENERATION
# ============================================================

def build_prompt(request_text, research):
    writer_profile = load_writer_profile()
    research_text = build_research_text(research)

    return f"""
You are writing for a crypto creator.

The creator explains crypto, blockchain, AI agents,
onchain activity, protocols, infrastructure, money and
internet culture in a simple, human and memorable way.

Do not sound like a corporate content strategist.
Do not sound like a research report.
Do not write generic crypto filler.

CREATOR PROFILE:

{writer_profile}

USER REQUEST:

{request_text}

RESEARCH:

{research_text}

TASK:

Create the requested content.

Use the research as factual grounding.

Do not invent facts.

Do not force every research detail into the content.

Prefer one strong idea over several weak ideas.

Write naturally.

Do not explain your writing process.

Return only the finished content.
""".strip()


def call_writer(prompt, temperature=0.8, max_tokens=1200):
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    client = Groq(
        api_key=GROQ_API_KEY
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a sharp crypto creator "
                    "and writer. "
                    "Be human, clear, specific and "
                    "original. "
                    "Never invent facts."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    return clean_model_text(
        response.choices[0].message.content
    )


def format_output(text):
    return clean_model_text(text)


# ============================================================
# INTELLIGENCE
# ============================================================

def generate_intelligence(
    research,
    context="manual research",
):
    writer_profile = load_writer_profile()
    research_text = build_research_text(research)

    prompt = f"""
You are a crypto intelligence editor.

Turn the research below into useful content intelligence
for a crypto creator.

CREATOR PROFILE:

{writer_profile}

CONTEXT:

{context}

RESEARCH:

{research_text}

Produce a concise intelligence report.

Focus on:

WHAT HAPPENED
WHY IT MATTERS
CONTENT ANGLE

Use only facts supported by the research.

Do not invent numbers, dates, quotes or claims.

Do not write a finished social-media post.

Make the angle specific and interesting.

Return:

WHAT HAPPENED:
...

WHY IT MATTERS:
...

CONTENT ANGLE:
...
""".strip()

    return call_writer(
        prompt,
        temperature=0.7,
        max_tokens=1000,
    )


# ============================================================
# CREATE
# ============================================================

def generate_content(
    request_text,
    research,
):
    prompt = build_prompt(
        request_text,
        research,
    )

    return call_writer(
        prompt,
        temperature=0.85,
        max_tokens=1400,
    )


# ============================================================
# CREATIVE IDEA ENGINE
# ============================================================

def build_idea_research_text(research):
    """
    Build a compact research packet specifically for the
    creative idea engine.

    The idea engine needs enough evidence to understand the
    story, but we deliberately keep the prompt compact so
    Groq does not receive an unnecessarily large request.
    """

    if not research:
        return ""

    sections = []

    answer = (
        research.get("answer", "")
        or ""
    ).strip()

    if answer:
        sections.append(
            f"SUMMARY:\n{answer[:1200]}"
        )

    results = research.get(
        "results",
        [],
    )

    for index, result in enumerate(
        results[:10],
        start=1,
    ):
        title = (
            result.get("title", "")
            or "Untitled"
        ).strip()

        content = (
            result.get("content", "")
            or ""
        ).strip()

        url = (
            result.get("url", "")
            or ""
        ).strip()

        if not content:
            continue

        # Keep individual source material compact.
        content = content[:900]

        sections.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"FACTS/CONTEXT: {content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sections)


def build_meme_idea_prompt(
    situation,
    research,
):
    writer_profile = load_writer_profile()
    research_text = build_idea_research_text(
        research
    )

    return f"""
You are the senior creative director for a crypto
creator brand.

The creator wants ideas for things they can actually
MAKE — not generic content strategy.

The brand explains crypto through sharp observations,
simple language, visual thinking, humor, absurdity,
human behavior and memorable storytelling.

The creator may use:

- text comics
- character illustrations
- handwritten memes
- single-panel drawings
- multi-panel comics
- sketches
- arrows and labels
- charts
- screenshots
- visual metaphors
- reaction scenes
- absurd visual situations
- simple editorial illustrations
- other formats when the situation calls for them

There is NO fixed format.

The situation decides the format.

USER'S SITUATION:

{situation}

RESEARCH:

{research_text}

YOUR JOB:

First understand what actually happened.

Separate confirmed facts from interpretation.

Then privately explore a LARGE creative possibility
space.

Think through many different possibilities before
selecting the winners.

Explore different:

- jokes
- visual metaphors
- characters
- compositions
- expressions
- formats
- narrative structures
- emotional reactions
- absurd comparisons
- social observations
- punchlines

Do NOT output the large pool.

Select only the 2 or 3 strongest ideas.

The ideas must feel like something a real crypto creator
would genuinely want to make.

Do not give generic suggestions such as:

"make a funny meme about this"

"make a comic explaining the situation"

"make an educational post"

Those are not ideas.

Give the actual creative premise.

For example, instead of:

"Make a comic about people buying the token."

think:

"Four-panel courtroom scene where the only evidence
presented for buying the token is a blue check reply."

That is the level of specificity required.

CHARACTER RULE:

Characters are optional.

Use a character only when it makes the idea stronger.

The character can be an existing recurring character,
a generic crypto trader, investor, founder, degen,
bot, protocol, whale, etc.

Do not force recurring characters into every idea.

FORMAT RULE:

The format must be chosen based on the situation.

One idea may be a text comic.

Another may be a single-panel drawing.

Another may be a handwritten sketch.

Do not make all three the same format.

QUALITY FILTER:

Reject ideas that are:

- generic
- obvious
- merely informational
- interchangeable with any crypto story
- dependent on invented facts
- too complicated to execute
- trying too hard to be funny
- just a rewritten headline
- generic "educational content"

Prefer:

- one clear visual or narrative premise
- immediate understanding
- strong human behavior
- irony
- tension
- surprise
- simplicity
- memorable imagery
- creator personality

IMPORTANT:

Do not copy another creator's exact artwork or style.

You may use the general principle of dynamic,
situation-driven crypto meme making.

OUTPUT EXACTLY 2 OR 3 IDEAS.

Use this format:

IDEA 1:
FORMAT:
CONCEPT:
EXECUTION:
PUNCHLINE:
SOURCES:

IDEA 2:
FORMAT:
CONCEPT:
EXECUTION:
PUNCHLINE:
SOURCES:

IDEA 3:
FORMAT:
CONCEPT:
EXECUTION:
PUNCHLINE:
SOURCES:

If only two ideas are genuinely strong, return two.

Do not write the finished meme.

Do not write the finished social post.

The user will create it themselves.

Every factual element must be supported by the
research sources.
""".strip()


def build_post_idea_prompt(
    subject,
    research,
):
    writer_profile = load_writer_profile()
    research_text = build_idea_research_text(
        research
    )

    return f"""
You are the senior creative director for a crypto
creator brand.

Your job is to discover genuinely interesting things
the creator could WRITE or CREATE.

You are NOT a generic content strategist.

You are NOT producing a list of SEO topics.

You are finding the strongest creative directions hidden
inside a subject.

CREATOR PROFILE:

{writer_profile}

SUBJECT:

{subject}

RESEARCH:

{research_text}

YOUR JOB:

First understand the subject deeply.

Identify:

- what actually happened
- what changed
- what is unusual
- what people misunderstand
- what people will care about
- where there is tension
- where incentives conflict
- what users/investors/builders/degenerates might do
- what practical action may matter
- what assumption could be challenged
- what story is hiding underneath the facts

Then privately generate a LARGE pool of possible
directions.

Think across many different forms:

- BREAK/news
- analysis
- opinion
- contrarian take
- technical breakdown
- education
- guide
- checklist
- "what this means"
- investor/degen preparation
- user behavior
- protocol mechanics
- onchain behavior
- business/incentive analysis
- comparison
- narrative
- cultural observation
- myth vs reality
- simple explainer
- unusual question
- experiment
- timeline
- case study
- other forms suggested by the subject

Do not output the large pool.

Filter it aggressively.

Return only the 2 or 3 strongest ideas.

CRITICAL:

The subject determines the direction.

Do not force a predefined content type.

Do not turn every subject into:

"Why this matters"

"Everything you need to know"

"The future of crypto"

"5 things to know"

Those are generic.

The final ideas should feel like actual things the
creator could sit down and make.

Each idea must contain a real premise.

BAD:

"Write about Arc mainnet."

GOOD:

"Use the September 16 launch as a deadline: what should
someone actually have ready before the chain goes live,
and which things are worth doing now rather than after
launch?"

BAD:

"Explain Arc."

GOOD:

"Break down the one thing an investor/degen should
understand before interacting with Arc on day one."

QUALITY FILTER:

Reject ideas that are:

- generic
- vague
- obvious
- just article titles
- merely summaries of the research
- unrelated to the subject
- repetitive
- dependent on speculation
- manufactured controversy
- too broad to execute

Prefer ideas with:

- a clear question
- tension
- a useful insight
- a strong opinion
- a surprising observation
- practical value
- human behavior
- a specific story
- a clear reason to care

The creator wants to choose an idea and then write or
create it themselves.

Therefore:

DO NOT write the finished post.

DO NOT write a full draft.

Give them the creative direction.

OUTPUT EXACTLY 2 OR 3 IDEAS.

Use:

IDEA 1:
FORMAT:
HOOK / PREMISE:
ANGLE:
WHAT TO EXPLORE:
WHY THIS IS INTERESTING:
SOURCES:

IDEA 2:
FORMAT:
HOOK / PREMISE:
ANGLE:
WHAT TO EXPLORE:
WHY THIS IS INTERESTING:
SOURCES:

IDEA 3:
FORMAT:
HOOK / PREMISE:
ANGLE:
WHAT TO EXPLORE:
WHY THIS IS INTERESTING:
SOURCES:

If only two are genuinely strong, return two.

All factual claims must be grounded in the research.
""".strip()


def generate_creative_ideas(
    mode,
    request_text,
    research,
):
    mode = (
        str(mode)
        .strip()
        .lower()
    )

    request_text = (
        str(request_text)
        .strip()
    )

    if not request_text:
        raise ValueError(
            "Idea request cannot be empty."
        )

    if mode == "meme":
        prompt = build_meme_idea_prompt(
            request_text,
            research,
        )

    elif mode == "post":
        prompt = build_post_idea_prompt(
            request_text,
            research,
        )

    else:
        raise ValueError(
            "Unknown idea mode. "
            "Use 'meme' or 'post'."
        )

    response = call_writer(
        prompt,
        temperature=1.0,
        max_tokens=1800,
    )

    if not response:
        raise RuntimeError(
            "No creative ideas were generated."
        )

    return response


# ============================================================
# LEGACY IDEAS
# ============================================================

def generate_ideas(
    request_text,
    research,
):
    """
    Legacy compatibility wrapper.

    Existing /ideas continues to work while the new
    /idea command uses generate_creative_ideas().
    """

    writer_profile = load_writer_profile()
    research_text = build_research_text(
        research
    )

    prompt = f"""
You are a senior crypto creator.

Generate exactly 3 useful content ideas about:

{request_text}

CREATOR PROFILE:

{writer_profile}

RESEARCH:

{research_text}

Rules:

- Stay tightly relevant to the subject.
- Do not invent facts.
- Do not produce generic topics.
- Do not repeat the same angle.
- Think like a creator, not an SEO strategist.
- Each idea must have a distinct premise.
- The ideas must be things the creator could actually
  turn into a post, comic, visual, breakdown or guide.

Return:

IDEA 1:
TITLE:
...
ANGLE:
...
WHY IT'S INTERESTING:
...
SOURCES:
...

IDEA 2:
TITLE:
...
ANGLE:
...
WHY IT'S INTERESTING:
...
SOURCES:
...

IDEA 3:
TITLE:
...
ANGLE:
...
WHY IT'S INTERESTING:
...
SOURCES:
...
""".strip()

    return call_writer(
        prompt,
        temperature=0.9,
        max_tokens=1200,
    )