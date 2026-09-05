import logging
import re
import requests
from urllib.parse import urlparse

from config import EXA_API_KEY, MAX_RESEARCH_RESULTS

logger = logging.getLogger(__name__)

EXA_URL = "https://api.exa.ai/search"


# ============================================================
# FILTERS
# ============================================================

LOW_VALUE_TERMS = [
    "casino",
    "gambling",
    "horoscope",
    "celebrity gossip",
]


CRYPTO_TERMS = [
    "crypto",
    "cryptocurrency",
    "blockchain",
    "web3",
    "defi",
    "token",
    "airdrop",
    "stablecoin",
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "solana",
    "base",
    "arbitrum",
    "optimism",
    "polygon",
    "avalanche",
    "bnb",
    "wallet",
    "on-chain",
    "onchain",
    "smart contract",
    "protocol",
    "layer 2",
    "l2",
    "dao",
    "usdc",
    "usdt",
    "dex",
    "staking",
    "yield",
    "liquidity",
    "bridge",
    "perpetual",
    "trading",
    "exchange",
    "ai agent",
    "ai agents",
    "agentic",
]


# ============================================================
# SOURCE QUALITY
# ============================================================

HIGH_QUALITY_DOMAINS = {
    "github.com",
    "ethereum.org",
    "solana.com",
    "base.org",
    "arbitrum.io",
    "optimism.io",
    "circle.com",
    "visa.com",
    "mastercard.com",
    "stripe.com",
    "paypal.com",
    "a16zcrypto.com",
    "coindesk.com",
    "theblock.co",
    "blockworks.co",
    "decrypt.co",
    "bankless.com",
    "messari.io",
    "defillama.com",
    "dune.com",
    "l2beat.com",
    "coinbase.com",
    "binance.com",
    "kraken.com",
    "uniswap.org",
    "chainalysis.com",
    "consensys.io",
    "fireblocks.com",
    "paradigm.xyz",
    "variant.fund",
}


MEDIUM_QUALITY_DOMAINS = {
    "mirror.xyz",
    "paragraph.xyz",
    "medium.com",
    "substack.com",
    "cointelegraph.com",
    "cryptoslate.com",
    "beincrypto.com",
    "thedefiant.io",
    "decrypt.co",
}


# ============================================================
# HELPERS
# ============================================================

def domain_from_url(url):
    try:
        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "")
        return domain
    except Exception:
        return ""


