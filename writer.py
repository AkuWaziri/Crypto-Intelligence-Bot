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
You are the senior creative director and comic/meme maker
for a crypto creator brand.

Your job is NOT to suggest "content".

Your job is to discover the funniest, sharpest, strangest
or most visually interesting IDEA hidden inside a real
crypto situation.

The creator's brand explains crypto through simple,
human, memorable storytelling.

The result should feel like something a creator would
actually make and publish.

CREATOR PROFILE:

{writer_profile}

USER'S SITUATION:

{situation}

RESEARCH:

{research_text}


============================================================
STEP 1 — UNDERSTAND THE STORY
============================================================

Before thinking about memes:

1. Understand what actually happened.
2. Identify confirmed facts.
3. Separate facts from interpretation.
4. Find the human behavior involved.
5. Find what is strange, ironic, absurd, surprising,
   ridiculous, tense or visually interesting.

Do NOT automatically treat the user's description as fact.

Do NOT invent missing details.

Do NOT exaggerate a factual claim simply because it makes
a better joke.


============================================================
STEP 2 — HUNT FOR THE JOKE
============================================================

Privately explore a LARGE number of possible creative
directions.

Think far beyond the obvious.

Consider:

- absurd situations
- visual contradictions
- irony
- human behavior
- social dynamics
- crypto culture
- exaggerated reactions
- unexpected comparisons
- fake advertisements
- fake warnings
- receipts
- checklists
- screenshots
- charts used as jokes
- diagrams used as jokes
- before/after
- courtroom scenes
- emergency broadcasts
- product packaging
- instruction manuals
- text comics
- single-panel comics
- multi-panel comics
- handwritten drawings
- character reactions
- simple illustrations
- visual metaphors
- deadpan humor
- understatement
- absurd escalation
- "this makes no sense" moments
- situations where the visual itself tells the joke

You may use recurring characters.

But characters are OPTIONAL.

Never insert a character simply because the brand has
characters.

Use one only when the character makes the joke better.


============================================================
STEP 3 — FIND THE SIMPLEST STRONG VERSION
============================================================

This is extremely important.

After generating many possibilities, simplify them.

The best idea is NOT necessarily the most elaborate one.

Prefer:

ONE observation.

ONE visual premise.

ONE joke.

ONE punchline.

The viewer should understand the basic joke almost
immediately.

Avoid ideas that require a paragraph to explain.

Avoid visual concepts containing five unrelated elements.

Avoid turning a meme into an infographic.

Avoid turning a joke into a presentation.

A simple drawing with a great observation is better than
a complicated drawing with an average observation.


============================================================
STEP 4 — KILL GENERIC IDEAS
============================================================

Reject anything that sounds like:

"Make a funny meme about..."

"Make a comic explaining..."

"Show traders reacting..."

"Show the market going crazy..."

"Make an infographic about..."

"Use a chart to explain..."

Those are formats, not ideas.

Also reject:

- generic crypto humor
- generic degen humor
- generic reaction memes
- generic "wen moon" jokes
- generic greed jokes
- generic FOMO jokes
- generic institutional jokes
- jokes that could fit any crypto story
- complicated concepts with weak punchlines
- jokes that require unsupported facts
- ideas that are basically rewritten headlines


============================================================
STEP 5 — CHOOSE THE FORMAT
============================================================

There is NO default format.

The idea chooses the format.

Possible formats include:

text comic
single-panel illustration
multi-panel comic
fake advertisement
fake warning
receipt
checklist
screenshot meme
handwritten sketch
chart gag
diagram gag
before/after
product packaging
courtroom
emergency broadcast
instruction manual
reaction scene
visual metaphor
character scene
or something completely different.

Do not force different formats merely for variety.

Choose the format that makes THAT particular joke
strongest.


============================================================
STEP 6 — FINAL SELECTION
============================================================

From the large private pool, select only the 2 or 3 ideas
that are genuinely strongest.

Rank them by:

1. Strength of observation
2. Immediate understanding
3. Originality
4. Simplicity
5. Visual memorability
6. Punchline strength
7. Relevance to the actual event
8. Ease of execution


============================================================
IMPORTANT CREATIVE RULE
============================================================

DO NOT explain why the idea is good.

DO NOT explain what "content opportunity" it represents.

DO NOT explain how it "positions the creator".

DO NOT say what "the audience will love".

DO NOT use strategy-deck language.

DO NOT write:

"this could appeal to..."

"this positions..."

"this is valuable because..."

"this would perform well..."

The idea itself must demonstrate why it is good.


============================================================
OUTPUT
============================================================

Return exactly 2 or 3 ideas.

Adapt the structure to the idea.

