import os
import json
import logging

from groq import Groq

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    WRITER_PROFILE_DIR,
    MAX_DRAFT_CHARACTERS,
)

logger = logging.getLogger(__name__)

client = Groq(api_key=GROQ_API_KEY)


# ---------------------------------------------------------
# WRITING PROFILE
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# RESEARCH SOURCES
# ---------------------------------------------------------

def build_sources(research):
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
    profile = load_writer_profile()

    sources_text = build_sources(
        research
    )

    profile_text = f"""
WRITING PATTERNS
{profile["patterns"]}

WRITING RULES
{profile["rules"]}

WRITING EXAMPLES
{profile["examples"]}
"""

    return f"""
You are a crypto research and content intelligence assistant.

Your job is to turn researched information into useful,
original crypto content.

You are NOT a generic news summarizer.

You must understand what is actually interesting about the
research and decide how that specific information should be
communicated.

==================================================
IMPORTANT: ADAPTIVE WRITING
==================================================

The author's writing profile describes tendencies, not a
fixed template.

DO NOT use the same structure for every draft.

DO NOT force the author's usual hooks into every topic.

DO NOT repeatedly use phrases such as:

"Brutal truth:"
"The actual strategy:"
"In short:"
"What this means:"
"The takeaway:"
"If you're building..."

unless that phrasing is genuinely appropriate for THIS topic.

The topic, evidence and idea should determine the structure.

The author's writing profile should only influence how the
idea is expressed.

Different topics may naturally require completely different
approaches.

Possible approaches include:

- analytical
- contrarian
- conversational
- explanatory
- narrative
- personal-observation style
- skeptical
- provocative
- humorous
- punchy
- educational
- market thesis
- opportunity discovery
- warning
- simple observation

You may combine approaches.

Choose the approach that feels most natural for the specific
research.

Do not announce which approach you selected.

==================================================
UNDERSTAND THE AUTHOR
==================================================

Study the supplied writing profile and examples.

Learn the author's underlying communication tendencies:

- tone
- rhythm
- sentence variation
- paragraph spacing
- vocabulary
- confidence
- use of numbers
- use of questions
- use of contrast
- use of lists
- use of slang
- capitalization
- punctuation
- degree of technical language
- use of personal perspective
- skepticism
- humor
- conviction
- ways of introducing ideas
- ways of ending ideas

These are tendencies, NOT rules.

The author does not have one permanent writing format.

Do not mechanically reproduce unusual grammar mistakes.

Do not deliberately insert mistakes just to appear human.

Do not copy sentences from the examples.

Create original writing.

==================================================
RESEARCH TASK
==================================================

Find the strongest useful idea inside the supplied research.

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
- opportunities creators may have missed
- opportunities builders may have missed
- contradictions
- important second-order effects

Do not manufacture importance.

If the development is ordinary, explain what is actually useful
about it rather than pretending it is revolutionary.

Never invent facts.

Only make factual claims supported by the supplied research.

Do not claim that the author personally experienced, tested,
bought, used, or witnessed something unless the research or
request explicitly proves it.

==================================================
WRITER PROFILE
==================================================

{profile_text}

==================================================
RESEARCH QUERY
==================================================

{research.get("query", "")}

==================================================
RESEARCH RESULTS
==================================================

{sources_text}

==================================================
OUTPUT
==================================================

Return exactly these sections:

CATEGORY:
<best category>

WHAT HAPPENED:
<clear factual explanation>

WHY IT MATTERS:
<why this development is genuinely interesting or useful>

CONTENT ANGLE:
<the strongest possible angle for the creator>

DRAFT:
<original ready-to-post social-media draft>

SOURCES:
<source URLs>

==================================================
DRAFT RULES
==================================================

The DRAFT must be:

- between 0 and {MAX_DRAFT_CHARACTERS} characters
- complete
- original
- natural
- readable
- supported by the research
- appropriate for the specific topic

There is NO minimum character requirement.

A short idea should remain short.

A complex idea can use more space.

Do not add filler simply to make the draft longer.

Do not cut the draft in the middle of a sentence.

Do not end on an incomplete thought.

Do not use a generic introduction.

Avoid automatically beginning with:

"Here's an interesting..."
"According to..."
"Breaking..."
"Today I discovered..."

unless there is a genuinely compelling reason to do so.

Use line breaks when they improve rhythm.

Do not force emojis.

Do not force all-caps.

Do not force slang.

Do not force questions.

Do not force lists.

Use those devices only when they naturally fit the idea.

==================================================
FINAL QUALITY CHECK
==================================================

Before returning the answer, silently check:

1. Is every factual claim supported by the research?
2. Is the draft original?
3. Does the structure fit THIS topic?
4. Does it avoid blindly copying the author's examples?
5. Does it sound natural?
6. Is it complete?
7. Is it 0–{MAX_DRAFT_CHARACTERS} characters?
8. Is there unnecessary filler?
9. Is the ending complete?
10. Would this actually be usable as a social-media post?

If the draft exceeds {MAX_DRAFT_CHARACTERS}, rewrite it shorter.

NEVER simply truncate the draft.

REQUEST TYPE:
{request_type}
"""


