import os
import re
import logging

from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, WRITER_PROFILE_DIR

logger = logging.getLogger(__name__)

MAX_RESEARCH_SOURCES = 14
MAX_SOURCE_CHARS = 900


def _profile():
    parts = []
    for name in ("examples.txt", "patterns.txt", "rules.txt"):
        path = os.path.join(WRITER_PROFILE_DIR, name)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                value = f.read().strip()
            if value:
                parts.append(f"--- {name} ---\n{value}")
        except Exception:
            logger.exception("Could not read creator profile: %s", name)
    return "\n\n".join(parts)


def _clean(value, limit=None):
    text = re.sub(r"\\s+", " ", str(value or "")).strip()
    if limit and len(text) > limit:
        text = text[:limit].rstrip()
    return text


def _research_packet(research):
    if not research:
        return "No research packet was returned."

    sections = []
    answer = _clean(research.get("answer"), 1400)
    if answer:
        sections.append("RESEARCH SUMMARY:\n" + answer)

    results = list(research.get("results") or [])
    results.sort(key=lambda x: float(x.get("score", 0) or 0), reverse=True)

    seen = set()
    for index, result in enumerate(results[:MAX_RESEARCH_SOURCES], 1):
        url = _clean(result.get("url"))
        key = url or _clean(result.get("title"))
        if not key or key in seen:
            continue
        seen.add(key)
        title = _clean(result.get("title"), 220) or "Untitled"
        content = _clean(result.get("content"), MAX_SOURCE_CHARS)
        source = _clean(result.get("source") or result.get("domain"))
        if not content:
            continue
        sections.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"SOURCE: {source}\n"
            f"EVIDENCE: {content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sections) or "No usable evidence was returned."


def _call(prompt, temperature=0.8, max_tokens=900):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing.")

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=min(max(int(max_tokens), 200), 1800),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto content editor, researcher, "
                    "story developer and creator. Write like a real human. "
                    "Be specific, skeptical and useful. Never invent facts."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    return str(response.choices[0].message.content or "").strip()


def research_for_creator(topic, research):
    packet = _research_packet(research)
    profile = _profile()
    prompt = f"""
You are the research desk for a serious crypto content creator.

TOPIC:
{topic}

CREATOR DNA:
{profile}

EVIDENCE PACKET:
{packet}

Produce a creator-grade research brief. Do not write a generic news summary.

Your private process:
1. Establish what is directly supported by the sources.
2. Separate facts, interpretations and unresolved claims.
3. Identify the most interesting mechanism, tension, number, behavior,
   contradiction, consequence or overlooked detail.
4. Find what is genuinely worth turning into content.
5. Remove duplicated, weak or promotional claims.
6. Never upgrade a source's claim into fact.
7. Never invent missing numbers, dates, quotes, motives or outcomes.
8. If sources disagree, state the disagreement clearly.
9. Prefer primary/official evidence when available.
10. Think like a researcher first and an editor second.

Return exactly this structure:

RESEARCH BRIEF
Topic: <topic>

BOTTOM LINE
<2-4 concise sentences explaining what the evidence actually shows>

WHAT HAPPENED
- <fact>
- <fact>
- <fact>

WHY IT IS INTERESTING
- <specific observation>
- <specific mechanism/consequence>

KEY EVIDENCE
- <important fact + source context>
- <important fact + source context>
- <important fact + source context>

WHAT IS UNCERTAIN
- <uncertain or disputed point>
- <uncertain or disputed point>

CONTENT ANGLES
1. <strong specific story angle>
2. <strong different story angle>
3. <strong different story angle>
4. <strong different story angle>
5. <strong different story angle>

SOURCE NOTES
- <source title> — <url>
- <source title> — <url>

Do not add a generic conclusion. Do not use hype.
""".strip()
    return _call(prompt, temperature=0.55, max_tokens=1200)


