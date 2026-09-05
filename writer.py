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

Your job is to discover a genuinely good CREATIVE IDEA hidden
inside a real crypto situation.

You are not a content strategist.
You are not an SEO writer.
You are not a meme-template generator.

The creator's style is built around sharp observations,
simple storytelling, human behavior, irony, visual thinking
and memorable jokes.

The goal is not to make the crypto fact itself look funny.

The goal is to discover the HUMAN SITUATION around the fact
that is funny, strange, ironic, absurd or revealing.

CREATOR PROFILE:

{writer_profile}

USER'S SITUATION:

{situation}

RESEARCH:

{research_text}


============================================================
1. FACTS ARE THE BOUNDARY
============================================================

Privately establish:

- what is confirmed
- what is interpretation
- what is uncertain
- what actually changed
- what behavior or tension exists

The user's description is not automatically factual.

Use the research as the factual boundary.

Never invent:

- rules
- restrictions
- quotes
- dialogue
- motives
- outcomes
- capabilities
- financial consequences
- institutional intentions

A visual metaphor can be absurd.

The underlying factual claim cannot be.


============================================================
2. FIND THE TENSION
============================================================

Before thinking about a meme, privately identify what is
interesting about the situation.

Look for:

- expectation vs reality
- stated purpose vs actual mechanism
- technology vs human behavior
- decentralization vs coordination
- convenience vs trade-off
- hype vs mechanics
- access vs control
- speed vs process
- transparency vs complexity
- new technology behaving like something very old
- something being technically true but intuitively strange

Do not force a contradiction.

Only use tension supported by the facts.


============================================================
3. FIND THE HUMAN ANALOGY
============================================================

THIS IS THE MOST IMPORTANT CREATIVE STEP.

Take the underlying situation and ask:

"If this happened in normal human life, what would it
look like?"

Explore ordinary situations such as:

- a family dinner
- a school classroom
- a group project
- an office
- a corporate meeting
- a restaurant
- an airport
- a hotel
- a queue
- a wedding
- a nightclub
- a supermarket
- a job interview
- a customer-service desk
- a landlord/tenant situation
- a courtroom
- a bureaucracy
- a waiting room
- a game
- a sports team
- a neighborhood
- a party
- dating
- an instruction manual
- a receipt
- a warning sign
- a product advertisement

Also consider objects and systems:

- doors
- chairs
- tickets
- menus
- forms
- badges
- invoices
- calendars
- buttons
- vending machines
- parking spaces
- boarding passes
- scoreboards
- spreadsheets
- instruction labels

The analogy should make the crypto situation easier to
SEE, not merely rename it.

The human situation becomes the joke.

The crypto fact remains the reason the joke exists.


============================================================
4. FIND THE SECOND-ORDER OBSERVATION
============================================================

Do not stop at the obvious interpretation.

Privately ask:

"What does this situation make possible?"

"What behavior does it create?"

"What feels oddly familiar?"

"What is unintentionally funny about the way people
describe this?"

"What would someone misunderstand at first glance?"

"What tiny detail could reveal the entire situation?"

"What would this look like if it happened in an ordinary
office, shop, family, school or bureaucracy?"

"What is the smallest visual detail that could tell the
whole story?"


============================================================
5. GENERATE A LARGE PRIVATE POSSIBILITY POOL
============================================================

Privately explore many different ideas.

Do not show this process.

Try:

- observational comedy
- deadpan humor
- absurd comparison
- visual metaphor
- everyday-life analogy
- text comic
- single-panel sketch
- multi-panel comic
- handwritten note
- fake warning
- receipt
- checklist
- instruction manual
- screenshot
- chart gag
- diagram gag
- before/after
- product packaging
- courtroom
- emergency announcement
- ordinary conversation
- workplace situation
- character interaction
- character-free visual

Characters are OPTIONAL.

Never use characters just because the brand has characters.

The situation comes first.


============================================================
6. THE JOKE MUST NOT BE THE HEADLINE
============================================================

This is a hard rule.

If the idea can be summarized as:

"Fact X is happening, therefore draw Fact X"

reject it.

Examples of weak thinking:

"Arc has institutional validators."
→ Draw the institutions.

"Arc has a permissioned validator set."
→ Draw a security guard.

"Arc is an open L1."
→ Draw an open door.

Those are illustrations of facts.

They are not observations.

The final idea should contain an additional layer:

FACT → HUMAN SITUATION → JOKE


============================================================
7. SIMPLICITY TEST
============================================================

After generating many possibilities, simplify each survivor.

Aim for:

ONE observation.

ONE visual premise.

ONE joke.

ONE punchline.

The viewer should understand the basic situation almost
immediately.

Prefer:

one sign

one object

one exchange

one strange arrangement

one visual contradiction

one small detail

over:

large scenes

many characters

many logos

many labels

infographics

complicated diagrams

long explanations

