import logging
import re
import requests

from config import EXA_API_KEY, MAX_RESEARCH_RESULTS

logger = logging.getLogger(__name__)

EXA_URL = "https://api.exa.ai/search"


# ---------------------------------------------------------
# CRYPTO RELEVANCE
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
    "stablecoin",
]


# ---------------------------------------------------------
# GENERIC / LOW-VALUE TERMS
# ---------------------------------------------------------

LOW_VALUE_TERMS = [
    "sponsored",
    "casino",
    "gambling",
    "horoscope",
    "celebrity gossip",
]


# ---------------------------------------------------------
# RELEVANCE CHECK
# ---------------------------------------------------------

def is_crypto_relevant(result):
    """
    Keep results that have meaningful crypto/Web3 relevance.
    """

    title = str(result.get("title", ""))
    content = str(result.get("content", ""))

    text = f"{title} {content}".lower()

    if any(term in text for term in LOW_VALUE_TERMS):
        return False

    matches = 0

    for term in CRYPTO_TERMS:
        if re.search(
            rf"\b{re.escape(term)}\b",
            text,
            flags=re.IGNORECASE,
        ):
            matches += 1

    return matches >= 1


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
# DEDUPLICATION
# ---------------------------------------------------------

def deduplicate_results(results):
    """
    Remove duplicate URLs and duplicate titles.
    """

    unique = []

    seen_urls = set()
    seen_titles = set()

    for result in results:

        url = result.get("url", "").strip().lower()
        title = result.get("title", "").strip().lower()

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
# WEB SEARCH
# ---------------------------------------------------------

def search_web(
    query: str,
    max_results: int = MAX_RESEARCH_RESULTS,
):
    """
    Search the web using Exa and return crypto-relevant
    research material for the intelligence writer.
    """

    if not EXA_API_KEY:
        raise RuntimeError(
            "EXA_API_KEY is missing."
        )

    query = str(query).strip()

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

        results.append(result)

    results = deduplicate_results(
        results
    )

    logger.info(
        "Crypto-relevant results: %s",
        len(results),
    )

    return {
        "query": query,
        "answer": "",
        "results": results,
    }


# ---------------------------------------------------------
# SOURCE FORMATTING
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

        url = result.get(
            "url",
            ""
        )

        if not url:
            continue

        lines.append(
            f"{index}. {title}\n{url}"
        )

    return "\n\n".join(lines)