import logging
import requests

from config import EXA_API_KEY, MAX_RESEARCH_RESULTS

logger = logging.getLogger(__name__)

EXA_URL = "https://api.exa.ai/search"


# ---------------------------------------------------------
# OBVIOUSLY IRRELEVANT CONTENT
# ---------------------------------------------------------

LOW_VALUE_TERMS = [
    "casino",
    "gambling",
    "horoscope",
    "celebrity gossip",
]


# ---------------------------------------------------------
# CRYPTO RELEVANCE TERMS
# ---------------------------------------------------------

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
    "defi",
]


# ---------------------------------------------------------
# RELEVANCE CHECK
# ---------------------------------------------------------

def is_crypto_relevant(result):
    """
    Determine whether a result is reasonably related
    to crypto/Web3.

    We intentionally keep this filter permissive.
    Exa is responsible for discovery; the writer can
    determine whether a result is actually useful.
    """

    title = str(
        result.get("title", "")
    )

    content = str(
        result.get("content", "")
    )

    text = (
        f"{title} {content}"
    ).lower()

    # Reject obvious non-crypto / low-value material.
    for term in LOW_VALUE_TERMS:
        if term in text:
            return False

    # Accept if any known crypto term appears.
    for term in CRYPTO_TERMS:
        if term.lower() in text:
            return True

    # If Exa returned a result for a targeted crypto query,
    # don't automatically discard it just because the page
    # itself uses different terminology.
    return True


# ---------------------------------------------------------
# NORMALIZE RESULT
# ---------------------------------------------------------

def normalize_result(item):
    """
    Convert an Exa result into the internal research format.
    """

    title = str(
        item.get("title", "")
    ).strip()

    url = str(
        item.get("url", "")
    ).strip()

    content = str(
        item.get("text", "")
    ).strip()

    if len(content) > 1500:
        content = content[:1500].rstrip()

    return {
        "title": title,
        "url": url,
        "content": content,
    }


# ---------------------------------------------------------
# DEDUPLICATE RESULTS
# ---------------------------------------------------------

def deduplicate_results(results):
    """
    Remove duplicate URLs and duplicate titles.
    """

    unique = []

    seen_urls = set()
    seen_titles = set()

    for result in results:

        url = (
            result.get("url", "")
            .strip()
            .lower()
        )

        title = (
            result.get("title", "")
            .strip()
            .lower()
        )

        if url and url in seen_urls:
            continue

        if title and title in seen_titles:
            continue

        if url:
            seen_urls.add(url)

        if title:
            seen_titles.add(title)

        unique.append(result)

    return unique


# ---------------------------------------------------------
# EXA SEARCH
# ---------------------------------------------------------

def search_web(
    query: str,
    max_results: int = MAX_RESEARCH_RESULTS,
):
    """
    Search the web using Exa.

    The research layer discovers current information.
    The writer is responsible for turning the discoveries
    into useful crypto intelligence.
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
        "Researching: %s",
        query,
    )

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
                "maxCharacters": 1500
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
            item
        )

        if not result["url"]:
            continue

        if not result["content"]:
            continue

        if not is_crypto_relevant(
            result
        ):
            continue

        results.append(
            result
        )

    results = deduplicate_results(
        results
    )

    logger.info(
        "Research results retained: %s",
        len(results),
    )

    return {
        "query": query,
        "answer": "",
        "results": results,
    }


# ---------------------------------------------------------
# FORMAT SOURCES
# ---------------------------------------------------------

def format_sources(research):
    """
    Format research sources for the writer.
    """

    lines = []

    for index, result in enumerate(
        research.get(
            "results",
            []
        ),
        start=1,
    ):

        title = (
            result.get(
                "title",
                "Untitled"
            )
            or "Untitled"
        )

        url = (
            result.get(
                "url",
                ""
            )
            or ""
        ).strip()

        if not url:
            continue

        lines.append(
            f"{index}. {title}\n{url}"
        )

    return "\n\n".join(
        lines
    )