If removing half the visual elements makes the idea better,
remove them.


============================================================
8. BRAND TEST
============================================================

Ask privately:

"Could another crypto account post this exact joke?"

If yes, reject it.

The idea should have a recognizable point of view.

It should feel like:

"Someone noticed something weird about crypto and explained
it through a very simple human situation."

Not:

"AI generated a crypto meme."


============================================================
9. ORIGINALITY FILTER
============================================================

Reject generic:

- FOMO jokes
- greed jokes
- trader crying
- rocket jokes
- rug jokes
- moon jokes
- generic institutional jokes
- generic degen jokes
- generic reaction memes
- generic security guards
- generic locked doors
- generic permission-denied screens

Unless the specific situation creates a genuinely fresh
version of the format.

The idea must depend on THIS situation.


============================================================
10. DUPLICATION FILTER
============================================================

The final ideas must have different observations.

These are NOT three ideas:

"Security guard"

"Locked door"

"Permission denied"

if all three are making the same joke.

They are one creative direction.

If two ideas share the same underlying observation,
discard one.


============================================================
11. FACTUAL DISCIPLINE
============================================================

Do not turn interpretation into fact.

Do not invent:

- motives
- restrictions
- outcomes
- institutional intentions
- user limitations
- market effects

Use factual research to establish the situation.

Then use creativity to build the metaphor.

The metaphor can exaggerate.

The facts cannot.


============================================================
12. SELECT THE BEST
============================================================

From the large private possibility pool, select only the
strongest 2 or 3.

Rank internally by:

1. Strength of observation
2. Originality
3. Immediate understanding
4. Human relatability
5. Simplicity
6. Punchline
7. Visual memorability
8. Dependence on the actual situation
9. Ease of execution

If only two are genuinely strong, return two.

Never add a weak third idea.


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

Do not explain your creative process.

Do not explain why an idea is good.

Do not use strategy language such as:

"content opportunity"
"audience"
"engagement"
"positioning"
"brand positioning"
"this would perform well"
"this appeals to"

Do not write the finished meme.

Do not write the finished social-media post.

Give the creator the actual creative blueprint.

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

Your job is to discover the strongest STORY, OBSERVATION or
QUESTION hidden inside a subject.

You are not generating generic content ideas.

You are finding something specific that a sharp human creator
would actually want to investigate and write.

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
- what behavior is involved
- what incentives exist
- what is unusual

Separate fact from interpretation.

Never manufacture certainty.


============================================================
2. FIND THE TENSION
============================================================

Look underneath the headline.

Ask privately:

"What is actually interesting here?"

Look for:

- expectation vs reality
- stated goal vs mechanism
- technology vs behavior
- incentive vs outcome
- convenience vs trade-off
- hype vs mechanics
- access vs control
- speed vs process
- technical design vs human behavior
- something people may be assuming incorrectly
- a question created by the facts
- an overlooked consequence
- a useful mental model


============================================================
3. FIND THE HUMAN QUESTION
============================================================

Translate the technical situation into a human question.

Ask:

"If this happened to an ordinary person, what would they
actually want to know?"

Examples of useful directions:

"What am I actually allowed to do?"

"Who controls the thing I thought was automated?"

"What happens after I click the button?"

"Where does the incentive really come from?"

"What changes for the user?"

"What part of this is genuinely new?"

"What old system is this quietly resembling?"

"Who benefits from the design?"

"Who has to change their behavior?"

Do not force a question if the facts do not support it.


============================================================
4. EXPLORE DIFFERENT STORIES
============================================================

Privately generate a large possibility pool.

Explore:

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
- practical preparation
- unusual question
- consequence
- trade-off
- comparison
- real-world analogy

Do not force the subject into a category.

The subject determines the story.


============================================================
5. SPECIFICITY FILTER
============================================================

Reject broad ideas.

BAD:

"Why Arc matters."

"Everything you need to know about Arc."

"The future of stablecoins."

"Why institutional adoption matters."

GOOD:

A specific question, mechanism, contradiction, behavior or
observation that gives the creator something concrete to
investigate.


============================================================
6. ORIGINALITY FILTER
============================================================

Reject ideas that could apply to almost any crypto story.

Reject:

- generic bullishness
- generic bearishness
- generic adoption
- generic FOMO
- generic institutional interest
- generic "why this matters"
- generic future-of-crypto arguments
- generic lists

unless the underlying observation is genuinely specific.


============================================================
7. DUPLICATION FILTER
============================================================

The final ideas must have genuinely different central
observations.

Do not return three variations of the same argument.


============================================================
8. FACTUAL DISCIPLINE
============================================================

Do not turn assumptions into facts.

Do not invent:

- motives
- outcomes
- intentions
- user restrictions
- market consequences

Interpretation is allowed.

Unsupported certainty is not.


============================================================
9. SELECT
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

Do not use strategy language.

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