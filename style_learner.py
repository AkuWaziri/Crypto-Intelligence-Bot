import json
import os
import logging

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

PROFILE_FILE = "writing_profile.json"
EXAMPLES_FILE = "writing_examples.json"

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get(
    "GROQ_MODEL",
    "openai/gpt-oss-120b",
)


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:
            return json.load(file)

    except Exception:
        logger.exception(
            "Could not load %s",
            path,
        )
        return default


def save_json(path, data):
    with open(
        path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def load_profile():
    return load_json(
        PROFILE_FILE,
        {
            "version": 1,
            "purpose": (
                "Learn and reproduce the user's "
                "natural crypto writing patterns "
                "without copying individual posts."
            ),
            "voice": {},
            "structure": {},
            "language": {},
            "content_style": {},
            "crypto_style": {},
            "human_patterns": {},
            "examples": [],
        },
    )


def load_examples():
    data = load_json(
        EXAMPLES_FILE,
        {"examples": []},
    )

    examples = data.get(
        "examples",
        [],
    )

    return [
        item.get("text", "").strip()
        for item in examples
        if isinstance(item, dict)
        and item.get("text", "").strip()
    ]


def build_analysis_prompt(
    examples,
    existing_profile,
):
    joined_examples = "\n\n--- EXAMPLE ---\n\n".join(
        examples
    )

    profile_json = json.dumps(
        existing_profile,
        indent=2,
        ensure_ascii=False,
    )

    return f"""
You are a writing-pattern analyst.

Your task is to analyze the user's actual writing examples and
update a structured writing profile.

The goal is NOT to copy the examples.

The goal is to identify repeatable characteristics that can later
help another AI produce original writing that feels naturally
consistent with this author's style.

Analyze:

- tone
- personality
- confidence
- technical depth
- formality
- hook patterns
- paragraph patterns
- transitions
- endings
- sentence length
- vocabulary
- preferred phrasing
- avoided phrasing
- capitalization
- punctuation
- emoji usage
- use of numbers
- use of examples
- use of contrasts
- questions
- lists
- crypto terminology
- preferred content angles
- natural imperfections
- rhythm
- repetition patterns
- personal observations
- opinion patterns

Important rules:

1. Do not invent characteristics that are not supported by the examples.
2. Do not copy complete sentences from the examples.
3. Do not turn one unusual sentence into a permanent writing rule.
4. Look for repeated patterns across multiple examples.
5. Preserve uncertainty when the evidence is weak.
6. Prefer concise, practical observations.
7. The profile should describe the author, not the individual topics.
8. Do not store private or sensitive personal information.
9. Do not make the future writer imitate typos mechanically.
10. Natural human variation is more important than artificial mistakes.

Return ONLY valid JSON.

The JSON must follow this structure:

{profile_json}

Here are the user's writing examples:

{joined_examples}
"""


def learn_profile():
    examples = load_examples()

    if not examples:
        raise RuntimeError(
            "No writing examples found. "
            "Add examples to writing_examples.json first."
        )

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    profile = load_profile()

    client = Groq(
        api_key=GROQ_API_KEY
    )

    prompt = build_analysis_prompt(
        examples,
        profile,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You analyze writing patterns "
                    "and return valid JSON only."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
    )

    text = (
        response.choices[0]
        .message
        .content
        .strip()
    )

    if not text:
        raise RuntimeError(
            "Groq returned an empty writing profile."
        )

    if text.startswith("```"):
        text = text.strip("`")

        if text.startswith("json"):
            text = text[4:].strip()

    try:
        learned_profile = json.loads(text)

    except json.JSONDecodeError as exc:
        logger.error(
            "Invalid JSON returned by Groq:\n%s",
            text,
        )

        raise RuntimeError(
            "Groq returned invalid JSON "
            "for the writing profile."
        ) from exc

    if not isinstance(
        learned_profile,
        dict,
    ):
        raise RuntimeError(
            "Writing profile must be a JSON object."
        )

    learned_profile["version"] = 1

    learned_profile["purpose"] = (
        "Learn and reproduce the user's "
        "natural crypto writing patterns "
        "without copying individual posts."
    )

    save_json(
        PROFILE_FILE,
        learned_profile,
    )

    logger.info(
        "Writing profile updated from %d examples.",
        len(examples),
    )

    return learned_profile


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO
    )

    profile = learn_profile()

    print(
        json.dumps(
            profile,
            indent=2,
            ensure_ascii=False,
        )
    )