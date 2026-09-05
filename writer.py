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

        content = content[:900]

        sections.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"FACTS/CONTEXT: {content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sections)


# ============================================================
# MEME IDEA GENERATION
# ============================================================

def build_meme_idea_prompt(
    situation,
    research,
):
    writer_profile = load_writer_profile()
    research_text = build_idea_research_text(
        research
    )

    return f"""
You are the senior creative director for a distinctive crypto
creator brand.

Your job is to find the BEST CREATIVE IDEA hidden inside a real
crypto situation.

You are not a content strategist.
You are not an SEO writer.
You are not a headline generator.

The creator makes simple, memorable crypto stories using humor,
irony, visual thinking, human behavior and sharp observations.

The final idea should feel like something a talented human
creator thought of after noticing something strange about the
situation.

CREATOR PROFILE:

{writer_profile}

USER'S SITUATION:

{situation}

RESEARCH:

{research_text}


============================================================
1. ESTABLISH THE FACTS
============================================================

Privately determine:

- What is actually confirmed?
- What is interpretation?
- What is genuinely unusual?
- What behavior, contradiction, irony or tension exists?

The user's description is NOT automatically factual.

Research is the factual boundary.

Never invent:
- rules
- restrictions
- quotes
- dialogue
- numbers
- motives
- outcomes
- capabilities
- consequences

If something is unknown, do not present it as fact.


============================================================
2. FIND THE OBSERVATION
============================================================

Do NOT immediately turn the main fact into a meme.

Look one layer deeper.

Ask privately:

"What is funny, strange, ironic, absurd or revealing about
this situation?"

Look for:

- an unexpected contrast
- human behavior
- irony
- contradiction
- social dynamics
- a strange consequence
- an awkward situation
- something that feels backwards
- something that resembles an ordinary real-world situation
- an exaggerated but understandable metaphor
- a visual contradiction
- a tiny detail that reveals the larger story

The strongest idea may be about the BEHAVIOR around the event,
not the event itself.


============================================================
3. GENERATE A LARGE PRIVATE POSSIBILITY POOL
============================================================

Privately explore many different creative directions.

Do not show this process.

Try radically different possibilities:

- deadpan observation
- absurd comparison
- visual metaphor
- text comic
- single-panel sketch
- multi-panel comic
- fake warning
- receipt
- instruction manual
- screenshot
- handwritten note
- chart gag
- diagram gag
- before/after
- product packaging
- courtroom
- emergency broadcast
- ordinary everyday situation
- character interaction
- completely character-free visual joke

Characters are OPTIONAL.

Do not use a character merely because characters exist
in the brand.


============================================================
4. THE SECOND-ORDER RULE
============================================================

This is critical.

Do NOT make the obvious fact itself the punchline.

BAD:

"Arc has institutional validators."

→ Draw institutions around Arc.

BAD:

"Validators are permissioned."

→ Draw a security guard saying access denied.

BAD:

"Arc is an open L1."

→ Draw an open door that is actually closed.

Those simply illustrate the headline.

BETTER:

Find the strange HUMAN or CULTURAL situation created by
the underlying facts.

The factual situation is the INPUT.

The observation is the JOKE.


============================================================
5. SIMPLIFY
============================================================

After exploring many possibilities, simplify aggressively.

The winning idea should normally contain:

ONE observation.
ONE visual premise.
ONE joke.
ONE punchline.

A viewer should understand the basic premise almost immediately.

Prefer:

a clever sign

a strange object

a ridiculous comparison

a tiny visual detail

a short exchange

a simple drawing

over:

large scenes

many characters

many labels

many logos

infographics

complicated diagrams

long explanations


============================================================
6. ORIGINALITY FILTER
============================================================

Reject any idea that could be used for almost any crypto story.

Reject:

- generic FOMO
- generic greed
- generic "wen moon"
- generic trader crying
- generic market going crazy
- generic rocket
- generic rug pull
- generic "institutional money"
- generic reaction meme
- generic security guard
- generic locked door
- generic "permission denied"

UNLESS the specific situation creates a genuinely new
version of that joke.

The idea must depend on THIS situation.


============================================================
7. DUPLICATION FILTER
============================================================

The 2–3 final ideas MUST NOT be the same joke expressed
through different formats.

For example:

security guard + institutions

permission denied + institutions

locked room + institutions

are ONE IDEA.

Choose only one.

The other ideas must come from different observations.


============================================================
8. FACTUAL DISCIPLINE
============================================================

The creative idea may exaggerate the VISUAL METAPHOR.

It may NOT exaggerate the FACT.

Example:

Acceptable:
A ridiculous boardroom metaphor for a permissioned validator
structure.

Not acceptable:
Claiming ordinary users are prohibited from using the network
if the research does not establish that.

Keep factual statements precise.

The joke can be absurd.

The facts cannot.


============================================================
9. SELECT
============================================================

From the private possibility pool, keep only the strongest
2 or 3.

Rank internally by:

1. Originality
2. Strength of observation
3. Immediate understanding
4. Simplicity
5. Punchline
6. Visual memorability
7. Dependence on the actual situation
8. Ease of execution

If only two are genuinely strong, return two.

Never add a weak third idea just to reach three.


============================================================
OUTPUT
============================================================

Return ONLY the final ideas.

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

Do not explain the creative process.

Do not explain why the idea is good.

Do not use phrases such as:

"this positions the creator"
"this appeals to the audience"
"this would perform well"
"content opportunity"
"engagement"
"brand positioning"

Do not write the finished social-media post.

Do not write a strategy document.

Give the creator the actual idea they can make.

Every factual element must be supported by the research.
""".strip()


