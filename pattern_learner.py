import os
import re
import time
import logging
import requests
from urllib.parse import quote

from creator_store import cache_get, cache_set

logger = logging.getLogger(__name__)

X_API_BASE = "https://api.x.com/2/tweets/search/recent"

def _topic_terms(topic):
    text = re.sub(r"[^A-Za-z0-9$# ]+", " ", str(topic or "")).strip()
    return " ".join(text.split()[:8])

def _score(post, users):
    metrics = post.get("public_metrics") or {}
    engagement = sum(int(metrics.get(k, 0) or 0) for k in (
        "like_count", "reply_count", "retweet_count", "quote_count"
    ))
    user = users.get(post.get("author_id"), {})
    followers = int((user.get("public_metrics") or {}).get("followers_count", 0) or 0)
    return engagement / max(followers, 100)

def _fetch_x(topic):
    token = os.getenv("X_BEARER_TOKEN", "").strip()
    if not token:
        return []
    query = f'({_topic_terms(topic)}) lang:en -is:retweet'
    params = {
        "query": query,
        "max_results": 100,
        "tweet.fields": "created_at,public_metrics,author_id,text",
        "expansions": "author_id",
        "user.fields": "username,public_metrics",
    }
    try:
        response = requests.get(
            X_API_BASE,
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        users = {
            item["id"]: item
            for item in payload.get("includes", {}).get("users", [])
        }
        posts = []
        for item in payload.get("data", []):
            text = re.sub(r"\s+", " ", item.get("text", "")).strip()
            if not text:
                continue
            posts.append({
                "text": text,
                "created_at": item.get("created_at", ""),
                "username": users.get(item.get("author_id"), {}).get("username", ""),
                "score": _score(item, users),
            })
        posts.sort(key=lambda x: x["score"], reverse=True)
        return posts[:40]
    except Exception:
        logger.exception("X pattern collection failed.")
        return []

def _analyze(posts):
    if not posts:
        return {
            "available": False,
            "count": 0,
            "openers": [],
            "length": {},
            "slang": [],
            "angles": [],
            "sample": [],
        }
    openers = []
    lengths = []
    for post in posts:
        words = post["text"].split()
        openers.append(" ".join(words[:5]))
        lengths.append(len(post["text"]))
    common = {}
    for post in posts:
        for token in re.findall(r"\$?[A-Za-z][A-Za-z0-9_]{2,}", post["text"].lower()):
            if token in {"the","and","for","this","that","with","from","crypto","about"}:
                continue
            common[token] = common.get(token, 0) + 1
    slang = [x for x,n in sorted(common.items(), key=lambda kv: kv[1], reverse=True) if n >= 2][:20]
    return {
        "available": True,
        "count": len(posts),
        "openers": openers[:12],
        "length": {
            "avg_chars": round(sum(lengths) / len(lengths)),
            "min_chars": min(lengths),
            "max_chars": max(lengths),
        },
        "slang": slang,
        "angles": [],
        "sample": [{"text": p["text"], "username": p["username"]} for p in posts[:20]],
    }

def get_patterns(topic, hot=False):
    key = "patterns:" + re.sub(r"\s+", " ", str(topic or "").lower()).strip()
    cached = cache_get(key, 3 * 3600 if hot else 24 * 3600)
    if cached:
        return cached
    data = _analyze(_fetch_x(topic))
    cache_set(key, data)
    return data
