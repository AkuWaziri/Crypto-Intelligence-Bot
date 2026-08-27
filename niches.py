import json
import os

NICHES_FILE = "niches.json"

DEFAULT_NICHES = [
    "AI tools",
    "AI agents",
    "AI infrastructure",
    "AI + blockchain",
    "crypto payments",
    "airdrops",
    "rewards",
    "campaigns",
    "claim rewards",
    "ending soon",
    "crypto opportunities",
    "new crypto protocols",
    "crypto products",
    "on-chain activity",
    "wallet movements",
    "smart money",
    "crypto security",
    "smart contracts",
    "contract vulnerabilities",
    "crypto exploits",
    "protocol updates",
    "new crypto launches",
    "emerging crypto narratives",
    "crypto infrastructure",
]


def load_custom_niches():
    if not os.path.exists(NICHES_FILE):
        return []

    try:
        with open(NICHES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

    except Exception:
        pass

    return []


def save_custom_niches(niches):
    with open(
        NICHES_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            niches,
            file,
            indent=2,
            ensure_ascii=False
        )


custom_niches = load_custom_niches()


def get_niches():
    return DEFAULT_NICHES + custom_niches


def add_niche(niche: str):
    niche = niche.strip()

    if not niche:
        return False

    existing = [
        item.lower()
        for item in get_niches()
    ]

    if niche.lower() in existing:
        return False

    custom_niches.append(niche)

    save_custom_niches(custom_niches)

    return True