# ============================================================
# POST IDEA GENERATION
# ============================================================

def build_post_idea_prompt(
    subject,
    research,
):
    writer_profile = load_writer_profile()
    research_text = build_idea_research_text(
        research
    )

    return f"""
You are the senior creative director for a distinctive crypto
creator.

Your job is to discover the strongest STORY or OBSERVATION
inside a subject.

You are not generating generic "content ideas".

You are finding something specific that is actually worth
writing about.

CREATOR PROFILE:

{writer_profile}

SUBJECT:

{subject}

RESEARCH:

{research_text}


============================================================
1. FACTS FIRST
============================================================

Privately establish:

- what happened
- what changed
- what is confirmed
- what is uncertain
- what people may misunderstand
- what behavior or incentive is involved
- what is unusual

Separate facts from interpretation.

Never manufacture certainty.


============================================================
2. FIND THE REAL STORY
============================================================

Do not simply summarize the subject.

Look underneath it.

Ask:

"What is the interesting thing here that most people could
easily miss?"

Look for:

- tension
- contradiction
- unexpected behavior
- incentives
- trade-offs
- technical mechanics
- human behavior
- practical consequences
- an assumption that deserves testing
- something people are interpreting incorrectly
- a question created by the facts
- a useful mental model
- a surprising connection


============================================================
3. EXPLORE DIFFERENT DIRECTIONS
============================================================

Privately generate a large possibility pool.

Explore different kinds of stories:

- technical breakdown
- simple explanation
- contrarian observation
- practical guide
- opinion
- case study
- timeline
- mechanism
- user behavior
- builder perspective
- investor perspective
- incentive analysis
- business model
- myth vs reality
- overlooked detail
- "the part people are missing"
- "what happens next"
- practical preparation
- unusual question

Do not force the subject into a category.

The subject determines the story.


============================================================
4. SPECIFICITY FILTER
============================================================

Reject broad ideas.

BAD:

"Why Arc matters."

"Everything you need to know about Arc."

"The future of stablecoins."

"Why institutional adoption matters."

GOOD:

A specific question, mechanism, contradiction or observation
that gives the creator something concrete to investigate.


============================================================
5. NO GENERIC CONTENT LANGUAGE
============================================================

Do not describe an idea using:

"content opportunity"

"audience"

"engagement"

"positioning"

"brand"

"this will perform well"

"this appeals to"

Instead describe the actual story.

The idea should explain what the creator would actually
investigate, explain, question or argue.


============================================================
6. FACTUAL DISCIPLINE
============================================================

Do not turn assumptions into facts.

Do not manufacture controversy.

Do not invent motives.

Do not invent outcomes.

Do not make bullish or bearish conclusions unless the
research supports them.

Interpretation is allowed.

Certainty without evidence is not.


============================================================
7. DUPLICATION FILTER
============================================================

The final ideas must be genuinely different.

Do not return three versions of:

"Why this matters."

Each idea must have a different central observation or
question.


============================================================
8. SELECT
============================================================

Keep only the strongest 2 or 3.

Rank internally by:

1. Strength of observation
2. Specificity
3. Interesting tension
4. Originality
5. Factual grounding
6. Usefulness
7. Room for a strong opening
8. Room for a memorable conclusion

If only two are genuinely strong, return two.


============================================================
OUTPUT
============================================================

Return ONLY the final ideas.

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

Do not write the finished post.

Do not explain the creative process.

Give the creator the actual story direction.

All factual claims must be grounded in the research.
""".strip()


# ============================================================
# CREATIVE IDEA GENERATION
# ============================================================

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