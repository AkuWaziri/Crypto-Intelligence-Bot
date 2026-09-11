import asyncio
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from research import search_web
from writer import generate_intelligence
from niches import get_niches
from config import RESEARCH_INTERVAL_MINUTES

logger = logging.getLogger(__name__)


# These are discovery lanes, not a rotation. Every scheduled sweep searches
# across the crypto landscape so the strongest current developments can win.
TREND_SEARCHES = [
    "crypto breaking current news latest major developments adoption institutional crypto",
    "crypto emerging narratives latest DeFi stablecoins payments tokenization RWA DePIN staking restaking",
    "crypto AI agents AI blockchain infrastructure wallets developer activity interoperability cross-chain L2 L3",
    "crypto on-chain activity whale wallet user growth transactions volume liquidity trading ecosystem activity",
    "crypto exploits hacks vulnerabilities security incidents audits protocol failures privacy security",
    "crypto funding investments partnerships integrations launches products protocols token launches mainnet testnet",
    "crypto governance regulation policy approvals institutional adoption legal developments DAOs ecosystem milestones",
    "crypto airdrops rewards campaigns quests incentives opportunities new ecosystems tokenomics unlocks NFTs consumer crypto",
    "crypto Bitcoin Ethereum Solana ecosystem developments new protocols experiments social consumer crypto exchanges wallets",
    "crypto latest adoption users developers revenue fees stablecoin payments infrastructure major ecosystem developments",
]

HISTORY_FILE = Path("feed_history.json")
HISTORY_DAYS = 14
MAX_HISTORY_ITEMS = 500
MAX_CANDIDATES_PER_SEARCH = 2
MAX_FEED_ITEMS = 3

GENERIC_TERMS = {
    "crypto", "cryptocurrency", "blockchain", "web3", "latest", "news",
    "today", "update", "updates", "breaking", "report", "reports", "new",
    "major", "the", "and", "for", "with", "from", "this", "that",
}


def get_search_queries(niche):
    return [
        f"{niche} crypto Web3 latest",
        f"{niche} blockchain latest",
    ]


def choose_research_topics():
    """Compatibility helper for older callers."""
    niches = get_niches()
    return niches[:1] if niches else []


def _utc_now():
    return datetime.now(timezone.utc)


