import logging
from research import search_web

logger = logging.getLogger(__name__)


def deep_research(query, max_sources=12):
    """
    Run one comprehensive research pass.

    search_web already expands a topic across multiple research angles
    (general, news, official, technical, data, onchain, ecosystem,
    tokenomics, criticism and analysis). Calling search_web repeatedly
    here was redundant and made Telegram commands much slower.
    """
    query = str(query or "").strip()
    if not query:
        raise ValueError("Research query cannot be empty.")

    try:
        result = search_web(query, max(6, int(max_sources)))
    except Exception:
        logger.exception("Deep research search failed: %s", query)
        return {
            "query": query,
            "answer": "",
            "results": [],
            "source_count": 0,
            "distinct_domains": 0,
            "minimum_source_requirement_met": False,
        }

    results = result.get("results") or []

    # search_web already ranks, deduplicates and diversifies results.
    # Keep the strongest sources while preserving its existing ordering.
    selected = [dict(item) for item in results[:max(1, int(max_sources))]]

    distinct_domains = {
        (item.get("domain") or "").strip().lower()
        for item in selected
        if item.get("domain")
    }

    return {
        "query": query,
        "answer": result.get("answer", ""),
        "results": selected,
        "source_count": len(selected),
        "distinct_domains": len(distinct_domains),
        "minimum_source_requirement_met": len(selected) >= 5 and len(distinct_domains) >= 5,
    }
