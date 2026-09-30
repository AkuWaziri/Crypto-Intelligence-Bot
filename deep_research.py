import logging
from research import search_web

logger = logging.getLogger(__name__)

def deep_research(query, max_sources=12):
    query = str(query or "").strip()
    if not query:
        raise ValueError("Research query cannot be empty.")

    angle_queries = [
        query,
        f"{query} official docs announcement",
        f"{query} recent news",
        f"{query} technical mechanism architecture",
        f"{query} onchain data activity wallets transactions",
        f"{query} audit security exploit criticism controversy",
        f"{query} team founders history funding investors",
        f"{query} adoption users integrations payments volume",
    ]

    merged = []
    seen = set()
    for q in angle_queries:
        try:
            result = search_web(q, max(6, max_sources))
            for item in result.get("results", []):
                key = (item.get("url") or item.get("title") or "").strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                item = dict(item)
                item["deep_query"] = q
                merged.append(item)
        except Exception:
            logger.exception("Deep research angle failed: %s", q)

    # Preserve source diversity before score order.
    selected = []
    domains = set()
    for item in sorted(merged, key=lambda x: float(x.get("score", 0) or 0), reverse=True):
        domain = (item.get("domain") or "").lower()
        if domain and domain in domains:
            continue
        selected.append(item)
        if domain:
            domains.add(domain)
        if len(selected) >= max_sources:
            break

    # If fewer than five independent domains exist, fill with remaining sources.
    if len(selected) < min(5, max_sources):
        selected_keys = {(x.get("url") or x.get("title") or "").lower() for x in selected}
        for item in sorted(merged, key=lambda x: float(x.get("score", 0) or 0), reverse=True):
            key = (item.get("url") or item.get("title") or "").lower()
            if key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(key)
            if len(selected) >= max_sources:
                break

    result = {
        "query": query,
        "answer": "",
        "results": selected,
        "source_count": len(selected),
        "distinct_domains": len({(x.get("domain") or "").lower() for x in selected if x.get("domain")}),
        "minimum_source_requirement_met": len(selected) >= 5 and len({
            (x.get("domain") or "").lower() for x in selected if x.get("domain")
        }) >= 5,
    }
    return result