def _normalize_text(text):
    text = str(text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tokens(text):
    return {
        token
        for token in _normalize_text(text).split()
        if len(token) >= 3 and token not in GENERIC_TERMS
    }


def _similarity(left, right):
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _story_fingerprint(result):
    title = _normalize_text(result.get("title", ""))
    content = _normalize_text(result.get("content", ""))[:900]
    return hashlib.sha256(
        f"{title}|{content}".encode("utf-8")
    ).hexdigest()


def load_feed_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(
            HISTORY_FILE.read_text(encoding="utf-8")
        )
        return data if isinstance(data, list) else []
    except Exception:
        logger.exception("Could not read feed history; starting clean.")
        return []


def save_feed_history(history):
    HISTORY_FILE.write_text(
        json.dumps(
            history[-MAX_HISTORY_ITEMS:],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def prune_feed_history(history):
    cutoff = _utc_now() - timedelta(days=HISTORY_DAYS)
    kept = []

    for item in history:
        try:
            fed_at = datetime.fromisoformat(item.get("fed_at", ""))
        except Exception:
            continue
        if fed_at >= cutoff:
            kept.append(item)

    return kept[-MAX_HISTORY_ITEMS:]


def is_previously_fed(result, history):
    fingerprint = _story_fingerprint(result)
    title = result.get("title", "")
    content = result.get("content", "")

    for old in history:
        if old.get("fingerprint") == fingerprint:
            return True

        title_similarity = _similarity(title, old.get("title", ""))
        content_similarity = _similarity(
            content,
            old.get("content", ""),
        )

        # Same story with a rewritten headline/article.
        if title_similarity >= 0.70 and content_similarity >= 0.45:
            return True

        # Same headline/topic with substantial evidence overlap.
        if title_similarity >= 0.55 and content_similarity >= 0.65:
            return True

    return False


def _trend_score(result):
    title = str(result.get("title", "")).lower()
    content = str(result.get("content", "")).lower()
    score = float(result.get("score", 0) or 0)

    freshness_terms = [
        "breaking", "today", "just", "hours", "now", "latest",
        "announced", "announcement", "launch", "launched", "released",
        "exploit", "hack", "funding", "integrated", "integration",
        "governance", "upgrade", "mainnet", "testnet", "airdrop",
        "claim", "partnership", "regulation", "approval", "adoption",
        "users", "user growth", "developers", "developer activity",
    ]

    signal_terms = [
        "billion", "million", "volume", "users", "transactions", "wallets",
        "funding", "revenue", "fees", "liquidity", "supply", "adoption",
        "exploit", "hack", "vulnerability", "launch", "mainnet", "airdrop",
        "rewards", "campaign", "partnership", "integration", "institutional",
    ]

    for term in freshness_terms:
        if term in title:
            score += 5
        elif term in content:
            score += 1

    for term in signal_terms:
        if term in title:
            score += 3

    if len(content) >= 700:
        score += 2

    return score


def rank_trending_candidates(results, history):
    candidates = []

    for result in results:
        if not result.get("title") or not result.get("url"):
            continue
        if is_previously_fed(result, history):
            continue

        candidate = dict(result)
        candidate["trend_score"] = _trend_score(candidate)
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: item.get("trend_score", 0),
        reverse=True,
    )
    return candidates


async def research_niche(niche):
    """Compatibility path for existing non-GitHub callers."""
    import random

    query = random.choice(get_search_queries(niche))
    research = await asyncio.to_thread(search_web, query)

    if not research.get("results"):
        return None

    research["niche"] = niche
    return research


async def discover_trending_research():
    """Run a broad current-market sweep across the crypto ecosystem."""
    combined = []

    for query in TREND_SEARCHES:
        try:
            research = await asyncio.to_thread(
                search_web,
                query,
                MAX_CANDIDATES_PER_SEARCH,
            )
            combined.extend(research.get("results", []))
        except Exception:
            logger.exception(
                "Trend discovery failed for query: %s",
                query,
            )

    unique = []
    seen = set()

    for result in combined:
        key = (
            result.get("url", "").strip().lower(),
            _normalize_text(result.get("title", "")),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(result)

    return unique


async def generate_feed():
    history = prune_feed_history(load_feed_history())
    candidates = await discover_trending_research()
    ranked = rank_trending_candidates(candidates, history)

    reports = []

    for candidate in ranked[:MAX_FEED_ITEMS]:
        try:
            research = {
                "query": "current crypto trend",
                "answer": "",
                "results": [candidate],
            }

            intelligence = await asyncio.to_thread(
                generate_intelligence,
                research,
                "current crypto trend feed",
            )

            if intelligence:
                reports.append({
                    "report": intelligence,
                    "candidate": candidate,
                })
        except Exception:
            logger.exception(
                "Trend writing failed for: %s",
                candidate.get("title", "unknown"),
            )

    return reports, history


def record_fed_items(history, reports):
    now = _utc_now().isoformat()

    for item in reports:
        candidate = item.get("candidate", {})
        history.append({
            "fingerprint": _story_fingerprint(candidate),
            "title": candidate.get("title", ""),
            "content": candidate.get("content", "")[:1200],
            "url": candidate.get("url", ""),
            "fed_at": now,
        })

    save_feed_history(history)


async def scheduler_loop(send_message):
    logger.info(
        "Research scheduler started. Interval: %s minutes",
        RESEARCH_INTERVAL_MINUTES,
    )

    await asyncio.sleep(10)

    while True:
        try:
            reports, history = await generate_feed()

            if reports:
                await send_message(
                    "🧠 <b>CRYPTO INTELLIGENCE FEED</b>\n\n"
                    "Current developments worth looking at:"
                )

                for item in reports:
                    report = item["report"]
                    if len(report) > 3900:
                        report = report[:3900] + "\n\n[truncated]"
                    await send_message(report)

                record_fed_items(history, reports)
            else:
                logger.info(
                    "No new high-signal crypto developments found this cycle."
                )

        except Exception:
            logger.exception("Scheduled feed failed.")

        await asyncio.sleep(RESEARCH_INTERVAL_MINUTES * 60)