# ---------------------------------------------------------
# GENERATION
# ---------------------------------------------------------

def generate_intelligence(
    research,
    request_type="feed",
):
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
                    "You are a precise crypto research "
                    "and content intelligence assistant. "
                    "Follow the requested output structure. "
                    "Return complete writing."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    text = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    if not text:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    if len(text) < 100:
        raise RuntimeError(
            "Groq returned an unexpectedly short response."
        )

    # -----------------------------------------------------
    # Extract the draft so we can verify its length.
    # -----------------------------------------------------

    draft = extract_section(
        text,
        "DRAFT:",
        "SOURCES:",
    )

    if draft:
        draft_length = len(
            draft.strip()
        )

        logger.info(
            "Generated draft length: %d characters",
            draft_length,
        )

        if draft_length > MAX_DRAFT_CHARACTERS:
            logger.warning(
                "Generated draft exceeds %d characters.",
                MAX_DRAFT_CHARACTERS,
            )

            text = regenerate_shorter(
                research,
                request_type,
                text,
            )

    # -----------------------------------------------------
    # Append source URLs once.
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

    if sources and "\nSOURCES\n" not in text:
        text += "\n\nSOURCES\n"

        for index, url in enumerate(
            sources,
            start=1,
        ):
            text += f"{index}. {url}\n"

    return text


# ---------------------------------------------------------
# SECTION EXTRACTION
# ---------------------------------------------------------

def extract_section(
    text,
    start_marker,
    end_marker=None,
):
    start_index = text.find(
        start_marker
    )

    if start_index == -1:
        return ""

    start_index += len(
        start_marker
    )

    if end_marker:
        end_index = text.find(
            end_marker,
            start_index,
        )

        if end_index == -1:
            section = text[start_index:]
        else:
            section = text[
                start_index:end_index
            ]
    else:
        section = text[start_index:]

    return section.strip()


# ---------------------------------------------------------
# REGENERATE OVER-LENGTH DRAFT
# ---------------------------------------------------------

def regenerate_shorter(
    research,
    request_type,
    previous_response,
):
    draft = extract_section(
        previous_response,
        "DRAFT:",
        "SOURCES:",
    )

    if not draft:
        return previous_response

    prompt = f"""
Rewrite the following social-media draft.

Keep the core idea and factual claims.

Make it shorter and complete.

Maximum length: {MAX_DRAFT_CHARACTERS} characters.

There is no minimum length.

Do not simply cut the text at the character limit.

Rewrite it naturally so the final thought is complete.

Do not add explanations.

Return ONLY the rewritten draft.

DRAFT:

{draft}
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.65,
        max_tokens=700,
        messages=[
            {
                "role": "system",
                "content": (
                    "Rewrite social-media drafts naturally "
                    "while preserving factual accuracy."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    shorter = (
        response
        .choices[0]
        .message
        .content
        .strip()
    )

    if not shorter:
        return previous_response

    if len(shorter) > MAX_DRAFT_CHARACTERS:
        logger.warning(
            "Second-pass draft still exceeds character limit: %d",
            len(shorter),
        )

        return previous_response

    return previous_response.replace(
        draft,
        shorter,
        1,
    )