import html
import logging
import re
import requests
from urllib.parse import urlparse
from xml.etree import ElementTree

from config import MAX_RESEARCH_RESULTS

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"
BING_NEWS_RSS = "https://www.bing.com/news/search"

LOW_VALUE_TERMS = ["casino", "gambling", "horoscope", "celebrity gossip"]

CRYPTO_TERMS = [
    "crypto", "cryptocurrency", "blockchain", "web3", "defi", "token",
    "airdrop", "stablecoin", "bitcoin", "btc", "ethereum", "eth", "solana",
    "base", "arbitrum", "optimism", "polygon", "avalanche", "bnb", "wallet",
    "on-chain", "onchain", "smart contract", "protocol", "layer 2", "l2", "dao",
    "usdc", "usdt", "dex", "staking", "yield", "liquidity", "bridge",
    "perpetual", "trading", "exchange", "ai agent", "ai agents", "agentic",
    "rwa", "tokenization", "payments", "memecoin", "nft", "restaking",
]

HIGH_QUALITY_DOMAINS = {
    "github.com", "ethereum.org", "solana.com", "base.org", "arbitrum.io",
    "optimism.io", "circle.com", "visa.com", "mastercard.com", "stripe.com",
    "paypal.com", "a16zcrypto.com", "coindesk.com", "theblock.co",
    "blockworks.co", "decrypt.co", "bankless.com", "messari.io", "defillama.com",
    "dune.com", "l2beat.com", "coinbase.com", "binance.com", "kraken.com",
    "uniswap.org", "chainalysis.com", "consensys.io", "fireblocks.com",
    "paradigm.xyz", "variant.fund",
}

MEDIUM_QUALITY_DOMAINS = {
    "mirror.xyz", "paragraph.xyz", "medium.com", "substack.com",
    "cointelegraph.com", "cryptoslate.com", "beincrypto.com", "thedefiant.io",
}


