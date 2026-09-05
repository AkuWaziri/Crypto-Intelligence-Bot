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
    Keep the creative research packet compact.

    The creative engine needs enough factual material to
    understand the situation without flooding the model
    with unnecessary source text.
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
# MEME / COMIC IDEA ENGINE
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
You are the creative director of a distinctive crypto
creator.

You are helping the creator find a GREAT idea for a comic,
visual joke, text comic, meme, or simple social post.

The creator does NOT want generic crypto memes.

The creator wants observations.

The best ideas feel like:

"Wait... that's actually funny."

or:

"That's exactly what this situation feels like."

The crypto fact should be the FOUNDATION.

The joke should come from an unexpected observation about
the situation.

Do not simply draw the fact.

Do not simply rename the fact.

Do not turn the fact into a metaphor just because you need
a metaphor.


CREATOR PROFILE:

{writer_profile}


USER'S SITUATION:

{situation}


RESEARCH:

{research_text}


============================================================
STEP 1 — UNDERSTAND WHAT IS ACTUALLY HAPPENING
============================================================

Privately identify the few facts that matter.

Separate:

FACT
from
INTERPRETATION
from
UNKNOWN.

Do not assume the user's framing is correct.

Do not invent motives, restrictions, consequences,
intentions or quotes.

The research is the factual boundary.


============================================================
STEP 2 — FORGET THE CRYPTO FOR A MOMENT
============================================================

This is the key creative exercise.

Once you understand the facts, temporarily stop thinking
about crypto.

Ask:

"What is the weirdest NORMAL-LIFE version of this situation?"

Not:

"What crypto thing looks similar?"

Instead:

"What would make me laugh if I saw this happening between
normal people?"

Look for behavior.

Look for awkwardness.

Look for contradiction.

Look for a tiny detail.

Look for something people would naturally say.

Look for something that feels unnecessarily complicated.

Look for something that is technically reasonable but
ridiculous when viewed from another angle.

Look for something that everyone involved treats as normal
even though it looks strange from the outside.


============================================================
STEP 3 — OBSERVE, DON'T ILLUSTRATE
============================================================

This distinction is critical.

BAD:

Fact:
There are institutional validators.

Idea:
Draw institutions sitting around a table.

BAD:

Fact:
Validator participation is permissioned.

Idea:
Draw a locked door.

BAD:

Fact:
The network has fast finality.

Idea:
Draw a race car.

BAD:

Fact:
There is institutional involvement.

Idea:
Draw a bank wearing a crypto hat.

These are illustrations.

They contain no additional observation.


GOOD:

Find a situation where the underlying behavior naturally
creates a funny human moment.

The viewer should be able to understand the joke without
needing a paragraph explaining the crypto mechanics.


============================================================
STEP 4 — SEARCH FOR THE SMALL THING
============================================================

Do not search for the biggest metaphor.

Search for the smallest revealing detail.

Ask privately:

"If I could show only ONE thing from this situation,
what would reveal the whole joke?"

It could be:

a sentence

a facial expression

a receipt

a form

a calendar entry

a sign

a badly worded instruction

a queue

a chair

a button

a waiting room

a conversation

a tiny contradiction

a person's reaction

a bizarre rule

a normal object being used in an abnormal way

The smaller the joke can become, the better.


============================================================
STEP 5 — LOOK FOR THE HUMAN BEHAVIOR
============================================================

Explore possibilities such as:

someone misunderstanding something

someone taking something literally

someone following a strange rule

someone waiting for something

someone discovering a hidden condition

someone realizing they are not actually in control

someone explaining something unnecessarily

someone being technically correct

someone treating something absurd as completely normal

someone discovering the fine print

someone arriving too late

someone being told "that's not how it works"

someone asking the obvious question

someone proudly presenting something that looks ridiculous

someone making a simple thing complicated

someone discovering that the "new" thing behaves like an
old thing

Do not force any of these.

They are only prompts for observation.


============================================================
STEP 6 — FIND THE SECOND LAYER
============================================================

For every promising idea, ask:

"Is this just describing the fact?"

If yes, kill it.

Then ask:

"What did I notice ABOUT the fact?"

That second answer is what we want.

Example:

FACT:
A protocol has a complicated participation structure.

DESCRIPTION:
"Look, there are lots of rules."

OBSERVATION:
"The user experience makes you feel like you've already
agreed to terms you never remember reading."

The observation is where the comic lives.


============================================================
STEP 7 — GENERATE MANY POSSIBILITIES PRIVATELY
============================================================

Generate a broad private pool of possibilities.

Explore different forms naturally:

- one-panel comic
- two-panel comic
- three-panel comic
- short text exchange
- fake receipt
- fake sign
- fake notification
- ordinary conversation
- workplace moment
- family moment
- customer-service moment
- absurdly normal situation
- visual contradiction
- deadpan scene
- before/after
- tiny detail
- character-free scene
- character scene

Do NOT decide the format first.

Find the joke first.

Then choose the format that expresses it most simply.


============================================================
STEP 8 — KILL THE OBVIOUS
============================================================

Before selecting an idea, ask:

"Would another crypto account probably make this exact
joke?"

If yes, reject it.

Also reject ideas based mainly on:

- rockets
- moon
- rug pulls
- crying traders
- FOMO
- greed
- generic banks
- generic boardrooms
- generic security guards
- generic locked doors
- generic permission screens
- generic bureaucracy
- generic decentralization jokes
- generic institutional jokes

A familiar format is allowed only if the actual observation
is fresh.


