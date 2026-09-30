import logging
import os
import re
from groq import Groq

from config import GROQ_API_KEY, GROQ_MODEL, WRITER_PROFILE_DIR
from creator_store import (
    init_db, approved_posts, recent_structures, remember_structure, find_banned
)
from pattern_learner import get_patterns

logger = logging.getLogger(__name__)
MAX_RESEARCH_SOURCES = 16
MAX_SOURCE_CHARS = 900

init_db()

def _profile():
    parts = []
    for name in ("examples.txt", "patterns.txt", "rules.txt"):
        path = os.path.join(WRITER_PROFILE_DIR, name)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    value = f.read().strip()
                if value:
                    parts.append(f"--- {name} ---\n{value}")
            except Exception:
                logger.exception("Could not read creator profile: %s", name)
    return "\n\n".join(parts)

def _approved_packet():
    posts = approved_posts(20)
    if not posts:
        return "No approved posts have been logged yet."
    return "\n\n".join(
        f"APPROVED {i}:\n{p['text']}" for i,p in enumerate(posts, 1)
    )

def _research_packet(research):
    if not research:
        return "No research packet was returned."
    sections = []
    answer = re.sub(r"\s+", " ", str(research.get("answer", "") or "")).strip()
    if answer:
        sections.append("RESEARCH SUMMARY:\n" + answer[:1400])
    seen = set()
    results = sorted(list(research.get("results") or []), key=lambda x: float(x.get("score",0) or 0), reverse=True)
    for result in results:
        url = str(result.get("url","") or "").strip()
        title = str(result.get("title","") or "Untitled").strip()
        key = url.lower() or title.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        content = re.sub(r"\s+", " ", str(result.get("content","") or "")).strip()
        sections.append(
            f"SOURCE: {title}\nDOMAIN: {result.get('domain','')}\n"
            f"ANGLE: {result.get('research_angle','general')}\n"
            f"EVIDENCE: {content[:MAX_SOURCE_CHARS]}\nURL: {url}"
        )
        if len(sections) >= MAX_RESEARCH_SOURCES + 1:
            break
    return "\n\n".join(sections)

def _patterns(topic):
    data = get_patterns(topic, hot=any(x in str(topic).lower() for x in ("today","latest","breaking","launch","announced","just")))
    if not data.get("available"):
        return "LIVE HUMAN PATTERN DATA: unavailable. Do not invent trend observations."
    samples = "\n".join(f"- {x['text']}" for x in data.get("sample", [])[:20])
    return (
        f"LIVE HUMAN PATTERN DATA: {data.get('count',0)} public X posts.\n"
        f"Average length: {data.get('length',{}).get('avg_chars','unknown')} chars.\n"
        f"Common vocabulary: {', '.join(data.get('slang',[]))}\n"
        f"Openers observed: {' | '.join(data.get('openers',[])[:10])}\n"
        "Use this only for rhythm, vocabulary and gaps. Never copy a phrase or sentence.\n"
        f"SAMPLES FOR ANALYSIS ONLY:\n{samples}"
    )

def _call(prompt, temperature=0.8, max_tokens=900):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=min(max(int(max_tokens), 200), 1800),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a sharp human crypto-native writer and editor. "
                    "Tone DNA is the single source of truth for voice. "
                    "Write like a person with taste, memory, conviction and specific knowledge. "
                    "Never mention the writing process. Never invent facts."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()

