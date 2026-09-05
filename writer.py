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
# CREATOR IDENTITY
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
# HUMAN WRITING STRUCTURES
# ============================================================

HUMAN_WRITING_STRUCTURES = [
    {
        "name": "Observation → Reveal → Implication",
        "use_when": "A small visible detail reveals a bigger story.",
    },
    {
        "name": "Strange Detail → Explanation → Bigger Picture",
        "use_when": "The story contains an unusual or overlooked detail.",
    },
    {
        "name": "Claim → Evidence → Consequence",
        "use_when": "The research contains a strong factual claim and measurable evidence.",
    },
    {
        "name": "Question → Discovery → Realization",
        "use_when": "The topic becomes interesting through investigation.",
    },
    {
        "name": "Contradiction → Why → Payoff",
        "use_when": "Two facts appear to conflict or create an unexpected result.",
    },
    {
        "name": "Before → Change → After",
        "use_when": "Something materially changed over time.",
    },
    {
        "name": "Small Event → Hidden Mechanism → Large Consequence",
        "use_when": "A seemingly small event exposes an important mechanism.",
    },
    {
        "name": "Number → Context → Meaning",
        "use_when": "A striking number needs context before its importance becomes clear.",
    },
    {
        "name": "Common Assumption → Correction → Better Model",
        "use_when": "The obvious interpretation is incomplete or wrong.",
    },
    {
        "name": "Story → Detail → Lesson",
        "use_when": "A concrete event can teach a broader concept.",
    },
    {
        "name": "What Happened → What People Think → What Is Actually Happening",
        "use_when": "The public interpretation differs from the underlying mechanism.",
    },
    {
        "name": "Mechanism First",
        "use_when": "Understanding the mechanism is more useful than starting with the headline.",
    },
    {
        "name": "Consequence First",
        "use_when": "The outcome is more interesting than the event that caused it.",
    },
    {
        "name": "Incentive → Behavior → Result",
        "use_when": "People or protocols behave in response to an economic incentive.",
    },
    {
        "name": "Timeline → Inflection Point → Current State",
        "use_when": "The story makes sense through a sequence of events.",
    },
    {
        "name": "Case Study",
        "use_when": "One concrete example explains a larger system.",
    },
    {
        "name": "Myth → Evidence → Reality",
        "use_when": "A common belief can be tested against the evidence.",
    },
    {
        "name": "Problem → Mechanism → Solution",
        "use_when": "The content is educational, practical or guide-oriented.",
    },
    {
        "name": "Discovery Log",
        "use_when": "The story works naturally as a sequence of findings.",
    },
    {
        "name": "One Thing → Why It Matters",
        "use_when": "One overlooked fact carries most of the story.",
    },
]


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

    # Fix common encoding corruption.
    replacements = {
        "â€”": "—",
        "â€“": "–",
        "â€˜": "‘",
        "â€™": "’",
        "â€œ": "“",
        "â€ ": "”",
        "Â": "",
    }

    for bad, good in replacements.items():
        text = text.replace(
            bad,
            good,
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

    return last_character not in ".!?\"')]}"


# ============================================================
# RESEARCH COMPRESSION
# ============================================================

def _clean_research_content(content, max_chars):
    content = str(
        content or ""
    ).strip()

    content = re.sub(
        r"\s+",
        " ",
        content,
    )

    if len(content) > max_chars:
        content = content[:max_chars].rstrip()

    return content


def _research_result_score(result):
    try:
        return float(
            result.get(
                "score",
                0,
            )
            or 0
        )
    except Exception:
        return 0


def build_research_text(
    research,
    max_results=12,
    max_content_chars=850,
):
    """
    Build a compact evidence packet for Groq.

    Research can contain up to 30 candidates, but the model
    should not receive all of them at full length.

    This prevents large research sweeps from turning into
    oversized Groq requests while preserving the strongest
    evidence and multiple research angles.
    """

    if not research:
        return ""

    sections = []

    answer = (
        research.get(
            "answer",
            "",
        )
        or ""
    ).strip()

    if answer:
        sections.append(
            "RESEARCH SUMMARY:\n"
            + _clean_research_content(
                answer,
                1200,
            )
        )

    results = list(
        research.get(
            "results",
            [],
        )
        or []
    )

    # The research engine already ranks results.
    # Keep that ranking but preserve angle diversity.
    ranked = sorted(
        results,
        key=_research_result_score,
        reverse=True,
    )

    selected = []
    angle_counts = {}

    # First pass: evidence diversity.
    for result in ranked:
        angle = str(
            result.get(
                "research_angle",
                "general",
            )
            or "general"
        )

        count = angle_counts.get(
            angle,
            0,
        )

        if count >= 3:
            continue

        selected.append(result)

        angle_counts[angle] = count + 1

        if len(selected) >= max_results:
            break

    # Second pass: strongest remaining evidence.
    selected_urls = {
        str(
            item.get(
                "url",
                "",
            )
        ).strip()
        for item in selected
    }

    if len(selected) < max_results:
        for result in ranked:
            if len(selected) >= max_results:
                break

            url = str(
                result.get(
                    "url",
                    "",
                )
                or ""
            ).strip()

            if url and url in selected_urls:
                continue

            selected.append(result)

            if url:
                selected_urls.add(url)

    for index, result in enumerate(
        selected,
        start=1,
    ):
        title = (
            result.get(
                "title",
                "",
            )
            or "Untitled"
        ).strip()

        content = _clean_research_content(
            result.get(
                "content",
                "",
            ),
            max_content_chars,
        )

        url = (
            result.get(
                "url",
                "",
            )
            or ""
        ).strip()

        angle = (
            result.get(
                "research_angle",
                "general",
            )
            or "general"
        )

        if not content:
            continue

        sections.append(
            f"SOURCE {index}:\n"
            f"ANGLE: {angle}\n"
            f"TITLE: {title}\n"
            f"EVIDENCE: {content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(
        sections
    )


def get_draft_max(mode="normal"):
    if mode == "feed":
        return MAX_FEED_DRAFT_CHARACTERS

    return MAX_DRAFT_CHARACTERS


# ============================================================
# STRUCTURE SELECTION
# ============================================================

def format_structure_library():
    lines = []

    for index, structure in enumerate(
        HUMAN_WRITING_STRUCTURES,
        start=1,
    ):
        lines.append(
            f"{index}. "
            f"{structure['name']} — "
            f"{structure['use_when']}"
        )

    return "\n".join(lines)


# ============================================================
# STANDARD CONTENT GENERATION
# ============================================================

def build_prompt(request_text, research):
    writer_profile = load_writer_profile()

    research_text = build_research_text(
        research,
        max_results=12,
        max_content_chars=850,
    )

    structures = format_structure_library()

    return f"""
You are the writing engine for a distinctive crypto creator.

The creator explains crypto, blockchain, AI agents,
onchain activity, protocols, infrastructure, money and
internet culture in simple, human and memorable language.

The creator is NOT trying to sound like:

- a corporate publication
- an SEO writer
- a research report
- a marketing strategist
- an AI assistant

The creator's own writing DNA is the highest authority.

============================================================
CREATOR DNA
============================================================

{writer_profile}

============================================================
USER REQUEST
============================================================

{request_text}

============================================================
RESEARCH
============================================================

{research_text}

============================================================
HUMAN WRITING STRUCTURES
============================================================

{structures}

============================================================
PRIVATE EDITORIAL PROCESS
============================================================

Do NOT output this process.

Think deeply before writing.

1. UNDERSTAND THE STORY.

Identify:

- the actual event
- the important mechanism
- the strongest evidence
- the unusual detail
- the human consequence
- the useful lesson
- what remains uncertain

Do not force all of these into the final writing.

2. SEPARATE FACT FROM INTERPRETATION.

FACT:
Directly supported by the research.

INTERPRETATION:
A reasonable conclusion from the facts.

UNCERTAINTY:
Something the research does not establish.

Never present interpretation as confirmed fact.

Never invent:

- numbers
- dates
- motives
- quotes
- capabilities
- intentions
- outcomes
- users
- partnerships
- technical properties

3. FIND THE REAL STORY.

Do not simply rewrite the headline.

Ask:

"What is actually interesting here?"

Look for:

- an unexpected mechanism
- an incentive
- a contradiction
- an overlooked detail
- a behavioral change
- a hidden dependency
- an unusual consequence
- a surprising number
- a practical implication
- something people commonly misunderstand

4. CHOOSE THE BEST STRUCTURE.

Select ONE structure from the library.

Do not announce the structure.

The structure controls:

- order
- reveal
- pacing
- information flow

The creator DNA controls:

- voice
- rhythm
- sentence length
- humor
- personality
- word choice
- level of simplicity

5. BUILD A STRONG OPENING.

Do not begin with:

"Today we're going to talk about..."

"In the world of crypto..."

"Here's everything you need to know..."

"Recently..."

"Let's dive into..."

Start where the interesting thing starts.

6. COMPRESS.

Remove anything that does not improve:

- understanding
- evidence
- curiosity
- rhythm
- humor
- usefulness
- memorability

Rich thinking should produce compressed writing.

7. MAKE IT HUMAN.

Write like a sharp person explaining something to another
sharp person.

Use plain language.

Use technical terms only when they add precision.

Explain unavoidable jargon naturally.

8. DO NOT OVERWRITE.

A strong sentence beats three average sentences.

A strong observation beats five facts.

One clear idea beats a list.

9. IF HUMOR FITS, USE IT.

Do not force humor.

Do not add generic crypto jokes.

Do not use meme language just because the topic is crypto.

10. FINAL EDIT.

Before returning the writing, ask internally:

Is the first line strong?

Is the central idea clear?

Is every factual claim supported?

Did I accidentally invent anything?

Did I explain too much?

Can I remove 20%?

Does this sound like a person?

Does this sound like THIS creator?

If the answer is no, rewrite.

============================================================
FINAL TASK
============================================================

Create the requested content.

Return ONLY the finished content.

Do not describe your process.
Do not describe the research.
Do not mention the structure.
Do not mention the creator profile.
""".strip()


# ============================================================
# GROQ
# ============================================================

def call_writer(
    prompt,
    temperature=0.8,
    max_tokens=450,
):
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    client = Groq(
        api_key=GROQ_API_KEY
    )

    # Protect the application from accidental oversized
    # output requests. The config currently uses a 500-token
    # ceiling, so staying slightly below that is deliberate.
    safe_max_tokens = max(
        100,
        min(
            int(max_tokens),
            450,
        ),
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=safe_max_tokens,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a sharp crypto creator, "
                    "editor and writer. "
                    "Think deeply internally. "
                    "Write clearly, specifically and "
                    "naturally. "
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

    research_text = build_research_text(
        research,
        max_results=12,
        max_content_chars=850,
    )

    prompt = f"""
You are the intelligence editor behind a distinctive
crypto creator.

Your job is NOT to summarize every source.

Your job is to determine what is actually worth knowing.

Think like a room full of:

- researchers
- crypto analysts
- journalists
- technical investigators
- onchain analysts
- sharp creators
- skeptical editors

Generate broadly internally.

Then act like a ruthless editor.

Discard:

- obvious information
- repeated facts
- weak claims
- unsupported conclusions
- generic crypto commentary
- filler
- unnecessary context

Surface only the strongest intelligence.

============================================================
CREATOR DNA
============================================================

{writer_profile}

============================================================
CONTEXT
============================================================

{context}

============================================================
RESEARCH
============================================================

{research_text}

============================================================
PRIVATE INTELLIGENCE PROCESS
============================================================

Do NOT output this process.

1. Establish what is definitely true.

2. Identify the strongest evidence.

3. Compare sources.

4. Look for contradictions.

5. Look for what changed.

6. Look for the mechanism underneath the event.

7. Look for incentives and resulting behavior.

8. Look for numbers that materially change the story.

9. Identify what people may misunderstand.

10. Identify what remains unclear.

11. Search mentally for the deeper story.

12. Generate multiple possible interpretations.

13. Kill the obvious ones.

14. Keep only the observations that would make a
smart creator stop and say:

"Wait. That's interesting."

============================================================
OUTPUT
============================================================

Return a compact but information-dense intelligence report.

Use ONLY the sections that are genuinely supported by
the research.

Do NOT force every section to appear.

Possible sections:

SIGNAL:
The single most important thing.

WHAT ACTUALLY HAPPENED:
The factual event or change.

WHY IT IS INTERESTING:
The specific reason this is more interesting than
the headline suggests.

THE DETAIL PEOPLE MAY MISS:
One overlooked fact or relationship.

THE MECHANISM:
How the system actually works.

WHAT CHANGED:
Before versus after, when relevant.

THE NUMBERS:
Only important numbers with context.

INCENTIVE:
What economic or behavioral incentive is operating,
when relevant.

WHAT PEOPLE MAY BE GETTING WRONG:
Only when there is evidence for a misconception.

WHAT IS UNCLEAR:
Important uncertainty or missing evidence.

CONTENT OPPORTUNITIES:
2–4 specific things worth turning into content.

RABBIT HOLES:
2–4 deeper questions worth investigating.

============================================================
RULES
============================================================

- Facts must be supported by the research.
- Clearly label interpretation as interpretation.
- Never invent numbers.
- Never invent quotes.
- Never invent motives.
- Never invent certainty.
- Do not write a finished social post.
- Do not write generic commentary.
- Do not repeat the same fact in multiple sections.
- Prefer specificity over volume.
- Prefer useful intelligence over summary.
- Keep the final report compressed.
- No introduction.
- No conclusion.
""".strip()

    return call_writer(
        prompt,
        temperature=0.65,
        max_tokens=450,
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
        max_tokens=450,
    )


# ============================================================
# CREATIVE IDEA RESEARCH
# ============================================================

def build_idea_research_text(research):
    """
    Compact factual packet for creative ideation.

    The research engine may return up to 30 candidates.
    Creative generation only needs the strongest evidence.

    Keeping the packet small protects Groq from oversized
    requests while retaining enough context for discovery.
    """

    if not research:
        return ""

    sections = []

    answer = (
        research.get(
            "answer",
            "",
        )
        or ""
    ).strip()

    if answer:
        sections.append(
            "SUMMARY:\n"
            + answer[:1000]
        )

    results = list(
        research.get(
            "results",
            [],
        )
        or []
    )

    # Results are normally already ranked by research.py.
    # Keep the strongest 12 while preserving evidence types.
    ranked = sorted(
        results,
        key=_research_result_score,
        reverse=True,
    )

    selected = []
    angle_counts = {}

    for result in ranked:
        angle = str(
            result.get(
                "research_angle",
                "general",
            )
            or "general"
        )

        count = angle_counts.get(
            angle,
            0,
        )

        if count >= 3:
            continue

        selected.append(result)

        angle_counts[angle] = count + 1

        if len(selected) >= 12:
            break

    for index, result in enumerate(
        selected,
        start=1,
    ):
        title = (
            result.get(
                "title",
                "",
            )
            or "Untitled"
        ).strip()

        content = _clean_research_content(
            result.get(
                "content",
                "",
            ),
            750,
        )

        url = (
            result.get(
                "url",
                "",
            )
            or ""
        ).strip()

        angle = (
            result.get(
                "research_angle",
                "general",
            )
            or "general"
        )

        if not content:
            continue

        sections.append(
            f"SOURCE {index}\n"
            f"ANGLE: {angle}\n"
            f"TITLE: {title}\n"
            f"FACTS/CONTEXT: {content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(
        sections
    )


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
You are the senior comic writer and creative director
for a distinctive crypto creator.

Your job is to find the genuinely interesting human
observation hiding inside this specific situation.

You are NOT illustrating the crypto fact.

You are discovering what is funny, strange, ironic,
absurd, revealing or unexpectedly human about it.

============================================================
SITUATION
============================================================

{situation}

============================================================
RESEARCH
============================================================

{research_text}

============================================================
CORE CREATIVE PRINCIPLE
============================================================

FACT
↓
HUMAN BEHAVIOR
↓
OBSERVATION
↓
JOKE

NOT:

FACT
↓
LITERAL VISUAL OF FACT

The crypto fact creates the situation.

The human behavior creates the comedy.

============================================================
PRIVATE CREATIVE ROOM
============================================================

Do NOT output this process.

Generate a large internal pool of possibilities.

Explore aggressively:

- observational comedy
- deadpan
- absurdity
- irony
- awkward human behavior
- conversational humor
- visual situations
- character-free situations
- character-based situations
- ordinary objects
- ordinary social situations
- unexpected consequences
- contradictions
- incentives
- misunderstandings
- status behavior
- bureaucracy
- overconfidence
- understatement
- reversal
- anti-climax

Do not force any category.

============================================================
THE ORIGINALITY TEST
============================================================

Reject anything that feels like the first joke a crypto
account would make.

Automatically reject:

- FOMO
- greed
- moon
- rocket
- rug
- trader crying
- generic panic
- generic "free money"
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

These are not forbidden forever.

They are forbidden when they are merely obvious.

If one appears, it must contain a genuinely new
observation specific to this situation.

============================================================
NO LITERAL ANALOGIES
============================================================

Do not turn a crypto mechanism into an ordinary object
just because they look similar.

A vesting schedule is not automatically a calendar.

A wallet is not automatically a wallet.

A protocol is not automatically an office.

A token is not automatically money falling from the sky.

The resemblance is not the joke.

The behavior is.

============================================================
FACTUAL DISCIPLINE
============================================================

The joke may be absurd.

The factual setup may not be.

Never transform:

"may" → "does"

"could" → "will"

"some" → "everyone"

"described as" → "is"

Never invent:

- motives
- intentions
- capabilities
- restrictions
- quotes
- outcomes
- technical properties
- user behavior

If the joke requires an unsupported factual claim,
discard it.

============================================================
DISTINCTNESS
============================================================

The three final ideas must have THREE different
underlying observations.

Changing the:

- character
- location
- object
- visual style
- wording

does not make an idea different.

If two ideas make the same point, kill the weaker one.

============================================================
SIMPLICITY
============================================================

Prefer the smallest possible execution.

One panel can beat four.

Two lines can beat ten.

One reaction can beat five characters.

One exchange can beat a conversation.

One visual detail can beat an elaborate scene.

Do not add elements merely to make the idea look
"creative."

============================================================
PUNCHLINE
============================================================

The punchline must not explain the joke.

It must not summarize the research.

It must not sound like a headline.

It should feel like the final click.

Ask:

"Can I remove half the words?"

If yes, remove them.

Prefer:

- short
- sharp
- deadpan
- ironic
- conversational
- memorable

Do not force wordplay.

============================================================
FINAL ATTACK
============================================================

For every candidate, ask internally:

Is this actually funny?

Is this actually an observation?

Am I merely repeating the fact?

Could another crypto account make this exact joke?

Does this depend on THIS situation?

Did I invent anything?

Can I remove half of it?

Would someone understand it immediately?

Would it still be interesting without crypto jargon?

If not, discard it.

============================================================
RANKING
============================================================

Rank survivors internally by:

1. observation
2. originality
3. humor
4. immediate understanding
5. simplicity
6. specificity
7. visual memorability
8. factual discipline
9. brand distinctiveness

Return exactly THREE.

============================================================
FINAL OUTPUT
============================================================

Output ONLY:

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

Rules:

- Exactly 3 ideas.
- No introduction.
- No conclusion.
- No SOURCES.
- No citations.
- No research summary.
- No established-facts section.
- No "what to explore."
- No strategy language.
- No audience language.
- No filler.
- No finished social post.
- No alternative versions.

OBSERVATION:
One concise sentence.

EXECUTION:
Describe the actual comic/text-comic execution concisely.

PUNCHLINE:
Short, sharp and memorable.

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

Your job is to discover the strongest things worth
saying about the subject below.

You are NOT writing a research report.

You are NOT summarizing the sources.

You are finding stories.

============================================================
SUBJECT
============================================================

{subject}

============================================================
RESEARCH
============================================================

{research_text}

============================================================
PRIVATE EDITORIAL ROOM
============================================================

Do NOT output this process.

Think deeply.

Generate many different possible stories internally.

Then become a ruthless editor.

============================================================
1. ESTABLISH THE FACTS
============================================================

Determine:

- what happened
- what changed
- how the mechanism works
- who is affected
- what behavior changed
- what evidence exists
- what remains uncertain

Do not invent certainty.

============================================================
2. FIND WHAT IS ACTUALLY INTERESTING
============================================================

Look underneath the headline.

Search for:

- specific tension
- incentive
- mechanism
- unexpected consequence
- overlooked detail
- contradiction
- behavioral change
- unintuitive result
- trade-off
- hidden dependency
- useful number
- practical implication
- misconception
- unusual business model

============================================================
3. FIND THE REAL QUESTION
============================================================

Ask:

"What would a smart reader genuinely want to understand?"

The question must come from THIS story.

Do not manufacture a generic industry question.

============================================================
4. MOVE PAST THE HEADLINE
============================================================

A headline is an event.

An event is not automatically a story.

For example:

"Protocol launches."

"Stablecoin adoption rises."

"Institution enters crypto."

"AI agent gets funding."

These are events.

Find what is underneath them.

============================================================
5. EXPLORE MANY STORY TYPES
============================================================

Generate possibilities internally across:

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
- data story
- infrastructure story
- failure mode
- hidden dependency

Do not force categories.

============================================================
6. KILL GENERIC IDEAS
============================================================

Reject:

"Why this matters"

"The future of..."

"Why institutions are adopting..."

"Crypto is changing finance..."

"The future of AI agents..."

"What this means for the industry..."

"Everything you need to know..."

unless there is a highly specific observation underneath.

============================================================
7. DO NOT RESTATE THE NEWS
============================================================

A headline rewritten as a topic is not an idea.

The idea must add:

- a question
- an explanation
- an observation
- a useful model
- a surprising consequence
- a specific comparison
- a practical lesson

============================================================
8. FACT VS INTERPRETATION
============================================================

Use only claims supported by the research.

Never turn:

"may" → "does"

"could" → "will"

"some" → "everyone"

"described as" → "is"

Never invent:

- motives
- intentions
- capabilities
- consequences
- certainty
- quotes
- numbers

============================================================
9. MAKE THE THREE IDEAS ACTUALLY DIFFERENT
============================================================

Each final idea must have a different central observation.

Do not return three versions of the same thesis.

Changing wording is not enough.

============================================================
10. MAKE THE HOOK PUNCHY
============================================================

Start with the actual observation.

Avoid:

"Today..."

"Here is why..."

"Let's talk about..."

"What you need to know..."

"The most interesting thing..."

Start where the story becomes interesting.

============================================================
11. MAKE THE ANGLE USEFUL
============================================================

The angle should tell the creator exactly what the post
would investigate, explain or reveal.

One concise sentence.

No mini essay.

============================================================
12. ATTACK EVERY IDEA
============================================================

Ask internally:

Is this specific?

Is there a real observation?

Is it factual?

Is there something to learn?

Is there tension?

Would the reader already know this?

Does it go beyond the headline?

Could this become a strong opening?

Could this become a strong post?

If not, discard it.

============================================================
13. SIMPLIFY
============================================================

If an idea needs a paragraph to explain why it is
interesting, it probably is not sharp enough.

Think deeply.

Output simply.

============================================================
14. FINAL RANKING
============================================================

Rank survivors internally by:

1. strength
2. specificity
3. originality
4. usefulness
5. curiosity
6. factual discipline
7. distinctiveness

Return exactly THREE.

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

Rules:

- Exactly 3 ideas.
- No introduction.
- No conclusion.
- No established facts.
- No strange-part section.
- No question section.
- No "what to explore."
- No key facts section.
- No SOURCES.
- No citations.
- No research summary.
- No explanations.
- No strategy language.
- No audience language.
- No filler.
- Do not write the finished post.

HOOK:
One or two punchy sentences maximum.

ANGLE:
One concise sentence.

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
        temperature=0.95,
        max_tokens=450,
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
        research,
        max_results=10,
        max_content_chars=700,
    )

    prompt = f"""
You are a senior crypto creator and editor.

Generate exactly 3 useful content ideas about:

{request_text}

CREATOR PROFILE:

{writer_profile}

RESEARCH:

{research_text}

Think broadly internally.

Find the strongest specific stories inside the research.

Reject:

- generic topics
- generic crypto commentary
- headline rewrites
- repeated angles
- unsupported claims
- SEO-style topics

Each idea must have a distinct premise.

Each idea should be something the creator could turn into:

- a post
- a comic
- a technical breakdown
- an explanation
- a guide
- an observation

Do not invent facts.

Return exactly:

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
        max_tokens=450,
    )