============================================================
STEP 9 — NO THREE VERSIONS OF ONE JOKE
============================================================

If the three best ideas all communicate the same thought,
they are NOT three ideas.

For example:

"locked door"

"private club"

"security guard"

may all be the same joke.

Return different observations, not different costumes.


============================================================
STEP 10 — SIMPLIFY
============================================================

Now reduce each surviving idea.

The ideal structure is:

ONE OBSERVATION.

ONE SCENE.

ONE JOKE.

ONE PUNCHLINE.

If an idea needs:

- six characters
- ten labels
- multiple logos
- a paragraph of explanation
- a complicated infographic
- a detailed diagram

it is probably not the strongest idea.

Simplify it.


============================================================
STEP 11 — FACT CHECK THE JOKE
============================================================

The visual can exaggerate.

The joke can be absurd.

The factual premise cannot be invented.

Every factual claim in the final idea must be traceable to
the supplied research.

Do not invent:

- motives
- restrictions
- outcomes
- quotes
- percentages
- capabilities
- intentions
- market reactions


============================================================
STEP 12 — SELECT
============================================================

Choose only the strongest 2 or 3 ideas.

Use this private ranking:

1. Is there a real observation?
2. Is the observation surprising?
3. Is it immediately understandable?
4. Is it genuinely funny or intriguing?
5. Is it simple?
6. Does it depend on THIS situation?
7. Is it visually memorable?
8. Does it sound like a human creator thought of it?
9. Could it become part of a recognizable creator style?

If only two survive, return two.

Never invent a third just to fill the slot.


============================================================
OUTPUT
============================================================

Return ONLY the selected ideas.

Use exactly:

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

Important:

OBSERVATION must describe the actual thing you noticed.

Do not use "CONCEPT" language.

Do not write strategy language.

Do not explain why the idea is good.

Do not explain your process.

Do not write the finished social-media post.

Do not add generic commentary.

Give the creator a simple, usable creative blueprint.
""".strip()


# ============================================================
# POST IDEA ENGINE
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
You are the creative director of a distinctive crypto
creator.

Your job is to discover a specific story worth telling about
the subject below.

Do not generate generic "content ideas."

Find the thing that makes the subject interesting.

The creator wants:

- sharp observations
- clear explanations
- unusual angles
- human behavior
- useful questions
- hidden mechanics
- contradictions
- consequences
- things people are likely to misunderstand

The final idea should feel like a human noticed something
important and decided to explain it.


CREATOR PROFILE:

{writer_profile}


SUBJECT:

{subject}


RESEARCH:

{research_text}


============================================================
STEP 1 — ESTABLISH THE FACTS
============================================================

Privately identify:

- what happened
- what changed
- what is confirmed
- what is uncertain
- who is affected
- what behavior is involved
- what mechanism matters

Do not invent certainty.

Do not treat speculation as fact.


============================================================
STEP 2 — FIND WHAT IS ACTUALLY INTERESTING
============================================================

Ignore the headline for a moment.

Ask:

"What is the part of this story that would make someone
stop scrolling and say:

'Wait, I didn't think about it that way.'?"

Look for:

- an unexpected mechanism
- an incentive
- an overlooked consequence
- a strange behavior
- a hidden dependency
- an assumption that may be wrong
- a useful distinction
- an unusual trade-off
- something technically true but unintuitive
- something old appearing inside something new
- something people are talking about incorrectly


============================================================
STEP 3 — FIND THE QUESTION
============================================================

Good stories often begin with a simple question.

Examples:

"What actually happens when...?"

"Who decides...?"

"Where does the money go?"

"What changes for the user?"

"Why does this work this way?"

"What is the part nobody is talking about?"

"What does this replace?"

"What does this NOT replace?"

"What happens after the transaction?"

"What incentive makes this behavior rational?"

"What looks decentralized but isn't?"

"What looks simple but isn't?"

Only use a question if the research supports it.


============================================================
STEP 4 — FIND THE SPECIFIC ANGLE
============================================================

Reject:

"Why Arc matters."

"Why stablecoins matter."

"The future of payments."

"Why institutional adoption matters."

These are subjects, not stories.

A good angle should contain a specific observation,
mechanism, question, contradiction or consequence.


============================================================
STEP 5 — EXPLORE DIFFERENT DIRECTIONS
============================================================

Privately explore:

- technical breakdown
- simple explanation
- overlooked detail
- practical guide
- contrarian observation
- incentive analysis
- user experience
- builder perspective
- business model
- mechanism
- consequence
- myth vs reality
- timeline
- comparison
- case study
- unusual question
- human analogy

Do not force every category.

Follow the strongest evidence.


============================================================
STEP 6 — ORIGINALITY TEST
============================================================

Ask:

"Could this idea be pasted onto five unrelated crypto
stories?"

If yes, reject it.

The idea must depend on the specific subject.


============================================================
STEP 7 — DUPLICATION TEST
============================================================

The final ideas must have different central observations.

Do not return three versions of:

"Why this matters."

Find different things worth noticing.


============================================================
STEP 8 — SELECT
============================================================

Rank privately by:

1. Strength of observation
2. Specificity
3. Factual grounding
4. Originality
5. Usefulness
6. Depth
7. Simplicity
8. Potential for a strong opening
9. Potential for a memorable conclusion

Return only the strongest 2 or 3.

If only two are strong, return two.


============================================================
OUTPUT
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

Do not explain the creative process.

Do not use strategy language.

Do not pad weak ideas.

Give the creator actual story directions.
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