def creative_ideas(mode, request, research):
    packet = _research_packet(research)
    profile = _profile()

    if mode == "meme":
        task = """
Generate exactly 5 distinct meme/comic concepts.

The comedy must come from a specific human observation in THIS situation,
not from generic crypto clichés.

Explore different mechanisms such as:
- deadpan observation
- absurd consequence
- social behavior
- contradiction
- status games
- understatement
- awkward realism
- visual reversal
- character interaction
- text-only comic

Avoid generic moon/FOMO/rocket/rug/trader crying jokes unless the situation
makes that exact joke unusually specific.

For each concept return:
MEME 1
CORE OBSERVATION:
FORMAT:
VISUAL:
TEXT / DIALOGUE:
PUNCHLINE:
WHY IT WORKS:

Use short, drawable execution. The punchline should not explain itself.
"""
    else:
        task = """
Generate exactly 7 strong content ideas.

These are editorial story ideas, not finished posts.

Make the seven ideas materially different. Explore:
- overlooked detail
- mechanism
- consequence
- human behavior
- data point
- misconception
- practical lesson
- contradiction
- timeline
- business/incentive angle
- technical explanation
- cultural angle

For each return:
IDEA 1
HOOK:
ANGLE:
FORMAT:
WHY THIS IS WORTH MAKING:

The hook should sound like a creator noticing something, not a news headline.
Avoid generic phrases such as "why this matters", "the future of", and
"everything you need to know".
"""
    prompt = f"""
You are the senior creative director for a crypto creator.

REQUEST:
{request}

CREATOR DNA:
{profile}

RESEARCH:
{packet}

{task}

Private rules:
- Research is evidence, not a script.
- Never invent facts.
- If the request is current, rely on the evidence supplied.
- Do not repeat the same thesis in different wording.
- Reject obvious first-order ideas.
- Prefer a specific observation over broad commentary.
- The creator's voice should influence rhythm and taste, not factual claims.
- Do not write the finished social post unless the requested field explicitly
  asks for dialogue/text.
- Think broadly internally, then output only the requested ideas.
""".strip()
    return _call(prompt, temperature=0.95, max_tokens=1400)


def create_content(request, research):
    packet = _research_packet(research)
    profile = _profile()

    prompt = f"""
You are the final editor and writer for a crypto creator.

REQUEST:
{request}

CREATOR DNA:
{profile}

RESEARCH:
{packet}

Create the requested content at professional creator standard.

PRIVATE EDITORIAL PROCESS:
1. Determine the exact deliverable and platform implied by the request.
2. If the request is ambiguous, choose the most natural creator format.
3. Find one central idea. Do not cram multiple unrelated ideas together.
4. Use research as evidence. Do not invent facts.
5. Distinguish confirmed facts from interpretation.
6. If a claim cannot be verified from the evidence, either qualify it or omit it.
7. Avoid press-release language, SEO language and generic AI phrasing.
8. Match the creator DNA: conversational, observant, crypto-native, specific,
   occasionally funny, never artificially polished.
9. Use a strong opening. Do not begin with "Today", "Here's why", "Let's talk
   about", "In the world of crypto", or "Everything you need to know".
10. Keep useful technical detail when it actually improves understanding.
11. Cut repetition aggressively.
12. If the request asks for a thread, make every post advance the story.
13. If it asks for a meme/comic, give a usable visual script rather than an essay.
14. If it asks for a post, write a publish-ready post rather than an outline.
15. Never fabricate a personal experience or say the creator tested/discovered
   something unless the evidence or request establishes that.

QUALITY CHECK:
- Is the first line worth stopping for?
- Is there one clear idea?
- Is every factual claim supported?
- Does it sound human?
- Does it sound like this creator?
- Is anything unnecessary?
- Could the piece be shorter without losing the point?

Return ONLY the finished deliverable. No preamble, no explanation, no source list,
no labels such as "AI generated", and no editorial commentary.
""".strip()
    return _call(prompt, temperature=0.82, max_tokens=1500)
