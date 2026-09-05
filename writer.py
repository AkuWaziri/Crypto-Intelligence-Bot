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

    results = research.get(
        "results",
        [],
    )

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
# MEME / COMIC IDEA ENGINE
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
for a distinctive crypto creator.

Your job is to find genuinely interesting, funny,
strange, ironic or revealing observations inside the
specific situation below.

Do NOT simply illustrate the crypto fact.

Think deeply internally.

The desired creative path is:

FACT → HUMAN BEHAVIOR → OBSERVATION → JOKE

not:

FACT → IMAGE OF FACT


USER SITUATION:

{situation}


RESEARCH:

{research_text}


============================================================
PRIVATE CREATIVE PROCESS
============================================================

Do not output this process.

1. Understand the confirmed facts.

2. Find the human behavior created by the situation.

3. Find the tiny strange, funny, ironic or unexpected
detail inside that behavior.

4. Reject the obvious joke.

5. Look one level deeper.

6. Generate many different possibilities internally.

Explore:

- observational
- deadpan
- absurd
- ironic
- conversational
- visual
- character-free
- character-based
- ordinary-life situations
- ordinary objects
- unexpected consequences
- contradictions
- awkward human behavior

Do not force any particular category.

7. KILL GENERIC CRYPTO JOKES.

Reject:

- FOMO
- greed
- moon
- rocket
- rug
- trader crying
- generic "free money"
- generic panic
- generic crypto confusion
- generic institution jokes
- generic bureaucracy
- generic locked door
- security guard
- boardroom
- treasure chest
- calendar
- supermarket
- Ferrari
- filing cabinet

unless the specific situation creates a genuinely new
observation.

8. KILL LITERAL ANALOGIES.

Do not turn every crypto mechanism into an ordinary object
just because they superficially resemble each other.

The resemblance itself is not the joke.

9. FACT VS JOKE.

THE JOKE CAN BE ABSURD.

THE FACTUAL SETUP MUST BE TRUE.

Never turn:

"may" into "does"

"could" into "will"

"some" into "everyone"

"described as" into "is"

Never invent:

- motives
- consequences
- capabilities
- intentions
- quotes
- restrictions
- outcomes

If the joke requires an unsupported factual claim,
discard the joke.

10. MAKE THE THREE IDEAS DIFFERENT.

The three final ideas must have THREE DIFFERENT
underlying observations.

Changing the:

- character
- setting
- object
- visual style
- wording

does NOT make an idea new.

If two ideas make the same point, keep only the stronger one.

11. SIMPLIFY.

The comic should use the minimum necessary elements.

Prefer:

- one panel over four
- two lines over a paragraph
- one object over a full environment
- one reaction over five characters
- one exchange over a long conversation

12. MAKE THE PUNCHLINE PUNCHY.

The punchline must NOT explain the joke.

It must NOT summarize the research.

It must NOT sound like a headline.

It should feel like the final click.

Ask:

"Can I remove half the words?"

If yes, shorten it.

Prefer:

- short
- sharp
- deadpan
- ironic
- conversational
- memorable

Do not force wordplay.

13. ATTACK EVERY IDEA.

Ask internally:

Is this actually funny?

Is this actually an observation?

Am I just repeating the fact?

Did I invent anything?

Could another crypto account make this exact joke?

Does this depend on THIS situation?

Can I remove half of it?

Would the idea work without crypto jargon?

If not, discard it.

14. RANK THE FINALISTS.

Rank internally by:

1. observation
2. originality
3. humor
4. immediate understanding
5. simplicity
6. specificity
7. visual memorability
8. factual discipline
9. distinctiveness

Return exactly THREE.


============================================================
FINAL OUTPUT
============================================================

Output ONLY this:

IDEA 1:
FORMAT:
OBSERVATION:
EXECUTION:
PUNCHLINE:

IDEA 2:
FORMAT:
OBSERVATION:
EXECUTION:
PUNCHLINE:

IDEA 3:
FORMAT:
OBSERVATION:
EXECUTION:
PUNCHLINE:

FINAL RULES:

- Exactly 3 ideas.
- No introduction.
- No conclusion.
- No SOURCES.
- No citations.
- No alternative execution.
- No second version.
- No explanations.
- No research summary.
- No established-facts section.
- No "what to explore".
- No strategy language.
- No audience language.
- No filler.

