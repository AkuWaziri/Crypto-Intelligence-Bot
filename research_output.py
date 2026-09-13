import re

MAX_RESEARCH_CHARACTERS = 700

SECTION_LIMITS = {
    "signal": 45,
    "why": 55,
    "angles": 300,
    "rabbit": 180,
    "miss": 90,
}


def _extract(text, headings):
    for heading in headings:
        pattern = (
            rf"{re.escape(heading)}\s*:\s*"
            rf"(.*?)(?=\n[A-Z][A-Z /_-]*\s*:\s*|\Z)"
        )
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()
    return ""


def _shorten(text, limit):
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= limit:
        return text

    clipped = text[:limit].rstrip(" ,;:-")
    cut = clipped.rfind(" ")
    if cut >= max(20, limit - 35):
        clipped = clipped[:cut].rstrip(" ,;:-")

    return clipped


def _number_angles(text):
    if not text:
        return ""

    matches = re.findall(
        r"(?:^|\s)(\d+)\.\s*(.*?)(?=\s+\d+\.\s*|$)",
        text,
    )

    if matches:
        items = [item.strip() for _, item in matches[:2] if item.strip()]
    else:
        parts = re.split(r"\s*(?:;|\|)\s*", text)
        items = [part.strip() for part in parts[:2] if part.strip()]

    if not items:
        return ""

    return "1. " + items[0] + (" 2. " + items[1] if len(items) > 1 else "")


def _number_rabbit(text):
    if not text:
        return ""

    match = re.search(
        r"(?:^|\s)1\.\s*(.*?)(?=\s+2\.\s*|$)",
        text,
    )

    if match:
        return "1. " + match.group(1).strip()

    return "1. " + text.strip()


def _fallback_angles(raw, why, miss):
    mechanism = _extract(raw, ["THE MECHANISM", "MECHANISM"])
    changed = _extract(raw, ["WHAT CHANGED", "THE NUMBERS"])
    incentive = _extract(raw, ["INCENTIVE"])

    candidates = []

    if mechanism:
        candidates.append(
            "Explain the mechanism behind the event: " + mechanism
        )

    if changed:
        candidates.append(
            "Explore what changed and why it matters: " + changed
        )

    if incentive:
        candidates.append(
            "Break down the incentive driving the behavior: " + incentive
        )

    if why:
        candidates.append(
            "Challenge the obvious narrative: " + why
        )

    if miss:
        candidates.append(
            "Investigate the overlooked detail: " + miss
        )

    if not candidates:
        return ""

    return "  ".join(
        f"{index}. {item}"
        for index, item in enumerate(candidates[:2], start=1)
    )


def _fallback_rabbit(raw, why, miss):
    unclear = _extract(raw, ["WHAT IS UNCLEAR"])
    mechanism = _extract(raw, ["THE MECHANISM", "MECHANISM"])
    wrong = _extract(raw, ["WHAT PEOPLE MAY BE GETTING WRONG"])

    candidates = []

    if unclear:
        candidates.append(
            "What is still unclear here, and what evidence would confirm it? "
            + unclear
        )

    if mechanism:
        candidates.append(
            "What deeper mechanism could explain this? " + mechanism
        )

    if wrong:
        candidates.append(
            "What is the market misunderstanding? " + wrong
        )

    if miss:
        candidates.append(
            "What does the overlooked detail lead to? " + miss
        )

    if why:
        candidates.append(
            "What happens if this narrative is wrong? " + why
        )

    if not candidates:
        return ""

    return "  ".join(
        f"{index}. {item}"
        for index, item in enumerate(candidates[:2], start=1)
    )


def format_research_output(text):
    """Force manual /research output into one fixed five-section format."""
    raw = str(text or "").strip()
    if not raw:
        return ""

    signal = _extract(
        raw,
        [
            "SIGNAL",
            "WHAT ACTUALLY HAPPENED",
        ],
    )
    why = _extract(
        raw,
        [
            "WHY IT MATTERS",
            "WHY",
            "WHY IT IS INTERESTING",
        ],
    )
    angles = _extract(
        raw,
        [
            "CONTENT ANGLE",
            "CONTENT ANGLES",
            "CONTENT OPPORTUNITIES",
            "OPPORTUNITIES",
        ],
    )
    rabbit = _extract(
        raw,
        [
            "RABBIT HOLE",
            "RABBIT HOLES",
        ],
    )
    miss = _extract(
        raw,
        [
            "WHAT DETAILS PEOPLE MAY MISS",
            "DETAILS PEOPLE MAY MISS",
            "WHAT PEOPLE MAY MISS",
            "THE DETAIL PEOPLE MAY MISS",
        ],
    )

    if not angles:
        angles = _fallback_angles(raw, why, miss)

    if not rabbit:
        rabbit = _fallback_rabbit(raw, why, miss)

    signal = _shorten(signal, SECTION_LIMITS["signal"])
    why = _shorten(why, SECTION_LIMITS["why"])
    angles = _shorten(
        _number_angles(angles),
        SECTION_LIMITS["angles"],
    )
    rabbit = _shorten(
        _number_rabbit(rabbit),
        SECTION_LIMITS["rabbit"],
    )
    miss = _shorten(miss, SECTION_LIMITS["miss"])

    def build_output():
        return (
            f"SIGNAL: {signal}\n"
            f"WHY IT MATTERS: {why}\n"
            f"CONTENT ANGLE: {angles}\n"
            f"RABBIT HOLE: {rabbit}\n"
            f"WHAT DETAILS PEOPLE MAY MISS: {miss}"
        ).strip()

    output = build_output()

    # Hard 700-character guard. Trim the larger creative sections first.
    if len(output) <= MAX_RESEARCH_CHARACTERS:
        return output

    overflow = len(output) - MAX_RESEARCH_CHARACTERS
    rabbit = _shorten(
        rabbit,
        max(30, len(rabbit) - overflow),
    )
    output = build_output()

    if len(output) > MAX_RESEARCH_CHARACTERS:
        overflow = len(output) - MAX_RESEARCH_CHARACTERS
        angles = _shorten(
            angles,
            max(40, len(angles) - overflow),
        )
        output = build_output()

    if len(output) > MAX_RESEARCH_CHARACTERS:
        overflow = len(output) - MAX_RESEARCH_CHARACTERS
        miss = _shorten(
            miss,
            max(30, len(miss) - overflow),
        )
        output = build_output()

    return output[:MAX_RESEARCH_CHARACTERS].rstrip(" ,;:-")