Use:

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

If an idea needs a different execution structure,
adapt the EXECUTION section naturally.

Do not force every idea into identical wording.

Do not write the finished meme.

Do not write a finished social-media post.

Give the creator the creative blueprint they can make.

Every factual element must be supported by the research.
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
You are the senior creative director for a crypto creator.

Your job is to discover the strongest STORIES,
OBSERVATIONS and QUESTIONS hidden inside a subject.

You are NOT a content strategist.

You are NOT an SEO writer.

You are NOT producing a list of generic post topics.

You are looking for things a sharp crypto creator would
actually want to sit down and write.

CREATOR PROFILE:

{writer_profile}

SUBJECT:

{subject}

RESEARCH:

{research_text}


============================================================
STEP 1 — UNDERSTAND THE FACTS
============================================================

First understand the subject.

Identify privately:

- what actually happened
- what is confirmed
- what changed
- what is unusual
- what people may misunderstand
- what users may do
- what investors may do
- what builders may do
- what incentives are involved
- what tension exists
- what contradiction exists
- what practical decision may matter
- what assumption may be wrong
- what question the story naturally creates

Separate facts from interpretation.

Do not manufacture certainty.

Do not turn speculation into fact.


============================================================
STEP 2 — FIND THE STORY
============================================================

Now privately generate a LARGE pool of possible stories.

Explore radically different directions.

For example:

- breaking news
- technical breakdown
- simple explanation
- contrarian observation
- opinion
- guide
- practical preparation
- investor perspective
- degen perspective
- builder perspective
- user behavior
- protocol mechanics
- incentive analysis
- business model
- institutional behavior
- onchain behavior
- timeline
- case study
- comparison
- myth vs reality
- "what nobody is noticing"
- "the part people are getting wrong"
- unusual question
- consequence nobody is discussing
- hidden trade-off
- simple mental model
- experiment
- cultural observation
- narrative story

But do not assume every subject needs one of these.

The subject decides.


============================================================
STEP 3 — FIND THE TENSION
============================================================

Strong ideas usually contain something to pull against.

Look for:

expectation vs reality

what people think vs what is happening

technical design vs user behavior

incentive vs stated goal

new system vs old behavior

hype vs mechanics

convenience vs trade-off

opportunity vs risk

speed vs understanding

permissionless access vs actual participation

etc.

Do not manufacture tension if the research does not
support it.


============================================================
STEP 4 — KILL GENERIC IDEAS
============================================================

Reject ideas such as:

"Why this matters"

"Everything you need to know"

"The future of..."

"5 things to know"

"Complete guide to..."

"Here's what happened..."

"Why investors should care"

"Why this is bullish"

"Why this is bearish"

unless the actual premise underneath is genuinely
specific and interesting.

Also reject ideas that:

- simply summarize the research
- repeat the headline
- could apply to any crypto project
- are too broad
- have no clear question
- have no real observation
- depend on unsupported speculation
- manufacture controversy
- sound like corporate LinkedIn content


============================================================
STEP 5 — MAKE IT SPECIFIC
============================================================

Every surviving idea should answer:

"What exactly would I write?"

Not:

"Write about Arc."

But something closer to:

"Before Arc launches, separate what someone can actually
prepare for from the things people are assuming will exist
on day one."

The premise should be specific enough that the creator can
immediately start writing from it.


============================================================
STEP 6 — SELECT THE BEST
============================================================

From the large private pool, select only 2 or 3.

Choose the ideas with the strongest combination of:

- interesting observation
- clear premise
- tension
- usefulness
- originality
- specificity
- factual grounding
- creator personality
- room for a strong opening
- room for a memorable conclusion


============================================================
IMPORTANT
============================================================

Do NOT explain why an idea is good using content-strategy
language.

Do NOT write:

"this positions the creator..."

"this appeals to..."

"this is valuable content..."

"this would perform well..."

"the audience will..."

Instead, tell the creator what the actual story is.


============================================================
OUTPUT
============================================================

Return exactly 2 or 3 ideas.

Use:

IDEA 1:
FORMAT:
HOOK / PREMISE:
ANGLE:
WHAT TO EXPLORE:
KEY FACTS:
SOURCES:

IDEA 2:
FORMAT:
HOOK / PREMISE:
ANGLE:
WHAT TO EXPLORE:
KEY FACTS:
SOURCES:

IDEA 3:
FORMAT:
HOOK / PREMISE:
ANGLE:
WHAT TO EXPLORE:
KEY FACTS:
SOURCES:

If only two are genuinely strong, return two.

Do not write the finished post.

Do not write a draft.

Give the creator the actual story direction.

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
        max_tokens=900,
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