OBSERVATION:
Concise.

EXECUTION:
Practical and concise.

PUNCHLINE:
Short, sharp and memorable.

Do not write the finished social post.

Think deeply internally.

Output simply.
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

Find the strongest stories hiding inside the subject below.

Do NOT write a research report.

Do NOT give a long introduction.

Do NOT explain your thinking.

Think deeply internally and output only the strongest ideas.


SUBJECT:

{subject}


RESEARCH:

{research_text}


============================================================
PRIVATE CREATIVE PROCESS
============================================================

Do not output this process.

1. ESTABLISH THE FACTS.

Identify what is actually confirmed.

Understand:

- what happened
- what changed
- what mechanism matters
- what behavior matters
- who is affected

Do not invent certainty.


2. FIND WHAT IS ACTUALLY INTERESTING.

Look underneath the headline.

Find:

- a specific tension
- an incentive
- a mechanism
- an unexpected consequence
- an overlooked detail
- a contradiction
- a change in behavior
- an unintuitive result
- a trade-off
- a hidden dependency


3. FIND THE QUESTION.

Ask internally:

"What would a smart reader actually want to know?"

The question must come from the specific story.

Do not manufacture a generic industry question.


4. MOVE PAST THE HEADLINE.

The headline is not the story.

"Arc launches."

"Stablecoin adoption rises."

"Institution enters crypto."

These are events.

Find what is underneath the event.


5. GENERATE MANY DIFFERENT STORIES INTERNALLY.

Explore:

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


6. REJECT GENERIC IDEAS.

Reject:

- "Why this matters"
- "The future of..."
- "Why institutions are adopting..."
- "Crypto is changing finance..."
- "The future of AI agents..."
- "What this means for the industry..."

unless there is a genuinely specific observation
underneath.


7. DO NOT RESTATE THE NEWS.

The idea must add a question, explanation,
observation or useful perspective.

A headline rewritten as a topic is not an idea.


8. FACT VS INTERPRETATION.

Only make claims supported by the research.

Do not turn:

"may" into "does"

"could" into "will"

"some" into "everyone"

"described as" into "is"

Do not invent:

- motives
- intentions
- consequences
- capabilities
- certainty


9. MAKE THE THREE IDEAS DIFFERENT.

Each idea must have a different central observation.

Do not return three versions of the same thesis.

Changing the wording does not make an idea different.


10. MAKE THE HOOK PUNCHY.

The hook should immediately tell the reader why
this particular story is interesting.

Avoid long setup.

Avoid:

"The most interesting aspect of..."

"What you need to know about..."

"Here is why this matters..."

"Let's talk about..."

Start with the actual observation.


11. MAKE THE ANGLE DIRECT.

The angle should explain exactly what the creator
would investigate or explain.

One concise sentence.

No mini essay.


12. ATTACK EVERY IDEA.

Ask internally:

Is this specific?

Is it factual?

Is there a real observation?

Is there something to learn?

Is there tension?

Would the reader already know this?

Could this become a strong opening?

Could this become a strong post?

If not, discard it.


13. SIMPLIFY.

If the idea needs a paragraph to explain,
it is probably not strong enough.

Think deeply.

Output simply.


14. FINAL SELECTION.

Rank internally by:

1. strength
2. specificity
3. originality
4. usefulness
5. curiosity
6. factual discipline
7. distinctiveness

Return exactly THREE strong ideas.


============================================================
FINAL OUTPUT
============================================================

Output ONLY:

IDEA 1:
HOOK:
ANGLE:

IDEA 2:
HOOK:
ANGLE:

IDEA 3:
HOOK:
ANGLE:

FINAL RULES:

- Exactly 3 ideas.
- No introduction.
- No conclusion.
- No established facts.
- No strange-part section.
- No question section.
- No WHAT TO EXPLORE.
- No KEY FACTS.
- No SOURCES.
- No citations.
- No research summary.
- No explanations.
- No strategy language.
- No audience language.
- No filler.

HOOK:
One or two punchy sentences maximum.

ANGLE:
One concise sentence.

Do not write the finished post.

Think deeply internally.

Output simply.
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