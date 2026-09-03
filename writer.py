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

client = Groq(api_key=GROQ_API_KEY)


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


def clean_model_text(text: str) -> str:
    if not text:
        return ""

    text = re.sub(
        r"```(?:text|markdown|json)?",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = text.replace("```", "")

    # Remove malformed citation artifacts.
    text = re.sub(
        r"ã€\d+(?:â€[^ã€‘]*)?ã€‘",
        "",
        text,
    )

    # Remove markdown hyperlinks while preserving visible text.
    text = re.sub(
        r"\[([^\]]+)\]\([^)]+\)",
        r"\1",
        text,
    )

    return text.strip()


def extract_section(
    text: str,
    section_name: str,
    next_sections,
):
    next_pattern = "|".join(
        re.escape(item)
        for item in next_sections
    )

    pattern = (
        rf"{re.escape(section_name)}\s*:\s*"
        rf"(.*?)(?=\n\s*(?:{next_pattern})\s*:|\Z)"
    )

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        return ""

    return match.group(1).strip()


def parse_output(text: str):
    text = clean_model_text(text)

    category = extract_section(
        text,
        "CATEGORY",
        [
            "CONTENT ANGLE",
            "DRAFT",
            "SOURCES",
        ],
    )

    content_angle = extract_section(
        text,
        "CONTENT ANGLE",
        [
            "DRAFT",
            "SOURCES",
        ],
    )

    draft = extract_section(
        text,
        "DRAFT",
        [
            "SOURCES",
        ],
    )

    return {
        "category": category,
        "content_angle": content_angle,
        "draft": draft,
    }


def draft_looks_cut_off(draft: str) -> bool:
    if not draft:
        return True

    stripped = draft.strip()

    if len(stripped) < 20:
        return True

    lower = stripped.lower()

    unfinished_endings = (
        " and",
        " or",
        " but",
        " because",
        " that",
        " which",
        " with",
        " for",
        " to",
        " of",
        " in",
        " on",
        " at",
        " into",
        " from",
        " as",
        " than",
        " is",
        " are",
        " was",
        " were",
        " the",
        " a",
        " an",
        ",",
        ":",
        "-",
        "–",
        "—",
        "(",
        "[",
        "...",
    )

    if lower.endswith(unfinished_endings):
        return True

    if stripped.count("(") > stripped.count(")"):
        return True

    if stripped.count("[") > stripped.count("]"):
        return True

    return False


def build_research_text(research):
    sources = []

    for index, result in enumerate(
        research.get("results", []),
        start=1,
    ):
        title = result.get("title", "").strip()
        content = result.get("content", "").strip()
        url = result.get("url", "").strip()

        # Keep the prompt compact to reduce token consumption.
        compact_content = content[:1000]

        sources.append(
            f"SOURCE {index}\n"
            f"TITLE: {title}\n"
            f"CONTENT: {compact_content}\n"
            f"URL: {url}"
        )

    return "\n\n".join(sources)


def get_draft_max(request_type):
    if request_type == "feed":
        return MAX_FEED_DRAFT_CHARACTERS

    return MAX_DRAFT_CHARACTERS


def build_prompt(
    research,
    request_type="feed",
    retry=False,
):
    profile = load_writer_profile()

    sources_text = build_research_text(research)

    draft_max = get_draft_max(request_type)

    retry_instruction = ""

    if retry:
        retry_instruction = f"""
RETRY INSTRUCTION

The previous DRAFT failed validation.

Write a completely new DRAFT.

Maximum length: {draft_max} characters.

Make it shorter if necessary.

The DRAFT MUST finish naturally.

Do not end with an incomplete sentence,
unfinished thought, unfinished list, or "...".

Do not explain the retry.
"""

    return f"""
You are a senior crypto research editor and content strategist.

Your job is to transform current research into useful,
fact-grounded content intelligence for a crypto creator.

REQUEST TYPE:
{request_type}

You have TWO responsibilities.

RESPONSIBILITY 1 — EDITORIAL INTELLIGENCE

Understand what the research actually establishes.

Determine:

- what is confirmed
- what is uncertain
- what is genuinely important
- what is surprising
- what is changing
- what people may be overlooking
- what second-order implications could matter
- whether there is a meaningful opportunity
- whether there is a meaningful risk
- whether the story is bullish, bearish, neutral, skeptical,
  funny, controversial, educational, practical or simply interesting

Do NOT force every story into a bullish opportunity.

Do NOT force every story into a bearish warning.

Do NOT manufacture urgency.

Do NOT manufacture controversy.

Do NOT manufacture a creator opportunity when the evidence
does not support one.

The research determines the editorial stance.

If evidence is weak or speculative, say so.

If something is confirmed, distinguish it from speculation.

Never turn a possibility into a fact.

Never invent information.

RESPONSIBILITY 2 — CREATOR CONTENT STRATEGY

Determine the SINGLE strongest content angle a crypto creator
could use.

CONTENT ANGLE is NOT a summary of the research.

It is a professional recommendation telling the creator:

- what to write
- what perspective to take
- what part of the story deserves attention
- what evidence or examples to emphasize
- what the reader should understand
- what direction the creator can take if expanding the post

The CONTENT ANGLE should be useful even if the creator later
rewrites or expands the DRAFT using another writing tool.

A strong content angle can be:

- contrarian observation
- overlooked implication
- practical explainer
- comparison
- warning
- market thesis
- builder opportunity
- user-focused observation
- case study
- actionable post
- skeptical take
- trend analysis
- surprising fact
- debate/question

Do NOT automatically recommend:

"first mover advantage"

"start building now"

"this is a game changer"

"the future is here"

Only use such framing when the research genuinely supports it.

WRITING PROFILE

The profile describes HOW the creator naturally writes.

Use it flexibly.

Do not mechanically copy examples.

Do not repeatedly use the same hooks.

Do not repeatedly use the same paragraph structure.

Do not force slang.

Do not force all-caps.

Do not deliberately insert mistakes.

Different subjects should produce different writing.

The topic determines the shape.

The research determines the stance.

The writing profile influences the expression.

Never copy complete sentences or distinctive phrases
from the examples.

Never invent personal experiences.

WRITER PATTERNS:
{profile["patterns"]}

WRITER RULES:
{profile["rules"]}

WRITER EXAMPLES:
{profile["examples"]}

RESEARCH QUERY:
{research.get("query", "")}

RESEARCH:

{sources_text}

FACTUAL DISCIPLINE

Only make factual claims supported by the supplied research.

Do not add facts merely because they sound plausible.

Do not assume a company launched something if the sources
only describe a possibility.

Do not convert "potential" into "confirmed."

Do not make price, funding, user-count, adoption, launch,
performance or security claims unless supported.

Do not predict financial outcomes as facts.

Do not claim something is live, new, confirmed, official,
guaranteed or already happening unless the research supports it.

If sources conflict, reflect the uncertainty.

Be especially careful with absolute claims.

Do not claim that nobody, no project, no protocol, no company,
or nothing has done something unless the supplied research
explicitly establishes that.

Do not turn absence of evidence into evidence of absence.

The scope of the conclusion must match the scope of the research.

DRAFT REQUIREMENTS

The DRAFT is a short content starting point, not a full article.

Maximum length: {draft_max} characters.

There is NO minimum length.

The priority order is:

1. COMPLETE THOUGHT
2. STRONG IDEA
3. NATURAL WRITING
4. CHARACTER LIMIT

A complete 250-character draft is better than an incomplete
{draft_max}-character draft.

A complete 150-character draft is better than a cut-off
{draft_max}-character draft.

NEVER cut the DRAFT off simply because the character limit
is approaching.

NEVER end the DRAFT with:

- an unfinished sentence
- an unfinished list
- an unfinished argument
- "..."
- a dangling conjunction such as "and", "but", "because",
  "while", "which", "that", "with", or "so"
- a colon introducing information that never follows

If the idea is too large for the character limit, COMPRESS IT.

Remove secondary facts before removing the ending.

Do not try to squeeze every important fact into the DRAFT.

The DRAFT should communicate ONE strong idea clearly.

For /feed:

The DRAFT is an intelligence clue of no more than
350 characters.

It should give the creator a useful starting point that can
be expanded later.

For /create:

The DRAFT is a concise ready-to-develop content starting point
of no more than 410 characters.

For /research:

The DRAFT is a concise researched content starting point
of no more than 410 characters.

The CONTENT ANGLE should carry the deeper context, evidence,
perspective and development direction.

The DRAFT itself does NOT need to contain everything.

If the character limit is approaching, make the idea shorter.

Do NOT sacrifice completion to include another fact.

Before returning the answer, silently check:

- Is the final sentence complete?
- Is the thought complete?
- Does the ending read naturally?
- Is there any unfinished list?
- Is there any trailing conjunction?
- Is there an ellipsis?
- Is the DRAFT within the character limit?

If any answer is NO, rewrite the DRAFT shorter until all
conditions are satisfied.

Do not explain this validation process in the output.

{retry_instruction}

OUTPUT FORMAT

Return ONLY these four sections:

CATEGORY:
<short accurate category>

CONTENT ANGLE:
<professional recommendation for what the creator should
write and what perspective to take>

DRAFT:
<complete ready-to-post or ready-to-develop social-media draft>

SOURCES:
<plain source URLs, one per line>

Do NOT return:

WHAT HAPPENED:
WHY IT MATTERS:
ANALYSIS:
SUMMARY:
EDITORIAL JUDGMENT:
FACT CHECK:
NOTES:

Do not include citation markers inside the DRAFT.

Do not use markdown links in the DRAFT.
"""


def call_writer(
    research,
    request_type="feed",
    retry=False,
):
    prompt = build_prompt(
        research,
        request_type=request_type,
        retry=retry,
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.75,
        max_tokens=700,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto research editor "
                    "and content strategist. "
                    "Be fact-grounded, editorially intelligent, "
                    "adaptive and concise. "
                    "Always complete the requested draft."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    text = response.choices[0].message.content

    if not text:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return text.strip()


def format_output(
    model_text,
    research,
):
    parsed = parse_output(model_text)

    category = parsed["category"]
    content_angle = parsed["content_angle"]
    draft = parsed["draft"]

    if not category:
        category = "Crypto intelligence"

    if not content_angle:
        content_angle = (
            "Identify the strongest evidence-based perspective "
            "from this development and explain why it matters."
        )

    if not draft:
        raise RuntimeError(
            "Groq did not return a usable DRAFT section."
        )

    sources = []

    for result in research.get("results", []):
        url = result.get("url", "").strip()

        if url and url not in sources:
            sources.append(url)

    output = (
        "CATEGORY:\n"
        f"{category}\n\n"
        "CONTENT ANGLE:\n"
        f"{content_angle}\n\n"
        "DRAFT:\n"
        f"{draft}"
    )

    if sources:
        output += "\n\nSOURCES:\n"

        for url in sources:
            output += f"{url}\n"

    return output.strip(), draft


def generate_intelligence(
    research,
    request_type="feed",
):
    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    draft_max = get_draft_max(request_type)

    model_text = call_writer(
        research,
        request_type=request_type,
        retry=False,
    )

    output, draft = format_output(
        model_text,
        research,
    )

    needs_retry = (
        draft_looks_cut_off(draft)
        or len(draft) > draft_max
    )

    if needs_retry:
        logger.warning(
            "Generated draft failed validation. "
            "Length: %d. Maximum: %d.",
            len(draft),
            draft_max,
        )

        model_text = call_writer(
            research,
            request_type=request_type,
            retry=True,
        )

        output, draft = format_output(
            model_text,
            research,
        )

    if draft_looks_cut_off(draft):
        raise RuntimeError(
            "Generated draft appears incomplete."
        )

    if len(draft) > draft_max:
        raise RuntimeError(
            f"Generated draft is too long: "
            f"{len(draft)} characters. "
            f"Maximum allowed: {draft_max}."
        )

    return output


def generate_content(
    request: str,
    research=None,
):
    """
    Generate finished, ready-to-post creator content.

    This is intentionally separate from generate_intelligence().
    /research and /feed continue using the intelligence pipeline.
    /create uses this creator pipeline.
    """

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    request = request.strip()

    if not request:
        raise RuntimeError(
            "Create request cannot be empty."
        )

    profile = load_writer_profile()

    research_text = ""

    if research and research.get("results"):
        research_text = build_research_text(
            research
        )

    prompt = f"""
You are the dedicated crypto/Web3 content creator for this creator brand.

The user has asked you to CREATE CONTENT.

USER REQUEST:
{request}

RESEARCH / CURRENT CONTEXT:
{research_text if research_text else "No external research was supplied."}

WRITER PROFILE

PATTERNS:
{profile["patterns"]}

RULES:
{profile["rules"]}

EXAMPLES:
{profile["examples"]}


YOUR JOB

Understand the user's actual content request before writing.

The user may ask for:

- a GM post
- good morning post
- market observation
- reaction
- opinion
- hot take
- educational post
- explainer
- breaking-news post
- funny crypto post
- meme-style post
- storytelling post
- guide
- thread
- technical explanation
- contrarian take
- community post
- or another crypto/Web3 format.


IMPORTANT: CONTENT TYPE FIRST

The requested format determines the shape of the output.

If the user says:

"GM post"

"Crypto GM post"

"write a GM"

"good morning crypto post"

then create an actual GM post.

Do NOT turn it into a research report.

Do NOT explain what GM means unless that is specifically requested.

Do NOT produce CATEGORY, CONTENT ANGLE, DRAFT, or SOURCES.

The result should feel like something the creator would actually post on crypto Twitter/X that morning.

A GM post can use a current market observation, interesting development, community sentiment, humor, a simple thought, or a timely crypto reference when useful.

It does NOT need to mention news.

Do not force research into a GM post simply because research is available.


CURRENT CONTEXT AND RESEARCH

When the request benefits from current information, use the supplied research.

Use research especially when the user asks for:

- today's market
- current events
- latest news
- reactions
- breaking news
- what is happening
- current protocols/projects
- recent launches
- recent market movements
- current narratives
- recent crypto Twitter discussions

Research is context, not a script.

Extract only information that genuinely improves the requested content.

Never dump research into the post.

Never invent facts.

Never invent personal experiences.

Never claim the creator personally did something unless the user supplied that information.


WRITING STYLE

Write like a real crypto creator.

Use the writer profile as the creator's writing DNA.

Do not mechanically copy the examples.

Do not reuse distinctive phrases from the examples.

Do not make every post sound the same.

Do not force slang.

Do not force lowercase.

Do not force emojis.

Do not force hashtags.

Do not use generic AI motivational language.

Avoid phrases such as:

"the future is here"

"game changer"

"this changes everything"

"the next big thing"

unless the context genuinely calls for them.

The writing should feel natural, specific and intentional.

Short sentences are allowed.

Fragments are allowed when they feel natural to the creator.

Line breaks may be used when they improve the post.

The output should look like a real social post, not an essay.


GM-SPECIFIC BEHAVIOR

When the request is a GM post:

- make it feel current
- make it feel human
- give it a reason to exist
- it can be casual, funny, observational, reflective, market-aware or slightly provocative
- it can reference something happening in crypto when that improves it
- avoid generic "rise and grind" language
- avoid corporate motivational language
- avoid explaining the meaning of GM
- do not make every GM post sound inspirational
- do not use the same GM structure every time

The post should be something people could naturally reply to.


FACTUAL DISCIPLINE

Do not invent:

- prices
- percentages
- dates
- launches
- partnerships
- funding
- user numbers
- token performance
- protocol activity
- quotes
- announcements
- personal experiences

If research contains uncertainty, do not present speculation as fact.

If the request is creative and does not require factual claims, creative writing is allowed.


OUTPUT RULES

Return ONLY the finished content.

Do NOT return:

CATEGORY:
CONTENT ANGLE:
DRAFT:
SOURCES:
ANALYSIS:
SUMMARY:
EXPLANATION:
NOTES:

Do not say:

"Here is your post"

"Here's a draft"

"Based on the research"

"According to the sources"

Do not explain your reasoning.

Do not wrap the post in quotation marks.

Do not use markdown code fences.

Do not include source URLs unless the user explicitly asks for them.

Make the result ready to copy and post immediately.


QUALITY CHECK

Before returning the content, silently check:

1. Did I actually follow the requested content type?
2. If this is a GM request, does it actually feel like a GM post?
3. Is it natural?
4. Does it sound like a human crypto creator?
5. Did I avoid unnecessary research?
6. Did I avoid invented facts?
7. Is the post complete?
8. Did I avoid generic AI language?
9. Did I return ONLY the content?

If any answer is NO, rewrite before returning.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.85,
        max_tokens=700,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto content creator "
                    "and editorial strategist. "
                    "Create natural, human, ready-to-post "
                    "crypto content. "
                    "Follow the requested content format exactly."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    text = response.choices[0].message.content

    if not text:
        raise RuntimeError(
            "Groq returned an empty response."
        )

    return clean_model_text(text).strip()


def generate_ideas(
    request: str,
    research=None,
):
    """
    Generate three dynamic creator ideas from researched material.

    This is intentionally separate from:
    - generate_intelligence()
    - generate_content()

    /ideas is an editorial idea-discovery pipeline.
    It does not generate finished posts.
    """

    if not GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is missing."
        )

    request = request.strip()

    if not request:
        raise RuntimeError(
            "Ideas request cannot be empty."
        )

    if not research or not research.get("results"):
        raise RuntimeError(
            "No useful research was found for this topic."
        )

    profile = load_writer_profile()

    research_text = build_research_text(
        research
    )

    prompt = f"""
You are the idea strategist for a serious crypto/Web3 content creator.

The creator has given you a SUBJECT and wants ideas for content.

SUBJECT:
{request}

Your job is NOT to summarize the research.

Your job is to discover the most interesting CONTENT OPPORTUNITIES
hidden inside the research.

Think like an experienced human crypto creator, editor, researcher
and storyteller.

The creator covers areas such as:

- crypto
- blockchain
- DeFi
- stablecoins
- payments
- AI agents
- agentic economies
- protocols
- onchain activity
- hacks and exploits
- infrastructure
- users
- builders
- crypto culture
- narratives
- market behavior
- products
- governance
- technical developments
- unusual events
- memes and internet culture

The subject can be anything from:

- a protocol
- a company
- a technical concept
- an incident
- a hack
- a product
- a trend
- a narrative
- a quote
- a meme
- a cultural phrase
- an onchain development
- an industry debate
- a broad theme

The request may also be creative.

Examples:

"/ideas on Base"

"/ideas on Arc agentic economy"

"/ideas on the Plum hack"

"/ideas on Uniswap"

"/ideas on stablecoins"

"/ideas on 'we are so back'"

"/ideas on 'to the moon'"

"/ideas on comic art about 'we are so back'"

Do not assume every request needs a conventional news or educational
post.

The subject determines the creative territory.

--------------------------------------------------
RESEARCH
--------------------------------------------------

The following research was collected specifically for this request.

{research_text}

First understand what the research actually establishes.

Identify:

- important developments
- surprising details
- unusual facts
- contradictions
- unanswered questions
- overlooked implications
- second-order effects
- human consequences
- user consequences
- builder consequences
- economic implications
- technical implications
- behavioral patterns
- cultural significance
- useful comparisons
- interesting tensions
- things people may be misunderstanding
- things people may be overlooking
- opportunities for explanation
- opportunities for debate
- opportunities for storytelling
- opportunities for original observation

Do not assume every finding is content-worthy.

--------------------------------------------------
EDITORIAL DISCIPLINE
--------------------------------------------------

Separate FACT from ANGLE.

FACT means something directly supported by the supplied research.

ANGLE means a question, interpretation, explanation, comparison,
thesis, or creative direction that the creator could explore.

Creative interpretation is encouraged.

Unsupported factual claims are not.

Never turn an assumption into a fact simply because it makes the
idea more dramatic.

Do NOT invent:

- hacks
- bugs
- failures
- manipulation
- cover-ups
- motives
- conspiracies
- hidden strategies
- deliberate actions
- financial figures
- technical problems
- controversies
- partnerships
- launches
- adoption numbers
- performance claims
- security conclusions

If something is uncertain, frame it as:

- a question worth investigating
- a possibility
- an interpretation
- an unresolved tension
- something the creator could examine
- something that needs verification

Do not present it as established reality.

For example:

BAD:
"The protocol is hiding its real numbers."

GOOD:
"The protocol's public metrics raise a question: which numbers
actually matter for understanding what is happening?"

BAD:
"This is a deliberate shift away from decentralization."

GOOD:
"The project's growing institutional focus creates an interesting
question about how its original positioning may evolve."

BAD:
"This bug proves the system is broken."

GOOD:
"A strange data point is worth investigating before drawing a
conclusion about what caused it."

A strong idea can absolutely be provocative.

But the provocation must come from:

- evidence
- a real tension
- an interesting question
- a defensible interpretation
- an overlooked implication
- a meaningful comparison
- or a genuine disagreement

Never manufacture controversy simply to make an idea sound
interesting.

Never manufacture a mystery from an unexplained detail.

Never treat missing information as proof that something is being
hidden.

When evidence is ambiguous, curiosity is better than certainty.

--------------------------------------------------
CREATIVE THINKING
--------------------------------------------------

You have a very large creative toolbox.

Possible approaches include, but are NOT limited to:

NEWS
- what actually happened
- what changed
- what matters
- overlooked detail
- timeline
- reaction
- what happens next

EXPLAINING
- explain the confusing part
- explain why it matters
- explain how it works
- beginner explanation
- technical explanation
- myth vs reality
- misconception
- simple analogy

ANALYSIS
- data story
- unusual pattern
- comparison
- contradiction
- incentive analysis
- second-order effect
- downstream consequence
- business model
- protocol behavior
- user behavior
- capital behavior
- infrastructure implication

OPINION
- contrarian thesis
- unpopular observation
- challenge the dominant narrative
- "everyone is looking at X, but..."
- skeptical take
- strong thesis
- uncomfortable question
- debate starter
- what people are getting wrong

STORYTELLING
- follow the money
- follow the user
- follow the transaction
- follow the exploit
- timeline
- cause and effect
- before vs after
- day in the life
- a small event revealing a bigger trend
- unexpected connection
- case study

PRACTICAL
- guide
- checklist
- how-to
- what users should know
- what builders should know
- what to watch
- mistakes to avoid
- questions to ask
- practical implications

COMPARISON
- X vs Y
- old system vs new system
- traditional finance vs crypto
- protocol A vs protocol B
- expectation vs reality
- narrative vs data

CULTURE
- crypto behavior
- community psychology
- narrative cycles
- meme interpretation
- irony
- FOMO
- social dynamics
- recurring crypto habits
- why people behave this way

CREATIVE
- visual concept
- text comic
- metaphor
- analogy
- fictional scenario
- conversation
- absurd scenario
- narrative experiment
- meme concept
- cultural observation

FUTURE / SECOND ORDER
- what this enables
- what comes after
- who benefits
- who gets disrupted
- what new behavior becomes possible
- what infrastructure becomes necessary
- what nobody is discussing yet

These are examples, NOT categories that must appear in the output.

You must decide which approaches are actually appropriate.

--------------------------------------------------
IMPORTANT: THINK LIKE A CREATOR
--------------------------------------------------

Do not simply convert every source into an idea.

Do not produce:

"Explain what Arc is."

"Explain what Base is."

"Write about the hack."

"Discuss why this is important."

Those are topics, not strong content ideas.

A strong idea contains a perspective.

For example:

WEAK:
"Write about AI agents using stablecoins."

STRONG:
"AI agents may need their own financial infrastructure
because autonomous software cannot depend on humans to approve
every transaction."

The second gives the creator something to say.

Another example:

WEAK:
"Write about the Plum hack."

STRONG:
"The interesting part of the Plum hack may not be the amount
stolen, but the assumption that allowed the system to be exploited."

Again, the creator has a thesis.

The strong examples above are examples of STRUCTURE, not permission
to invent facts about a real event.

Only use a thesis like this when the supplied research supports
the underlying factual foundation.

--------------------------------------------------
DIVERSITY
--------------------------------------------------

Return exactly THREE ideas.

The three ideas must be meaningfully different.

Do not give three versions of the same thesis.

For example, do NOT return:

1. Arc enables AI agents.
2. Arc enables autonomous agents.
3. Arc enables agent payments.

Those are essentially the same idea.

Instead, deliberately search for different dimensions when the
research supports them.

One might be technical.

Another might be behavioral.

Another might be economic.

Or one might be a strong opinion, another a practical explainer,
and another a cultural observation.

But do not force diversity if the evidence does not support it.

Quality is more important than artificial variety.

If only one or two genuinely strong directions exist, do not invent
weak evidence merely to create artificial variety.

You must still return exactly three ideas, but the third may be a
more exploratory or question-driven direction rather than a false
claim.

--------------------------------------------------
IDEA QUALITY
--------------------------------------------------

Each idea must answer:

1. What is the creator actually talking about?
2. What is the perspective?
3. Why is this interesting?
4. What makes it different from the other ideas?
5. What evidence supports it?

The idea should give the creator enough direction to develop
a strong post, thread, breakdown, guide, story or other format.

Do not write the finished post.

Do not turn every idea into a hook.

Do not make every idea sound like a tweet.

These are CREATOR DIRECTIONS.

--------------------------------------------------
WRITER PROFILE
--------------------------------------------------

Use the writer profile to understand the creator's taste,
interests, writing DNA and preferred way of thinking.

Do NOT copy sentences.

Do NOT imitate examples mechanically.

The profile influences the quality and character of the ideas,
not the factual research.

PATTERNS:
{profile["patterns"]}

RULES:
{profile["rules"]}

EXAMPLES:
{profile["examples"]}

--------------------------------------------------
SOURCE DISCIPLINE
--------------------------------------------------

Every idea must be grounded in the supplied research.

Attach the 1 or 2 sources that most directly support that idea.

Do not attach irrelevant sources merely because they appeared
in the research.

Do not invent URLs.

Use ONLY URLs supplied in the research.

A source can support an important factual foundation even when
the creative interpretation itself is the creator's analysis.

Clearly separate evidence from interpretation.

Never turn speculation into fact.

If the research is weak, do not manufacture a strong claim.

If an idea is exploratory, make the exploratory nature clear.

--------------------------------------------------
NO REPETITION
--------------------------------------------------

Avoid generic AI phrases such as:

"this changes everything"

"game changer"

"the future is here"

"mass adoption"

"revolutionary"

"next big thing"

unless the research genuinely requires that framing.

Do not manufacture controversy.

Do not manufacture a contrarian angle.

Do not manufacture bullishness.

Do not manufacture bearishness.

Do not force a market angle when the subject is cultural.

Do not force a technical angle when the subject is social.

Do not force a comic idea when the request does not call for one.

--------------------------------------------------
OUTPUT
--------------------------------------------------

Return ONLY the following structure:

IDEA 1:
TITLE:
<short memorable title>

ANGLE:
<the actual perspective the creator could explore>

WHY IT'S INTERESTING:
<why this is worth creating content about>

SOURCES:
<source URL>
<optional second source URL>

IDEA 2:
TITLE:
<short memorable title>

ANGLE:
<the actual perspective the creator could explore>

WHY IT'S INTERESTING:
<why this is worth creating content about>

SOURCES:
<source URL>
<optional second source URL>

IDEA 3:
TITLE:
<short memorable title>

ANGLE:
<the actual perspective the creator could explore>

WHY IT'S INTERESTING:
<why this is worth creating content about>

SOURCES:
<source URL>
<optional second source URL>

Do not include:

SUMMARY:
ANALYSIS:
DRAFT:
CONTENT:
CONCLUSION:
NOTES:

Do not write a finished post.

Do not explain your reasoning.

Do not mention this prompt.

--------------------------------------------------
FINAL QUALITY CHECK
--------------------------------------------------

Before returning the answer, silently verify:

- Exactly 3 ideas?
- Are they genuinely different?
- Is each one a real perspective rather than a topic?
- Does each idea come from the research?
- Are the sources relevant?
- Are all URLs from the supplied research?
- Did I avoid invented facts?
- Did I avoid turning speculation into fact?
- Did I avoid inventing controversy?
- Did I avoid treating unexplained information as proof?
- Did I avoid generic AI content?
- Did I avoid forcing a content type?
- Could a serious creator actually build content from each?

If any answer is NO, improve the ideas before returning them.
"""

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.9,
        max_tokens=1200,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior crypto creator strategist. "
                    "Think like a human editorial director. "
                    "Find original, evidence-grounded content "
                    "opportunities rather than summarizing research. "
                    "Be creative without inventing facts or "
                    "manufacturing controversy."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    text = response.choices[0].message.content

    if not text:
        raise RuntimeError(
            "Groq returned an empty ideas response."
        )

    return clean_model_text(
        text
    ).strip()