def _quality(text, platform="x"):
    text = str(text or "")
    issues = []
    if "—" in text:
        issues.append("em_dash")
    if re.search(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]", text):
        issues.append("emoji")
    hits = find_banned(text)
    if hits:
        issues.extend([f"banned:{x}" for x in hits])
    if platform == "x":
        if len(text) > 280:
            issues.append("over_280")
        if len(re.findall(r"(?<!\w)#\w+", text)) > 1:
            issues.append("too_many_hashtags")
        if re.search(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+", text):
            issues.append("list_format")
        if re.search(r"(?m)^\s*(?:#+\s+|\*\*.+\*\*)", text):
            issues.append("header_format")
    if re.search(r"\b(?:guaranteed|guarantee|risk[- ]?free|certain profit|sure profit)\b", text, re.I):
        issues.append("financial_safety")
    return sorted(set(issues))

def _structure(text):
    lines = [x.strip() for x in str(text).splitlines() if x.strip()]
    if not lines:
        return "empty"
    first = lines[0]
    if len(lines) == 1:
        return "one_line"
    if "?" in first:
        return "question_open"
    if first.isupper() and len(first) < 100:
        return "all_caps_hook"
    if len(first) < 70 and len(lines) >= 3:
        return "short_hook_short_paragraphs"
    if len(text) > 500:
        return "long_form"
    return "short_paragraphs"

def _tone_context():
    return (
        "TONE DNA, OWNER PROFILE AND APPROVED POSTS ARE THE SOURCE OF TRUTH.\n"
        "Do not imitate a generic crypto creator. Learn cadence, vocabulary, "
        "sentence pressure, humor and degree of bluntness from the material below.\n"
        "TONE DNA:\n" + _profile() + "\n\n"
        "LAST 20 APPROVED POSTS:\n" + _approved_packet()
    )

def _base_rules(platform):
    x_rules = """
X FORMAT:
No emojis anywhere. No em dash. No headers, bold or bullet lists.
One sharp idea per post. Hook in the first line.
Keep it under 280 characters unless the request explicitly asks for a thread.
No closing moral or summary.
"""
    return f"""
HARD OUTPUT RULES:
Tone DNA is the authority.
A stranger should believe a human typed this without seeing the prompt.
Start with a human hook, not a topic label or assistant-style setup.
Include at least one concrete, post-specific detail when the research supports one.
For non-research commands, take a clear position. Conviction can be direct, metaphorical,
hyperbolic, idiomatic, a simile, educational analysis, or a mix when natural.
Do not force a position when evidence genuinely does not support one.
Change the structure from recent outputs. Do not reuse the same skeleton twice in a row.
Vary length. Short is allowed. Long is allowed when the platform/request needs it.
Use short forms and crypto-native shorthand naturally when Tone DNA supports it.
Allow small imperfections such as fragments or lowercase starts when they fit the voice.
Do not fabricate personal memories or experiences.
No generic bot-assistant phrasing.
No contrast-frame constructions in any form: "it's not X, it's Y", "this isn't about X, it's about Y",
"not just X but Y", "more than just X", "forget X, think Y".
No rhetorical setups: "here's the thing", "let that sink in", "read that again",
"think about it", "ever wondered".
No filler openers: "in today's fast-paced world", "in the world of crypto", "let's dive in",
"let's break it down", "buckle up".
Avoid triplet lists used for rhythm.
Do not end every post with a question. Ask only when a real person would genuinely ask it.
Never invent facts, numbers, dates, quotes, motives or outcomes.
Do not use these words/phrases: actually, honestly, essentially, literally, game-changer,
revolutionary, groundbreaking, unlock, unleash, delve, landscape, ecosystem, journey, navigate,
tapestry, testament, realm, paradigm, seamless, robust, leverage, "at the end of the day",
"the future of", "changing the game".
{ x_rules if platform == "x" else "Match the requested platform's natural formatting and behavior."}
"""

def _thinking():
    return """
PRIVATE THINKING. Do not output this section.
First identify the one idea worth saying.
Then identify the strongest verified detail.
Then decide what you believe about it.
Then choose a structure that differs from recent structures.
For humor/satire, identify the real tension in the current story before writing the joke.
For meme/comic concepts, think visually: text-only, character reaction, arrow/box annotation,
or one/two-panel setup. The joke must come from a specific observation.
"""

def _research_requirements():
    return """
RESEARCH DISCIPLINE:
Use the research packet as evidence, not decoration.
Prefer primary sources. Cross-check important numbers, dates and claims.
Treat unsupported details as unknown. Never fill gaps from memory.
Separate verified facts, single-source claims and uncertainty.
Find the overlooked detail, contradiction, timing angle, risk, incentive or mechanism.
"""

def _one_pass(prompt, platform, temperature=0.82, max_tokens=900):
    structures = recent_structures(10)
    prompt = prompt + "\n\nRECENT STRUCTURES TO AVOID:\n" + ", ".join(structures[-8:])
    return _call(prompt, temperature, max_tokens)

MAX_OUTPUT_CHARS = 900

def _within_output_limit(text, limit=MAX_OUTPUT_CHARS):
    return len(str(text or "").strip()) <= limit

def _fit_output(text, prompt, platform, limit=MAX_OUTPUT_CHARS):
    """Return a complete output. Never truncate; regenerate if it exceeds the limit."""
    text = str(text or "").strip()
    if _within_output_limit(text, limit):
        return text

    for _ in range(2):
        compact_prompt = f"""
{prompt}

LENGTH CONTROL:
The previous draft exceeded the hard {limit}-character output ceiling.
Rewrite the complete output from scratch so the ENTIRE response is {limit} characters or fewer.
Do not cut, clip, truncate, omit a required section, or leave an unfinished sentence.
Preserve the strongest verified details and the full requested structure.
Compress wording naturally. Finish every section and punchline.
Return only the complete final output.

PREVIOUS DRAFT:
{text}
"""
        text = _call(compact_prompt, 0.72, 1400).strip()
        if _within_output_limit(text, limit):
            return text

    # A final compact regeneration is preferable to returning a clipped response.
    final_prompt = f"""
{prompt}

FINAL LENGTH CONTROL:
Produce a complete final response of {limit} characters or fewer.
Every requested element must be finished. Do not truncate anything.
Return only the complete response.
"""
    return _call(final_prompt, 0.62, 1200).strip()

def _repair(text, prompt, platform):
    issues = _quality(text, platform)
    if not issues:
        return text.strip()
    repair_prompt = f"""
{_tone_context()}
{_base_rules(platform)}

Rewrite ONLY the draft below. Fix: {", ".join(issues)}.
Keep the same core idea and verified details. Make it sound more human, not more polished.
Return only the finished draft.
The complete response must remain within 900 characters. Never truncate it.

DRAFT:
{text}
"""
    fixed = _call(repair_prompt, 0.5, 700)
    return fixed.strip()

def research_for_creator(topic, research):
    patterns = _patterns(topic)
    prompt = f"""
{_tone_context()}
{_research_requirements()}
{_base_rules("telegram")}
{_thinking()}

COMMAND: /research
Remain neutral and evidence-led. Do not take a political, financial or promotional position.

TOPIC:
{topic}

RESEARCH PACKET:
{_research_packet(research)}

HUMAN PATTERN DATA:
{patterns}

Write a compact research brief. Keep the existing useful research structure:
RESEARCH BRIEF
Topic: ...
BOTTOM LINE
...
VERIFIED
- ...
SINGLE-SOURCE
- ...
UNCERTAIN / RUMOR
- ...
WHY IT IS INTERESTING
- ...
KEY EVIDENCE
- ...
CONTENT ANGLES
1. ...
2. ...
3. ...
SOURCE NOTES
- title — url

Then add one genuinely different alternate angle.
Do not invent source labels or facts.
"""
    primary = _one_pass(prompt, "telegram", 0.55, 1500)
    primary = _repair(primary, prompt, "telegram")
    return _fit_output(primary, prompt, "telegram")

def creative_ideas(mode, request, research):
    patterns = _patterns(request)
    if mode == "meme":
        mode_rules = """
Return exactly 2 strong meme/comic angles. Do not return 3 options and do not add an alternate.
For each angle use: FORMAT, OBSERVATION, EXECUTION, PUNCHLINE.
The observation must come from the researched situation.
Think like a pro crypto memecomic artist. Build the joke around the real tension.
Each angle must be executable as an actual meme/comic, not a generic topic or post idea.
Make the two executions meaningfully different in format or joke mechanism.
"""
    else:
        mode_rules = """
Return exactly 3 distinct post ideas and one alternate.
For each: HOOK and ANGLE.
Each idea must have a specific detail and a clear editorial direction.
"""
    prompt = f"""
{_tone_context()}
{_research_requirements()}
{_base_rules("telegram")}
{_thinking()}

COMMAND: /idea
REQUEST:
{request}

RESEARCH PACKET:
{_research_packet(research)}

HUMAN PATTERN DATA:
{patterns}

{mode_rules}
Avoid generic crypto clichés unless the live pattern data shows they are active.
Return no preamble and no process commentary.
"""
    primary = _one_pass(prompt, "telegram", 0.88, 1400)
    primary = _repair(primary, prompt, "telegram")
    return _fit_output(primary, prompt, "telegram")

def create_content(request, research):
    platform = "x"
    low = request.lower()
    if "telegram" in low:
        platform = "telegram"
    if "thread" in low:
        platform = "x_thread"

    patterns = _patterns(request)
    prompt = f"""
{_tone_context()}
{_research_requirements()}
{_base_rules(platform)}
{_thinking()}

COMMAND: /create
REQUEST:
{request}

RESEARCH PACKET:
{_research_packet(research)}

HUMAN PATTERN DATA:
{patterns}

Write the final content now.
The first line must feel like a human thought or observation, not "X is..." or "Here are...".
A stranger reading it should believe a human crypto-native wrote it.
Use at least one specific verified detail from the research when one exists.
Take a clear position. The position may be conviction, metaphor, hyperbole, idiom, simile,
education, analysis or a natural mix.
Use one idea only. Avoid the structure used by the recent outputs.
Vary sentence length and density. Short forms/abbreviations are welcome where natural.
For satire or meme requests, identify the real tension first and make the humor specific.
Return only the finished primary post. No labels, no alternate, no explanation.
"""
    primary = _one_pass(prompt, platform, 0.82, 1100)
    primary = _repair(primary, prompt, "x" if platform.startswith("x") else platform)
    primary = _fit_output(primary, prompt, platform)
    remember_structure(_structure(primary))
    return primary

def revise_content(request, draft, instruction):
    platform = "x"
    low = str(request or "").lower()
    if "telegram" in low:
        platform = "telegram"
    prompt = f"""
{_tone_context()}
{_base_rules(platform)}
{_research_requirements()}

CURRENT DRAFT:
{draft}

OWNER EDIT INSTRUCTION:
{instruction}

Rewrite the draft according to the instruction.
Preserve factual claims unless the instruction changes them.
Do not add unsupported claims.
Return only the revised draft.
"""
    revised = _call(prompt, 0.65, 900)
    issues = _quality(revised, "x" if platform.startswith("x") else platform)
    for _ in range(2):
        if not issues:
            break
        revised = _call(
            f"{_tone_context()}\nFix these deterministic issues: {', '.join(issues)}. "
            f"Return only the revised draft.\nDRAFT:\n{revised}",
            0.5, 700
        )
        issues = _quality(revised, "x" if platform.startswith("x") else platform)
    remember_structure(_structure(revised))
    return revised
def style_suggestions():
    posts = approved_posts(20)
    if not posts:
        return "No approved posts are logged yet."
    packet = "\n\n".join(p["text"] for p in posts)
    prompt = f"""
You are updating a creator's Tone DNA suggestion sheet.

Existing Tone DNA:
{_profile()}

Last approved posts:
{packet}

Identify only changes that are supported by repeated evidence in the approved posts.
Do not overwrite the Tone DNA. Do not invent traits.
Return concise suggestions under:
KEEP
ADD
REMOVE
TEST
"""
    return _call(prompt, 0.25, 700)
