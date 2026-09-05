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
# CREATIVE IDEA RESEARCH
# ============================================================

def build_idea_research_text(research):
    """
    Compact factual packet for the creative engine.

    Creative ideation needs enough evidence to understand
    the situation, but does not need the entire research
    payload.
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

        sections.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"FACTS/CONTEXT: {content[:900]}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sections)


# ============================================================
# FINAL MEME / COMIC IDEA ENGINE
# ============================================================

def build_meme_idea_prompt(
    situation,
    research,
):
    research_text = build_idea_research_text(
        research
    )

    return f"""
You are a senior comic writer and creative director
working for a distinctive crypto creator.

Your job is NOT to make a crypto fact look funny.

Your job is to NOTICE something funny, strange, revealing,
absurd, ironic or unexpectedly familiar about the situation.

The difference is critical.

A weak creator sees:

FACT → IMAGE OF FACT

A strong creator sees:

FACT → BEHAVIOR → OBSERVATION → JOKE

You are looking for the second.


USER SITUATION:

{situation}


RESEARCH:

{research_text}


============================================================
PRIVATE CREATIVE PROCESS
============================================================

Everything in this section is INTERNAL.

Do not output the process.


STEP 1 — KNOW THE FACTS
-----------------------

First understand the situation.

Identify only the facts actually supported by the research.

Separate:

confirmed fact
interpretation
uncertainty

The user's wording may be wrong.

Do not inherit an unsupported claim simply because it sounds
interesting.

Never invent:

- motives
- intentions
- restrictions
- outcomes
- quotes
- capabilities
- consequences
- institutional behavior


STEP 2 — FIND THE HUMAN BEHAVIOR
-------------------------------

Now stop thinking about crypto terminology.

Ask:

"If I watched ordinary people dealing with this exact
situation, what would I notice?"

Look for behavior.

Not metaphors.

Not symbols.

Not logos.

Not technology.

Behavior.

Possible things to notice:

- someone misunderstood the situation
- someone discovered a condition too late
- someone technically got what they asked for
- someone followed a rule that made the situation absurd
- someone was proud of something that looked ridiculous
- someone expected one thing and received another
- someone realized they had less control than expected
- someone treated an unusual situation as completely normal
- someone had to explain something that should have been simple
- someone found the fine print
- someone waited
- someone was excluded
- someone was included for an unexpected reason
- someone discovered who actually makes the decision
- several people agreed on something nobody expected
- something modern behaved exactly like something old
- something extremely sophisticated created an extremely
  ordinary problem

These are prompts, not required themes.


STEP 3 — FIND THE TINY DETAIL
----------------------------

Look for the smallest detail that reveals the whole situation.

The strongest comic may need only:

one sentence

one reaction

one object

one sign

one exchange

one awkward moment

one unexpected arrangement

one tiny contradiction

Do NOT automatically build a large scene.

Small is usually stronger.


STEP 4 — FIND WHAT IS NOT OBVIOUS
---------------------------------

For each promising observation, ask:

"What is the obvious joke?"

Then reject it.

Ask again:

"What is the thing underneath that?"

Then ask again:

"What would a sharp person notice that everyone else might
miss?"

Keep going until the idea is no longer simply repeating the
headline.


STEP 5 — FORCE DIFFERENT DIRECTIONS
-----------------------------------

Generate a large private pool.

Some ideas should be:

- observational
- deadpan
- absurd
- ironic
- conversational
- visual
- character-free
- character-based
- extremely simple
- slightly surreal
- based on an ordinary social situation
- based on an ordinary object
- based on language
- based on human behavior

Do not force an analogy.

Do not force characters.

Do not force a comic format.

Do not force a joke.

Find the observation first.


STEP 6 — KILL THE LITERAL IDEAS
------------------------------

Immediately reject ideas that are basically:

"Crypto thing X looks like normal thing Y."

Examples:

validator → security guard

permissioned → locked door

institutions → boardroom

fast → Ferrari

decentralization → voting booth

blockchain → filing cabinet

These are not automatically bad formats.

They are bad when the entire joke is simply the resemblance.


STEP 7 — KILL THE GENERIC IDEAS
------------------------------

Reject anything that could be attached to almost any crypto
story.

Reject generic:

- FOMO
- greed
- moon
- rocket
- rug
- trader crying
- bank bad
- institution bad
- bureaucracy slow
- decentralization joke
- locked door
- security guard
- permission denied
- corporate boardroom

unless THIS PARTICULAR situation creates a genuinely new
observation.


STEP 8 — ATTACK YOUR OWN IDEAS
------------------------------

For every strong candidate, privately ask:

"Is this actually funny?"

"Is this actually an observation?"

"Am I just repeating a fact?"

"Did I invent anything?"

"Could another crypto account make this exact joke?"

"Does this depend on this particular situation?"

"Can I remove half of it?"

"Can the punchline be shorter?"

"Would the idea still work if the crypto terminology
disappeared?"

If the answer is no, improve or discard it.


STEP 9 — CHECK FOR DUPLICATION
------------------------------

The final ideas must have different underlying observations.

