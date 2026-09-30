import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone

DB_PATH = os.getenv("CREATOR_DB_PATH", "creator_engine.db")

BUILTIN_BANS = [
    "actually", "honestly", "essentially", "literally", "game-changer",
    "revolutionary", "groundbreaking", "unlock", "unleash", "delve",
    "landscape", "ecosystem", "journey", "navigate", "tapestry",
    "testament", "realm", "paradigm", "seamless", "robust", "leverage",
    "at the end of the day", "the future of", "changing the game",
    "here's the thing", "let that sink in", "read that again",
    "think about it", "ever wondered", "in today's fast-paced world",
    "in the world of crypto", "let's dive in", "let's break it down",
    "buckle up",
    "it's not", "this isn't about", "not just", "more than just",
    "forget ", "on one hand", "on the other hand",
]

def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = _conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS banned_phrases (
        phrase TEXT PRIMARY KEY,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS drafts (
        id TEXT PRIMARY KEY,
        chat_id TEXT,
        command TEXT,
        request TEXT,
        primary_text TEXT,
        alternate_text TEXT,
        platform TEXT,
        created_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'draft'
    );
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id TEXT,
        action TEXT NOT NULL,
        old_text TEXT,
        new_text TEXT,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS approved_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        draft_id TEXT,
        text TEXT NOT NULL,
        platform TEXT,
        approved_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS structures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        structure TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS pattern_cache (
        cache_key TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        fetched_at TEXT NOT NULL
    );
    """)
    conn.commit()
    conn.close()

def now():
    return datetime.now(timezone.utc).isoformat()

def add_ban(phrase):
    phrase = str(phrase or "").strip()
    if not phrase:
        raise ValueError("Phrase cannot be empty.")
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO banned_phrases(phrase, created_at) VALUES (?, ?)",
        (phrase, now()),
    )
    conn.commit()
    conn.close()
    return phrase

def banned_phrases():
    conn = _conn()
    rows = conn.execute("SELECT phrase FROM banned_phrases ORDER BY phrase").fetchall()
    conn.close()
    return BUILTIN_BANS + [r["phrase"] for r in rows]

def _outside_quotes(text, start, end):
    before = text[:start]
    return before.count('"') % 2 == 0 and before.count("'") % 2 == 0

def find_banned(text):
    text = str(text or "")
    hits = []
    for phrase in banned_phrases():
        pattern = re.compile(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", re.I)
        for match in pattern.finditer(text):
            if _outside_quotes(text, match.start(), match.end()):
                hits.append(phrase)
                break
    return sorted(set(hits), key=str.lower)

def save_draft(chat_id, command, request, primary, alternate, platform):
    draft_id = uuid.uuid4().hex[:10]
    conn = _conn()
    conn.execute(
        """INSERT INTO drafts(id,chat_id,command,request,primary_text,alternate_text,platform,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (draft_id, str(chat_id or ""), command, request, primary, alternate, platform, now()),
    )
    conn.commit()
    conn.close()
    return draft_id

def latest_draft(chat_id):
    conn = _conn()
    row = conn.execute(
        "SELECT * FROM drafts WHERE chat_id=? ORDER BY created_at DESC LIMIT 1",
        (str(chat_id),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def record_feedback(draft_id, action, old_text="", new_text=""):
    conn = _conn()
    conn.execute(
        "INSERT INTO feedback(draft_id,action,old_text,new_text,created_at) VALUES(?,?,?,?,?)",
        (draft_id, action, old_text, new_text, now()),
    )
    if action == "approve":
        conn.execute("UPDATE drafts SET status='approved' WHERE id=?", (draft_id,))
        if new_text or old_text:
            text = new_text or old_text
            row = conn.execute("SELECT platform FROM drafts WHERE id=?", (draft_id,)).fetchone()
            conn.execute(
                "INSERT INTO approved_posts(draft_id,text,platform,approved_at) VALUES(?,?,?,?)",
                (draft_id, text, row["platform"] if row else "", now()),
            )
    elif action == "reject":
        conn.execute("UPDATE drafts SET status='rejected' WHERE id=?", (draft_id,))
    elif action == "edit":
        conn.execute(
            "UPDATE drafts SET primary_text=?, status='edited' WHERE id=?",
            (new_text, draft_id),
        )
    conn.commit()
    conn.close()

def approved_posts(limit=20):
    conn = _conn()
    rows = conn.execute(
        "SELECT text, platform, approved_at FROM approved_posts ORDER BY approved_at DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def recent_structures(limit=10):
    conn = _conn()
    rows = conn.execute(
        "SELECT structure FROM structures ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()
    conn.close()
    return [r["structure"] for r in rows]

def remember_structure(structure):
    if not structure:
        return
    conn = _conn()
    conn.execute(
        "INSERT INTO structures(structure,created_at) VALUES(?,?)",
        (structure, now()),
    )
    conn.commit()
    conn.close()

def cache_get(key, max_age_seconds):
    import json
    conn = _conn()
    row = conn.execute(
        "SELECT payload,fetched_at FROM pattern_cache WHERE cache_key=?",
        (key,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    try:
        stamp = datetime.fromisoformat(row["fetched_at"])
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if age > max_age_seconds:
            return None
        return json.loads(row["payload"])
    except Exception:
        return None

def cache_set(key, payload):
    import json
    conn = _conn()
    conn.execute(
        "INSERT OR REPLACE INTO pattern_cache(cache_key,payload,fetched_at) VALUES(?,?,?)",
        (key, json.dumps(payload, ensure_ascii=False), now()),
    )
    conn.commit()
    conn.close()
