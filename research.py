import logging
import requests

from config import EXA_API_KEY, MAX_RESEARCH_RESULTS

logger = logging.getLogger(__name__)

EXA_URL = "https://api.exa.ai/search"

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
]


def is_crypto_relevant(result):
    """
    Reject obviously unrelated search results.
    """

    text = (
        f"{result.get('title', '')} "
        f"{result.get('content', '')}"
    ).lower()

    return any(
        term in text
        for term in CRYPTO_TERMS
    )


def search_web(query: str, max_results: int = MAX_RESEARCH_RESULTS):
    """
    Search the web using Exa and keep only crypto-relevant results.
    """

    if not EXA_API_KEY:
        raise RuntimeError("EXA_API_KEY is missing.")

    logger.info("Researching: %s", query)

    headers = {
        "x-api-key": EXA_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "type": "auto",
        "numResults": max_results,
        "contents": {
            "text": {
                "maxCharacters": 800
            }
        }
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

    for item in data.get("results", []):

        result = {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": item.get("text", ""),
        }

        if is_crypto_relevant(result):
            results.append(result)

    logger.info(
        "Crypto-relevant results: %s",
        len(results),
    )

    return {
        "query": query,
        "answer": "",
        "results": results,
    }


def format_sources(research):
    lines = []

    for index, result in enumerate(
        research.get("results", []),
        start=1,
    ):
        title = result.get("title", "Untitled")
        url = result.get("url", "")

        if url:
            lines.append(
                f"{index}. {title}\n{url}"
            )

    return "\n\n".join(lines)