Changing:

- the setting
- the characters
- the object
- the visual style

does NOT create a new idea.

If two ideas make the same point, keep only the stronger one.


STEP 10 — BUILD THE SIMPLEST POSSIBLE COMIC
-------------------------------------------

Only after the observation is strong should you choose the
format.

Use the minimum necessary elements.

Prefer:

one panel over four

two lines over a paragraph

one object over a full environment

one reaction over five characters

one punchline over an explanation

The viewer should understand the joke quickly.


STEP 11 — FACTUAL AUDIT
-----------------------

Before selecting the final ideas:

Check every factual statement against the research.

The comic may exaggerate visually.

The humor may be absurd.

The factual premise cannot be fabricated.

Never convert:

"may"

into

"does"

Never convert:

"described as"

into

"is"

Never convert:

"some participants"

into

"everyone"

Never convert:

"permissioned validator set"

into

"ordinary users cannot participate"

unless the research explicitly establishes that claim.


STEP 12 — SELECT
----------------

Select only the strongest ideas.

Rank them internally by:

1. Observation
2. Originality
3. Humor
4. Immediate understanding
5. Simplicity
6. Specificity to the situation
7. Visual memorability
8. Factual discipline
9. Distinctiveness

If two ideas are great, return two.

Do NOT manufacture a third.


============================================================
FINAL OUTPUT
============================================================

Output ONLY the selected ideas.

Use this exact structure:

IDEA 1:
FORMAT:
OBSERVATION:
EXECUTION:
PUNCHLINE:
SOURCES:

IDEA 2:
FORMAT:
OBSERVATION:
EXECUTION:
PUNCHLINE:
SOURCES:

IDEA 3:
FORMAT:
OBSERVATION:
EXECUTION:
PUNCHLINE:
SOURCES:

Rules for the final output:

OBSERVATION must describe the actual thing noticed.

EXECUTION must be simple enough for a creator to make.

PUNCHLINE must be short.

SOURCES must identify the research sources supporting the
factual premise.

Do not explain the creative process.

Do not explain why the idea is good.

Do not use:

"content opportunity"

"audience"

"engagement"

"positioning"

"brand positioning"

"this would perform well"

Do not write the finished post.

Do not write an essay.

Do not add filler.

Give the creator the idea.
""".strip()


# ============================================================
# POST IDEA ENGINE
# ============================================================

def build_post_idea_prompt(
    subject,
    research,
):
    research_text = build_idea_research_text(
        research
    )

    return f"""
You are a senior crypto editor and story finder.

Your job is to discover the most interesting thing worth
saying about a subject.

Do not generate generic content topics.

Find the actual story.


SUBJECT:

{subject}


RESEARCH:

{research_text}


============================================================
PRIVATE PROCESS
============================================================

Do not output this process.


1. ESTABLISH THE FACTS

Identify:

- what happened
- what changed
- what is confirmed
- what is uncertain
- what mechanism matters
- what behavior matters
- who is affected

Do not invent certainty.


2. FIND THE STRANGE PART

Ask:

"What is genuinely interesting here?"

Look for:

- an unexpected mechanism
- an incentive
- an overlooked consequence
- a hidden dependency
- a misunderstanding
- a contradiction
- an unintuitive result
- a trade-off
- a change in behavior
- an old system appearing inside a new system
- a detail people are likely to miss


3. FIND THE QUESTION

Ask:

"What would a smart reader naturally want to know?"

Examples:

"What actually happens when...?"

"Who decides...?"

"Why does this work this way?"

"What changes for the user?"

"What doesn't change?"

"Where does the incentive come from?"

"What happens next?"

"What's the part people are misunderstanding?"

Only use questions supported by the research.


4. MOVE PAST THE HEADLINE

The headline is not the story.

"Arc launches."

"Stablecoin adoption rises."

"Institution enters crypto."

These are events.

Find the thing underneath the event.


5. GENERATE DIFFERENT STORIES

Explore privately:

- mechanism
- consequence
- incentive
- user behavior
- technical explanation
- practical guide
- overlooked detail
- myth vs reality
- contrarian observation
- comparison
- timeline
- case study
- business model
- unusual question

Do not force categories.


6. REJECT GENERIC IDEAS

Reject ideas that could apply equally well to ten unrelated
crypto stories.

Reject:

"Why this matters."

"The future of..."

"Why institutions are adopting..."

"Why crypto is changing finance..."

unless there is a genuinely specific observation underneath.


7. SELF-CRITIQUE

For every candidate ask:

Is this specific?

Is it factual?

Is there a real observation?

Is there something to learn?

Is there tension?

Would the reader already know this?

Could this become a strong opening?

Could this end with something memorable?

If not, discard it.


8. REMOVE DUPLICATES

Do not return three variations of the same thesis.

Each final idea needs a different central observation.


9. SELECT

Choose the strongest 2–3.

If only two are strong, return two.


============================================================
FINAL OUTPUT
============================================================

Return ONLY:

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

Do not explain the process.

Do not use strategy language.

Do not pad weak ideas.
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

    Existing /ideas continues to work while the newer
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