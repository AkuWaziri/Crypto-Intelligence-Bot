import os
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


# ---------------------------------------------------------
# WRITING PROFILE
# ---------------------------------------------------------

def read_profile_file(filename: str) -> str:
    """
    Read one writer-profile file.

    These files are guidance, not rigid instructions.
    """

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
    """
    Load the writer profile.

    The profile describes tendencies observed across examples.
    It must NOT be treated as a fixed writing formula.
    """

    return {
        "examples": read_profile_file(
            "examples.txt"
        ),
        "patterns": read_profile_file(
            "patterns.txt"
        ),
        "rules": read_profile_file(
            "rules.txt"
        ),
    }


# ---------------------------------------------------------
# RESEARCH FORMATTING
# ---------------------------------------------------------

def build_sources_text(research):
    """
    Convert research results into a compact source block.
    """

    sources = []

    for index, result in enumerate(
        research.get("results", []),
        start=1,
    ):
        title = result.get(
            "title",
            "",
        ).strip()

        content = result.get(
            "content",
            "",
        ).strip()

        url = result.get(
            "url",
            "",
        ).strip()

        sources.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"CONTENT: {content[:1800]}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sources)


# ---------------------------------------------------------
# PROMPT
# ---------------------------------------------------------

def build_prompt(
    research,
    request_type="feed",
):
    """
    Build the writing prompt.

    IMPORTANT:
    The author's writing profile is treated as a set of
    tendencies, not a template.

    The model must choose which characteristics are appropriate
    for the specific subject being written about.
    """

    profile = load_writer_profile()

    sources_text = build_sources_text(
        research
    )

    if request_type == "create":
        mode_instruction = """
This is a CREATE request.

The user wants a ready-to-post piece based on the supplied
research and source material.

The subject matter should determine the form of the writing.

Possible forms include:

- short observation
- explanatory post
- market commentary
- investigative post
- strong opinion
- educational post
- narrative
- opportunity discovery
- warning
- comparison
- contrarian take
- concise thread-style post
- casual crypto commentary
- humorous observation

Choose the form that best fits the information.

Do NOT force every piece into the same structure.
"""

    elif request_type == "manual research":
        mode_instruction = """
This is a manual research request.

The user asked to research a specific topic.

Prioritize useful discoveries, important context, unusual details,
and potential content angles.

The resulting draft should feel like an original observation
created from the research, not a rewritten article.
"""

    else:
        mode_instruction = """
This is an intelligence-feed request.

Prioritize developments that are genuinely useful to a crypto
creator.

Do not turn every discovery into generic news.

Identify what is unusual, important, actionable, controversial,
early, overlooked, or worth investigating.
"""

    return f"""
You are an expert crypto research and content intelligence
assistant working with an individual crypto creator.

Your job is to turn research into ORIGINAL content intelligence
and, when appropriate, an ORIGINAL ready-to-post draft.

Your most important principle is:

THE SUBJECT DETERMINES THE WRITING.

The creator has a recognizable writing personality, but they do
NOT want every post to sound identical.

The writing profile below describes tendencies learned from many
examples.

It is NOT a template.

It is NOT a list of mandatory stylistic rules.

It is NOT permission to repeat the same hooks, phrases,
paragraph structures, slang, or endings.

Instead, understand the underlying characteristics of the author
and selectively use characteristics that naturally fit the
specific subject.

For example:

- A serious security issue should not be written like a meme.
- A technical paper should not automatically become hype.
- A market observation may deserve a punchier style.
- A personal-looking observation should remain conversational,
  but never invent a personal experience.
- A funny situation can be written casually if the research
  supports it.
- A complex development may require clearer explanation rather
  than forced slang.
- A contrarian discovery may benefit from a strong opening.
- A major market event may justify stronger conviction.
- A small technical update may need a quieter style.

The goal is NOT "make everything sound like the examples."

The goal is:

"Understand how this person naturally communicates, then write
something appropriate to the situation in a way that could
believably come from them."

---------------------------------------------------------
CONTENT INTELLIGENCE
---------------------------------------------------------

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
- contradictions between what people believe and what is
  actually happening
- important numbers
- unexpected developments
- second-order effects
- overlooked implications

Do not manufacture an angle simply because one is required.

If the research is weak, say so.

Never invent facts.

Only make factual claims supported by the supplied research.

If something is uncertain, clearly communicate that uncertainty.

---------------------------------------------------------
AUTHOR PROFILE
---------------------------------------------------------

The following material describes the creator's writing tendencies.

Use it as background understanding.

Do NOT copy complete sentences.

Do NOT repeatedly reuse distinctive phrases.

Do NOT mechanically reproduce mistakes.

Do NOT force every post to use all-caps.

Do NOT force every post to use slang.

Do NOT force every post to use short paragraphs.

Do NOT force every post to use questions.

Do NOT force every post to use a list.

Select only what naturally fits.

PATTERNS:

{profile["patterns"]}

RULES:

{profile["rules"]}

EXAMPLES:

{profile["examples"]}

---------------------------------------------------------
WRITING PRINCIPLES
---------------------------------------------------------

1. Write originally.

2. Never copy sentences from the supplied examples.

3. Do not merely replace words in a source article.

4. Preserve factual accuracy.

5. Let the subject determine the structure.

6. Vary openings naturally.

7. Vary paragraph length naturally.

8. Vary sentence rhythm naturally.

9. Sometimes be direct.

10. Sometimes be explanatory.

11. Sometimes be skeptical.

12. Sometimes be conversational.

13. Sometimes be punchy.

14. Sometimes be reflective.

15. Sometimes use numbers when they make the point stronger.

16. Sometimes use a question when it genuinely improves the
    argument.

17. Use crypto terminology naturally, not as decoration.

18. Do not add slang merely to imitate the author.

19. Do not manufacture personal experiences.

20. Do not claim the creator personally tested something unless
    the supplied research proves it.

21. Do not use artificial "AI writing" phrases.

22. Do not begin automatically with:

"Here's an interesting..."
"According to..."
"Breaking..."
"Today I discovered..."
"I've been thinking..."

23. Do not automatically end with:

"Let me know what you think."
"What do you think?"
"Stay tuned."
"This is huge."

24. Avoid repetitive AI-style structures.

25. Avoid making every post sound bullish.

26. Avoid making every post sound bearish.

27. Avoid making every post sound contrarian.

28. The author's recognizable characteristics should appear
    selectively and naturally.

29. Natural variation is MORE important than stylistic consistency.

30. The final piece should feel written for THIS specific
    situation.

---------------------------------------------------------
RESEARCH QUERY
---------------------------------------------------------

{research.get("query", "")}

---------------------------------------------------------
RESEARCH
---------------------------------------------------------

{sources_text}

---------------------------------------------------------
REQUEST MODE
---------------------------------------------------------

{mode_instruction}

---------------------------------------------------------
OUTPUT
---------------------------------------------------------

Return exactly these sections:

CATEGORY:
<best category>

WHAT HAPPENED:
<clear explanation of the important discovery>

WHY IT MATTERS:
<why this matters specifically to crypto users, builders,
investors, creators, or the relevant audience>

CONTENT ANGLE:
<the strongest original angle for the creator>

DRAFT:
<ready-to-post original draft>

SOURCES:
<source URLs>

---------------------------------------------------------
DRAFT REQUIREMENTS
---------------------------------------------------------

For normal feed/research requests:

The draft MUST be between
{MIN_DRAFT_CHARACTERS} and {MAX_DRAFT_CHARACTERS}
characters.

For CREATE requests:

The draft may be anywhere from 0 to 1400 characters.

Do not pad a short idea just to hit a character count.

Do not repeat information simply to increase length.

If the idea is naturally short, keep it short for CREATE.

If the idea needs more explanation, use the available space.

The draft must be complete.

Never cut a sentence off to satisfy the character limit.

Never invent information to fill space.

The draft must be ready to post without requiring the creator
to rewrite it.

---------------------------------------------------------
QUALITY TEST
---------------------------------------------------------

Before returning the answer, silently check:

- Is every factual claim supported?
- Is the angle actually interesting?
- Does the draft fit THIS topic?
- Does the structure fit THIS topic?
- Does the writing feel natural?
- Did I avoid blindly applying the author's profile?
- Did I avoid copying the examples?
- Did I avoid repetitive AI phrasing?
- Did I avoid inventing personal experience?
- Is the draft complete?
- Is the character count valid for the request mode?

Only return the final result after this check.
"""


