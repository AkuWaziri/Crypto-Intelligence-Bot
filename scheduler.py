import asyncio
import logging
import random

from research import search_web
from writer import generate_intelligence
from niches import get_niches
from config import RESEARCH_INTERVAL_MINUTES

logger = logging.getLogger(__name__)


NICHE_SEARCHES = {
    "AI tools": [
        "new AI tools crypto Web3 latest",
        "new AI developer tools blockchain latest",
    ],
    "AI agents": [
        "new AI agents crypto Web3 latest",
        "AI agent crypto protocol launch latest",
    ],
    "AI infrastructure": [
        "AI infrastructure crypto Web3 latest",
        "new blockchain AI infrastructure latest",
    ],
    "AI + blockchain": [
        "AI blockchain projects launches latest",
        "AI crypto infrastructure developments latest",
    ],
    "crypto payments": [
        "crypto payments stablecoin payments latest",
        "new crypto payment infrastructure latest",
    ],
    "airdrops": [
        "new crypto airdrop announced latest",
        "Web3 airdrop eligibility claim latest",
    ],
    "rewards": [
        "crypto rewards campaign latest",
        "Web3 protocol rewards program latest",
    ],
    "campaigns": [
        "crypto protocol campaign rewards latest",
        "Web3 campaign points rewards latest",
    ],
    "claim rewards": [
        "crypto rewards claim live latest",
        "Web3 token claim rewards latest",
    ],
    "ending soon": [
        "crypto airdrop claim deadline ending soon",
        "Web3 campaign ending soon rewards",
        "crypto rewards deadline approaching",
    ],
    "crypto opportunities": [
        "new crypto opportunities latest",
        "new Web3 opportunities rewards campaigns latest",
    ],
    "new crypto protocols": [
        "new crypto protocol launched latest",
        "new Web3 protocol launch latest",
    ],
    "crypto products": [
        "new crypto product launched latest",
        "new Web3 tools products latest",
    ],
    "on-chain activity": [
        "unusual crypto on-chain activity latest",
        "interesting on-chain activity crypto latest",
    ],
    "wallet movements": [
        "large crypto wallet movement latest",
        "whale wallet activity BTC ETH latest",
    ],
    "smart money": [
        "crypto smart money activity latest",
        "on-chain smart money wallet movements latest",
    ],
    "crypto security": [
        "crypto security vulnerability latest",
        "Web3 security incident latest",
    ],
    "smart contracts": [
        "smart contract vulnerability crypto latest",
        "Web3 contract security issue latest",
    ],
    "contract vulnerabilities": [
        "crypto smart contract vulnerability latest",
        "Web3 contract exploit vulnerability latest",
    ],
    "crypto exploits": [
        "crypto exploit Web3 latest",
        "blockchain protocol exploit latest",
    ],
    "protocol updates": [
        "crypto protocol update latest",
        "Web3 protocol announcement latest",
    ],
    "new crypto launches": [
        "new crypto project launch latest",
        "new Web3 launch latest",
    ],
    "emerging crypto narratives": [
        "emerging crypto narrative latest",
        "new crypto trend narrative latest",
    ],
    "crypto infrastructure": [
        "new crypto infrastructure project latest",
        "blockchain infrastructure developments latest",
    ],
}


def get_search_queries(niche):
    """
    Return targeted crypto searches for a niche.
    """

    if niche in NICHE_SEARCHES:
        return NICHE_SEARCHES[niche]

    # Custom niches still receive crypto context.
    return [
        f"{niche} crypto Web3 latest",
        f"{niche} blockchain latest",
    ]


def choose_research_topics():
    niches = get_niches()

    if not niches:
        return []

    count = min(4, len(niches))

    return random.sample(niches, count)


async def research_niche(niche):
    """
    Research one niche using targeted queries.
    """

    queries = get_search_queries(niche)

    # Pick one query per niche this cycle.
    query = random.choice(queries)

    logger.info(
        "Researching niche '%s' with query '%s'",
        niche,
        query,
    )

    research = await asyncio.to_thread(
        search_web,
        query,
    )

    if not research.get("results"):
        return None

    # Tell the writer which niche triggered the research.
    research["niche"] = niche

    return research


async def generate_feed():
    topics = choose_research_topics()

    reports = []

    for niche in topics:
        try:
            research = await research_niche(niche)

            if not research:
                continue

            intelligence = await asyncio.to_thread(
                generate_intelligence,
                research,
                "scheduled feed",
            )

            if intelligence:
                reports.append(intelligence)

        except Exception:
            logger.exception(
                "Research failed for niche: %s",
                niche,
            )

    return reports


async def scheduler_loop(send_message):
    logger.info(
        "Research scheduler started. Interval: %s minutes",
        RESEARCH_INTERVAL_MINUTES,
    )

    await asyncio.sleep(10)

    while True:
        try:
            reports = await generate_feed()

            if reports:
                await send_message(
                    "🧠 <b>CRYPTO INTELLIGENCE FEED</b>\n\n"
                    "Fresh research worth looking at:"
                )

                for report in reports:

                    if len(report) > 3900:
                        report = report[:3900] + "\n\n[truncated]"

                    await send_message(report)

            else:
                logger.info(
                    "No useful research found this cycle."
                )

        except Exception:
            logger.exception(
                "Scheduled feed failed."
            )

        await asyncio.sleep(
            RESEARCH_INTERVAL_MINUTES * 60
        )