def domain_from_url(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def clean_text(text):
    text = html.unescape(str(text or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_query_text(text):
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def is_crypto_relevant(result, allow_targeted=False):
    text = f"{result.get('title', '')} {result.get('content', '')}".lower()
    if any(term in text for term in LOW_VALUE_TERMS):
        return False
    if allow_targeted:
        return True
    return any(term in text for term in CRYPTO_TERMS)


def build_research_queries(query):
    base = str(query or "").strip()
    if not base:
        return []
    return [
        (base, "general"),
        (f"{base} latest news developments update", "news"),
        (f"{base} official announcement documentation", "official"),
        (f"{base} how it works technical mechanism architecture", "technical"),
        (f"{base} users adoption activity metrics data", "data"),
        (f"{base} onchain transactions wallets volume flows", "onchain"),
        (f"{base} integrations partners ecosystem funding", "ecosystem"),
        (f"{base} incentives tokenomics allocation economics", "tokenomics"),
        (f"{base} criticism controversy risks security", "criticism"),
        (f"{base} analysis explained implications why it matters", "analysis"),
    ]


def normalize_result(title, url, content, research_angle="general"):
    title = clean_text(title)
    url = str(url or "").strip()
    content = clean_text(content)
    if len(content) > 1800:
        content = content[:1800].rstrip()
    return {
        "title": title,
        "url": url,
        "content": content,
        "domain": domain_from_url(url),
        "research_angle": research_angle,
    }


def deduplicate_results(results):
    unique = []
    seen_urls = set()
    seen_titles = set()
    for result in results:
        url = result.get("url", "").strip().lower()
        title = normalize_query_text(result.get("title", ""))
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


def score_result(result, original_query):
    title = result.get("title", "").lower()
    content = result.get("content", "").lower()
    domain = result.get("domain", "").lower()
    angle = result.get("research_angle", "general")
    score = 0

    for term in re.findall(r"[a-zA-Z0-9_-]+", original_query.lower()):
        if len(term) > 2:
            if term in title:
                score += 8
            elif term in content:
                score += 2

    if domain in HIGH_QUALITY_DOMAINS:
        score += 14
    elif domain in MEDIUM_QUALITY_DOMAINS:
        score += 6

    score += {
        "official": 10, "technical": 9, "data": 9, "onchain": 9,
        "news": 8, "analysis": 7, "criticism": 7, "ecosystem": 6,
        "tokenomics": 6, "general": 4,
    }.get(angle, 2)

    for term in [
        "launch", "launched", "announced", "released", "integrated", "transaction",
        "volume", "users", "wallets", "funding", "revenue", "partnership", "upgrade",
        "governance", "token", "airdrop", "claim", "vesting", "allocation", "security",
        "exploit", "hack", "risk", "adoption", "activity", "liquidity", "fees",
    ]:
        if term in title:
            score += 2

    if len(content) > 500:
        score += 2
    if len(content) > 1000:
        score += 2
    if title:
        score += 1
    return score


def rank_results(results, original_query):
    ranked = []
    for result in results:
        item = dict(result)
        item["score"] = score_result(item, original_query)
        ranked.append(item)
    ranked.sort(key=lambda item: item.get("score", 0), reverse=True)
    return ranked


def diversify_results(results, limit=30):
    selected = []
    angle_counts = {}
    for result in results:
        angle = result.get("research_angle", "general")
        if angle_counts.get(angle, 0) >= 5:
            continue
        selected.append(result)
        angle_counts[angle] = angle_counts.get(angle, 0) + 1
        if len(selected) >= limit:
            return selected
    return selected


def parse_rss(xml_text, research_angle, max_results, allow_targeted=False):
    root = ElementTree.fromstring(xml_text)
    results = []
    for item in root.findall(".//item")[:max_results]:
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        description = item.findtext("description", "")
        result = normalize_result(title, link, description, research_angle)
        if (
            result["url"]
            and result["title"]
            and result["content"]
            and is_crypto_relevant(result, allow_targeted=allow_targeted)
        ):
            results.append(result)
    return results


def google_news_search(query, max_results, research_angle, allow_targeted=False):
    response = requests.get(
        GOOGLE_NEWS_RSS,
        params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        headers={"User-Agent": "Mozilla/5.0 Crypto-Intelligence-Bot/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    return parse_rss(response.text, research_angle, max_results, allow_targeted)


def bing_news_search(query, max_results, research_angle, allow_targeted=False):
    response = requests.get(
        BING_NEWS_RSS,
        params={"q": query, "format": "rss"},
        headers={"User-Agent": "Mozilla/5.0 Crypto-Intelligence-Bot/1.0"},
        timeout=30,
    )
    response.raise_for_status()
    return parse_rss(response.text, research_angle, max_results, allow_targeted)


def classify_query_angle(query):
    text = str(query).lower()
    if any(word in text for word in ["official", "documentation", "announcement"]):
        return "official"
    if any(word in text for word in ["technical", "how", "architecture", "mechanism", "protocol"]):
        return "technical"
    if any(word in text for word in ["news", "latest", "launch", "update", "developments"]):
        return "news"
    if any(word in text for word in ["onchain", "on-chain", "transactions", "wallets", "flows"]):
        return "onchain"
    if any(word in text for word in ["data", "volume", "users", "activity", "metrics", "adoption"]):
        return "data"
    if any(word in text for word in ["risk", "criticism", "controversy", "problem", "exploit", "security"]):
        return "criticism"
    if any(word in text for word in ["tokenomics", "incentives", "vesting", "allocation", "supply", "economics"]):
        return "tokenomics"
    if any(word in text for word in ["partner", "integration", "ecosystem", "funding"]):
        return "ecosystem"
    if any(word in text for word in ["analysis", "explained", "implications", "why it matters"]):
        return "analysis"
    return "general"


def build_visual_reference_result(query):
    """Keep image-grounded creative requests usable when web search has no hit."""
    marker_positions = [
        query.find("VISUAL EVIDENCE FROM IMAGE:"),
        query.find("Image context:"),
    ]
    marker_positions = [position for position in marker_positions if position >= 0]
    if not marker_positions:
        return None

    marker_position = min(marker_positions)
    if query[marker_position:].startswith("VISUAL EVIDENCE FROM IMAGE:"):
        marker = "VISUAL EVIDENCE FROM IMAGE:"
    else:
        marker = "Image context:"

    visual_context = query.split(marker, 1)[1].strip()
    if not visual_context:
        return None

    return normalize_result(
        "User-provided image reference",
        "image://attached-reference",
        "USER-PROVIDED VISUAL REFERENCE — NOT EXTERNAL RESEARCH.\n"
        "Use this only as creative inspiration and visual evidence.\n\n"
        + visual_context,
        "visual_reference",
    )


def search_web(query: str, max_results: int = MAX_RESEARCH_RESULTS):
    query = str(query or "").strip()
    if not query:
        raise ValueError("Research query cannot be empty.")

    # Image-assisted research can be grounded by either the vision packet
    # or the image context passed into the creative idea engine.
    # In both cases, do not discard useful article results merely because an
    # article does not repeat a generic crypto keyword.
    allow_targeted = (
        "VISUAL EVIDENCE FROM IMAGE:" in query
        or "Image context:" in query
    )

    per_query = max(2, min(4, int(max_results)))
    all_results = []

    for research_query, angle in build_research_queries(query):
        try:
            results = google_news_search(
                research_query,
                per_query,
                angle,
                allow_targeted=allow_targeted,
            )
            all_results.extend(results)
            if results:
                logger.info("Google News angle %s returned %s results", angle, len(results))
        except Exception:
            logger.exception("Google News search failed [%s]", research_query)

    if not all_results:
        try:
            all_results = bing_news_search(
                query,
                max(5, int(max_results)),
                "news",
                allow_targeted=allow_targeted,
            )
        except Exception:
            logger.exception("Bing News fallback failed")

    all_results = deduplicate_results(all_results)

    if not all_results and allow_targeted:
        visual_reference = build_visual_reference_result(query)
        if visual_reference:
            all_results = [visual_reference]
            logger.info("Using attached image as the creative reference because web research returned no results.")

    ranked = rank_results(all_results, query)
    ranked = diversify_results(ranked, limit=30)

    logger.info("Manual research complete: %s unique candidates", len(ranked))
    return {"query": query, "answer": "", "results": ranked}


def format_sources(research):
    lines = []
    for index, result in enumerate(research.get("results", []), start=1):
        title = result.get("title", "Untitled") or "Untitled"
        url = (result.get("url", "") or "").strip()
        if url:
            lines.append(f"{index}. {title}\n{url}")
    return "\n\n".join(lines)
