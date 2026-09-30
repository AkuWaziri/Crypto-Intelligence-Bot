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

def _call(prompt, temperature=0.8, max_tokens=1200):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=temperature,
        max_tokens=min(max(int(max_tokens), 200), 2200),
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto creator and editor. "
                    "Tone DNA is the authority. Never substitute generic AI style. "
                    "Do not mention your process. Never invent facts."
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
    if re.search(r"\b(?:guaranteed|guarantee|risk[- ]?free|certain profit|sure profit)\b", text, re.I):
        issues.append("financial_safety")
    return issues

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
        "TONE DNA:\n" + _profile() + "\n\n"
        "LAST 20 APPROVED POSTS:\n" + _approved_packet()
    )

def _base_rules(platform):
    return f"""
HARD OUTPUT RULES:
- Tone DNA overrides default assistant style.
- No emojis.
- No em dash. Use periods or commas.
- No corporate/SEO language.
- No generic assistant preamble.
- No contrast-frame constructions such as "it's not X, it's Y", "not just X but Y", "forget X, think Y".
- No rhetorical filler such as "here's the thing", "let that sink in", "read that again", "think about it".
- Never use banned phrases.
- Never invent facts, numbers, dates, quotes, motives or outcomes.
- Avoid triplet lists used as rhythm.
- Do not end every post with a question.
- Keep the writing human, specific and opinionated when the command is not /research.
- {platform.upper()} output must match its platform behavior.
"""

def _thinking():
    return """
PRIVATE THINKING PASS. Do not output:
1. What is the one thing I actually want to say?
2. What do I believe and what is my position?
3. What would most people say here? Avoid that take.
4. What specific verified detail makes this credible?
5. Who is reading and what do they already know?
6. What is the risk of being wrong or misread?
"""

def _research_requirements():
    return """
RESEARCH DISCIPLINE:
Use the research packet as evidence, not as decoration.
Prefer primary sources. Cross-check important numbers, dates and claims.
Treat a fact as verified only when independently supported by at least two sources.
Treat a claim with one supporting source as single-source.
Treat a claim described as unverified, alleged or speculative as rumor/uncertain.
If evidence is missing, say not found. Never fill gaps from memory.
Look for the overlooked detail, contradiction, timing angle, risk or incentive.
"""

def _draft_and_rewrite(prompt, platform, temperature=0.82, max_tokens=1400):
    structures = recent_structures(10)
    full = prompt + "\n\nRECENT STRUCTURES TO AVOID REUSING:\n" + ", ".join(structures)
    drafts = []
    for angle in ("direct observation", "unexpected consequence", "incentive or contradiction"):
        drafts.append(_call(full + f"\n\nINTERNAL DRAFT ANGLE: {angle}. Draft internally only.", temperature, max_tokens))
    best_prompt = full + (
        "\n\nYou have three internal drafts. Select the strongest one, then rewrite it "
        "in Tone DNA voice. Do not output the drafts or explain the choice.\n"
        "Run a private anti-AI quality check before returning."
    )
    primary = _call(best_prompt, temperature, max_tokens)
    alternate = _call(
        full + "\n\nCreate ONE materially different alternate angle. Return only the alternate.",
        temperature, max_tokens
    )
    return primary.strip(), alternate.strip()

def research_for_creator(topic, research):
    patterns = _patterns(topic)
    prompt = f"""
{_tone_context()}

{_research_requirements()}

{_base_rules("telegram")}

This is /research. It must remain neutral and evidence-led.
Do not take a political, financial or promotional position.

TOPIC:
{topic}

RESEARCH PACKET:
{_research_packet(research)}

HUMAN PATTERN PASS:
{patterns}

Return the primary research brief and one alternate angle.

PRIMARY:
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

ALTERNATE:
A different evidence-led angle in 3-5 concise lines.

No unsupported claims. No invented source labels.
"""
    primary, alternate = _draft_and_rewrite(prompt, "telegram", 0.55, 1500)
    return f"{primary}\n\nALTERNATE\n{alternate}"

def creative_ideas(mode, request, research):
    patterns = _patterns(request)
    mode_rules = """
MEME MODE:
Return exactly 3 distinct concepts plus one alternate.
Comedy must come from a specific human observation in the researched situation.
No generic crypto clichés unless the live pattern data shows they are active.
Each concept must include FORMAT, OBSERVATION, EXECUTION, PUNCHLINE.
""" if mode == "meme" else """
POST IDEA MODE:
Return exactly 3 distinct story ideas plus one alternate.
Each must include HOOK and ANGLE.
Go beyond the headline. Find mechanism, incentive, consequence, behavior,
misconception, data, timeline, business model, failure mode or practical lesson.
"""
    prompt = f"""
{_tone_context()}

{_research_requirements()}
{_base_rules("telegram")}
{_thinking()}

REQUEST:
{request}

RESEARCH PACKET:
{_research_packet(research)}

HUMAN PATTERN PASS:
{patterns}

{mode_rules}

Return no preamble, no strategy commentary and no source dump.
"""
    primary, alternate = _draft_and_rewrite(prompt, "telegram", 0.92, 1200)
    return f"{primary}\n\nALTERNATE\n{alternate}"

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

REQUEST:
{request}

RESEARCH PACKET:
{_research_packet(research)}

HUMAN PATTERN PASS:
{patterns}

PLATFORM:
{platform}

WRITE THE FINAL CONTENT.
X: one idea, sharp hook, under 280 characters unless the request explicitly asks for a thread.
Telegram: conversational, detailed enough to be useful, short paragraphs.
Threads: each post must stand on its own.
No headers, bold or bullets in an X post.
Do not summarize the post at the end.
Do not fabricate personal experiences.

Return only the finished primary draft.
"""
    primary, alternate = _draft_and_rewrite(prompt, platform, 0.82, 1500)
    issues = _quality(primary, "x" if platform.startswith("x") else platform)
    if issues:
        repair = f"""
{_tone_context()}

REWRITE THE DRAFT. Fix every deterministic issue: {", ".join(issues)}.
Preserve the central idea, factual grounding and Tone DNA.
Return only the repaired draft.

DRAFT:
{primary}
"""
        for _ in range(2):
            primary = _call(repair, 0.55, 500)
            issues = _quality(primary, "x" if platform.startswith("x") else platform)
            if not issues:
                break
    alt_issues = _quality(alternate, "x" if platform.startswith("x") else platform)
    if alt_issues:
        alternate = _call(
            f"{_tone_context()}\nRewrite this alternate to remove: {', '.join(alt_issues)}. Return only the alternate.\n{alternate}",
            0.55, 500
        )
    remember_structure(_structure(primary))
    return f"{primary}\n\nALTERNATE\n{alternate}"

def extract_primary(text):
    return str(text or "").split("\n\nALTERNATE", 1)[0].strip()