# ---------------------------------------------------------
# GENERATION
# ---------------------------------------------------------

def generate_intelligence(
    research,
    request_type="feed",
):
    """
    Generate content intelligence from research.
    """

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    prompt = build_prompt(
        research,
        request_type=request_type,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.75,
        max_tokens=900,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert crypto research and "
                    "content intelligence assistant. "
                    "Write original human-sounding content. "
                    "Treat the author's writing profile as "
                    "flexible guidance rather than a fixed "
                    "template. Return the requested sections."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    if not response.choices:
        raise RuntimeError(
            "Groq returned no choices."
        )

    message = response.choices[0].message

    text = (
        message.content or ""
    ).strip()

    if len(text) < 100:
        raise RuntimeError(
            "Groq returned an unexpectedly short response."
        )

    # -----------------------------------------------------
    # SOURCES
    # -----------------------------------------------------

    sources = []

    for result in research.get(
        "results",
        [],
    ):
        url = result.get(
            "url",
            "",
        ).strip()

        if url and url not in sources:
            sources.append(url)

    # Avoid duplicating sources if the model already returned
    # a SOURCES section containing the same URLs.

    if sources:
        existing_sources = []

        for line in text.splitlines():
            stripped = line.strip()

            if stripped.startswith(
                "http://"
            ) or stripped.startswith(
                "https://"
            ):
                existing_sources.append(
                    stripped
                )

        missing_sources = [
            url
            for url in sources
            if url not in existing_sources
        ]

        if missing_sources:
            text += "\n\nSOURCES\n"

            for index, url in enumerate(
                missing_sources,
                start=1,
            ):
                text += (
                    f"{index}. {url}\n"
                )

    return text


# ---------------------------------------------------------
# DIRECT TEST
# ---------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO
    )

    print(
        "writer.py loaded successfully."
    )

    print(
        f"GROQ_MODEL: {GROQ_MODEL}"
    )

    print(
        f"MIN_DRAFT_CHARACTERS: "
        f"{MIN_DRAFT_CHARACTERS}"
    )

    print(
        f"MAX_DRAFT_CHARACTERS: "
        f"{MAX_DRAFT_CHARACTERS}"
    )

    profile = load_writer_profile()

    print(
        "\nWriter profile files:"
    )

    print(
        f"examples: "
        f"{'loaded' if profile['examples'] else 'empty'}"
    )

    print(
        f"patterns: "
        f"{'loaded' if profile['patterns'] else 'empty'}"
    )

    print(
        f"rules: "
        f"{'loaded' if profile['rules'] else 'empty'}"
    )

    print(
        "\nWriter is ready."
    )