def clean_text(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def normalize_query_text(text):
    text = str(text or "").strip().lower()

    text = re.sub(r"\s+", " ", text)

    return text


def is_crypto_relevant(result):
    title = str(result.get("title", ""))

    content = str(result.get("content", ""))

    text = f"{title} {content}".lower()

    for term in LOW_VALUE_TERMS:
        if term in text:
            return False

    for term in CRYPTO_TERMS:
        if term.lower() in text:
            return True

    # Some targeted queries can return useful material that
    # does not explicitly repeat generic crypto terminology.
    return True


# ============================================================
# QUERY EXPANSION
# ============================================================

def build_research_queries(query):
    """
    Turn one user question into a structured research sweep.

    The objective is not simply to find more articles.

    Each query attacks the subject from a different evidence
    angle so the final intelligence layer can discover:
        - what happened
        - how it works
        - what changed
        - who is involved
        - what the numbers say
        - what people may be missing
        - what is disputed
        - where the deeper story may be
    """

    base = str(query).strip()

    if not base:
        return []

    queries = [
        (
            base,
            "general",
        ),
        (
            f"{base} latest news developments update",
            "news",
        ),
        (
            f"{base} official announcement documentation",
            "official",
        ),
        (
            f"{base} how it works technical mechanism architecture",
            "technical",
        ),
        (
            f"{base} users adoption usage activity metrics data",
            "data",
        ),
        (
            f"{base} onchain transactions wallets volume flows",
            "onchain",
        ),
        (
            f"{base} integrations partners ecosystem funding",
            "ecosystem",
        ),
        (
            f"{base} incentives tokenomics allocation economics",
            "tokenomics",
        ),
        (
            f"{base} criticism controversy risks problems security",
            "criticism",
        ),
        (
            f"{base} analysis explained implications why it matters",
            "analysis",
        ),
    ]

    return queries


# ============================================================
# NORMALIZE
# ============================================================

def normalize_result(item, research_angle="general"):
    title = clean_text(
        item.get("title", "")
    )

    url = str(
        item.get("url", "")
    ).strip()

    content = clean_text(
        item.get("text", "")
    )

    if len(content) > 1800:
        content = content[:1800].rstrip()

    domain = domain_from_url(url)

    return {
        "title": title,
        "url": url,
        "content": content,
        "domain": domain,
        "research_angle": research_angle,
    }


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_results(results):
    unique = []

    seen_urls = set()
    seen_titles = set()
    seen_content = set()

    for result in results:
        url = (
            result.get("url", "")
            .strip()
            .lower()
        )

        title = normalize_query_text(
            result.get("title", "")
        )

        content = normalize_query_text(
            result.get("content", "")
        )

        content_key = content[:350]

        if url and url in seen_urls:
            continue

        if title and title in seen_titles:
            continue

        if content_key and content_key in seen_content:
            continue

        if url:
            seen_urls.add(url)

        if title:
            seen_titles.add(title)

        if content_key:
            seen_content.add(content_key)

        unique.append(result)

    return unique


# ============================================================
# RESULT SCORING
# ============================================================

def score_result(result, original_query):
    title = str(
        result.get("title", "")
    ).lower()

    content = str(
        result.get("content", "")
    ).lower()

    domain = str(
        result.get("domain", "")
    ).lower()

    angle = str(
        result.get("research_angle", "")
    ).lower()

    query_terms = [
        term.lower()
        for term in re.findall(
            r"[a-zA-Z0-9_-]+",
            original_query,
        )
        if len(term) > 2
    ]

    score = 0

    # --------------------------------------------------------
    # DIRECT TOPIC RELEVANCE
    # --------------------------------------------------------

    for term in query_terms:
        if term in title:
            score += 8
        elif term in content:
            score += 2

    # --------------------------------------------------------
    # SOURCE QUALITY
    # --------------------------------------------------------

    if domain in HIGH_QUALITY_DOMAINS:
        score += 14
    elif domain in MEDIUM_QUALITY_DOMAINS:
        score += 6

    # --------------------------------------------------------
    # EVIDENCE TYPE
    # --------------------------------------------------------

    angle_scores = {
        "official": 10,
        "technical": 9,
        "data": 9,
        "onchain": 9,
        "news": 8,
        "analysis": 7,
        "criticism": 7,
        "ecosystem": 6,
        "tokenomics": 6,
        "general": 4,
    }

    score += angle_scores.get(
        angle,
        2,
    )

    # --------------------------------------------------------
    # SIGNAL TERMS
    # --------------------------------------------------------

    signal_terms = [
        "launch",
        "launched",
        "announced",
        "announcement",
        "released",
        "release",
        "integrated",
        "integration",
        "transaction",
        "transactions",
        "volume",
        "users",
        "wallets",
        "funding",
        "revenue",
        "partnership",
        "partner",
        "upgrade",
        "governance",
        "token",
        "airdrop",
        "claim",
        "vesting",
        "allocation",
        "mechanism",
        "architecture",
        "security",
        "exploit",
        "hack",
        "risk",
        "data",
        "adoption",
        "activity",
        "supply",
        "liquidity",
        "flows",
        "fees",
        "market share",
    ]

    for term in signal_terms:
        if term in title:
            score += 2

    # --------------------------------------------------------
    # CONTENT DEPTH
    # --------------------------------------------------------

    if len(content) > 500:
        score += 2

    if len(content) > 1000:
        score += 2

    if len(content) > 1500:
        score += 1

    # --------------------------------------------------------
    # TITLE QUALITY
    # --------------------------------------------------------

    if title:
        score += 1

    if len(title) > 20:
        score += 1

    return score


def rank_results(results, original_query):
    scored = []

    for result in results:
        score = score_result(
            result,
            original_query,
        )

        result = dict(result)

        result["score"] = score

        scored.append(result)

    scored.sort(
        key=lambda item: item.get(
            "score",
            0,
        ),
        reverse=True,
    )

    return scored


# ============================================================
# EVIDENCE DIVERSITY
# ============================================================

def diversify_results(results, limit=30):
    """
    Prevent the final research pool from being dominated by
    five versions of the same evidence type.

    The strongest result still wins, but useful secondary
    angles are deliberately preserved.
    """

    if not results:
        return []

    selected = []

    angle_counts = {}

    # First pass:
    # preserve strong evidence from different angles.
    for result in results:
        angle = result.get(
            "research_angle",
            "general",
        )

        count = angle_counts.get(
            angle,
            0,
        )

        if count >= 5:
            continue

        selected.append(result)

        angle_counts[angle] = count + 1

        if len(selected) >= limit:
            return selected

    # Second pass:
    # fill any remaining slots with highest-ranked results.
    selected_urls = {
        result.get("url", "")
        for result in selected
    }

    for result in results:
        if len(selected) >= limit:
            break

        url = result.get(
            "url",
            "",
        )

        if url in selected_urls:
            continue

        selected.append(result)

        selected_urls.add(url)

    return selected


# ============================================================
# EXA REQUEST
# ============================================================

def exa_search(
    query,
    max_results,
    research_angle,
):
    headers = {
        "x-api-key": EXA_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "type": "auto",
        "numResults": max(
            1,
            int(max_results),
        ),
        "contents": {
            "text": {
                "maxCharacters": 1800
            }
        },
    }

    response = requests.post(
        EXA_URL,
        headers=headers,
        json=payload,
        timeout=60,
    )

    response.raise_for_status()

    data = response.json()

    results = []

    for item in data.get(
        "results",
        [],
    ):
        result = normalize_result(
            item,
            research_angle=research_angle,
        )

        if not result["url"]:
            continue

        if not result["content"]:
            continue

        if not is_crypto_relevant(result):
            continue

        results.append(result)

    return results


# ============================================================
# LEGACY ANGLE CLASSIFICATION
# ============================================================

def classify_query_angle(query):
    text = str(query).lower()

    if any(
        word in text
        for word in [
            "official",
            "documentation",
            "announcement",
        ]
    ):
        return "official"

    if any(
        word in text
        for word in [
            "technical",
            "how",
            "architecture",
            "mechanism",
            "protocol",
        ]
    ):
        return "technical"

    if any(
        word in text
        for word in [
            "news",
            "latest",
            "launch",
            "update",
            "developments",
        ]
    ):
        return "news"

    if any(
        word in text
        for word in [
            "onchain",
            "on-chain",
            "transactions",
            "wallets",
            "flows",
        ]
    ):
        return "onchain"

    if any(
        word in text
        for word in [
            "data",
            "volume",
            "users",
            "activity",
            "metrics",
            "adoption",
        ]
    ):
        return "data"

    if any(
        word in text
        for word in [
            "risk",
            "criticism",
            "controversy",
            "problem",
            "exploit",
            "security",
        ]
    ):
        return "criticism"

    if any(
        word in text
        for word in [
            "tokenomics",
            "incentives",
            "vesting",
            "allocation",
            "supply",
            "economics",
        ]
    ):
        return "tokenomics"

    if any(
        word in text
        for word in [
            "partner",
            "integration",
            "ecosystem",
            "funding",
        ]
    ):
        return "ecosystem"

    if any(
        word in text
        for word in [
            "analysis",
            "explained",
            "implications",
            "why it matters",
        ]
    ):
        return "analysis"

    return "general"


# ============================================================
# MAIN SEARCH
# ============================================================

def search_web(
    query: str,
    max_results: int = MAX_RESEARCH_RESULTS,
):
    """
    Broad research engine.

    One user query becomes multiple evidence-oriented
    searches. Results are normalized, filtered, deduplicated,
    ranked, and diversified.

    The return structure remains compatible with the existing
    writer and webhook pipeline.
    """

    if not EXA_API_KEY:
        raise RuntimeError(
            "EXA_API_KEY is missing."
        )

    query = str(
        query
    ).strip()

    if not query:
        raise ValueError(
            "Research query cannot be empty."
        )

    logger.info(
        "Starting broad research: %s",
        query,
    )

    research_queries = build_research_queries(
        query
    )

    all_results = []

    # Keep individual searches small.
    # Breadth comes from the evidence angles.
    per_query_results = max(
        2,
        min(
            4,
            int(max_results),
        ),
    )

    for index, query_data in enumerate(
        research_queries
    ):
        research_query, research_angle = query_data

        try:
            results = exa_search(
                research_query,
                per_query_results,
                research_angle,
            )

            all_results.extend(
                results
            )

            logger.info(
                "Research angle %s/%s [%s] returned %s results",
                index + 1,
                len(research_queries),
                research_angle,
                len(results),
            )

        except Exception:
            logger.exception(
                "Research angle failed [%s]: %s",
                research_angle,
                research_query,
            )

    # --------------------------------------------------------
    # CLEAN
    # --------------------------------------------------------

    all_results = deduplicate_results(
        all_results
    )

    # --------------------------------------------------------
    # RANK
    # --------------------------------------------------------

    ranked_results = rank_results(
        all_results,
        query,
    )

    # --------------------------------------------------------
    # DIVERSIFY
    # --------------------------------------------------------

    ranked_results = diversify_results(
        ranked_results,
        limit=30,
    )

    logger.info(
        "Broad research complete: %s unique candidates",
        len(ranked_results),
    )

    return {
        "query": query,
        "answer": "",
        "results": ranked_results,
    }


# ============================================================
# SOURCE FORMAT
# ============================================================

def format_sources(research):
    lines = []

    for index, result in enumerate(
        research.get(
            "results",
            [],
        ),
        start=1,
    ):
        title = (
            result.get(
                "title",
                "Untitled",
            )
            or "Untitled"
        )

        url = (
            result.get(
                "url",
                "",
            )
            or ""
        ).strip()

        if not url:
            continue

        lines.append(
            f"{index}. {title}\n{url}"
        )

    return "\n\n".join(lines)