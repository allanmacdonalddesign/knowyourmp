"""SQLite cache: HTTP responses (so we are kind to upstream) and topic classifications."""
import json
import sqlite3
import time

from .config import DB_PATH


def connect(path=None) -> sqlite3.Connection:
    path = path or DB_PATH
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path))
    db.execute("CREATE TABLE IF NOT EXISTS http_cache (key TEXT PRIMARY KEY, body TEXT, fetched_at REAL)")
    # Older versions cached Represent postcode lookups; their keys contain postal codes. Purge them.
    purged = db.execute("DELETE FROM http_cache WHERE key LIKE '%represent.opennorth.ca/postcodes/%'").rowcount
    db.commit()
    if purged:
        db.execute("VACUUM")  # deleted rows otherwise linger in free pages on disk
    db.execute(
        "CREATE TABLE IF NOT EXISTS classifications "
        "(source_url TEXT PRIMARY KEY, topics TEXT, model TEXT, classified_at REAL)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS plain_bills (bill_url TEXT PRIMARY KEY, text TEXT, grounded INTEGER, model TEXT, created_at REAL)"
    )
    return db


class HttpCache:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def get(self, key: str, max_age: float):
        row = self.db.execute("SELECT body, fetched_at FROM http_cache WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[1] <= max_age:
            return row[0]
        return None

    def put(self, key: str, body: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO http_cache VALUES (?,?,?)", (key, body, time.time()))
        self.db.commit()


class ClassificationCache:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def get(self, source_url: str):
        row = self.db.execute("SELECT topics FROM classifications WHERE source_url=?", (source_url,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, source_url: str, topics: list[str], model: str) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO classifications VALUES (?,?,?,?)",
            (source_url, json.dumps(topics), model, time.time()),
        )
        self.db.commit()


class PlainBillCache:
    def __init__(self, db: sqlite3.Connection):
        self.db = db

    def get(self, bill_url: str):
        row = self.db.execute("SELECT text, grounded FROM plain_bills WHERE bill_url=?", (bill_url,)).fetchone()
        return (row[0], bool(row[1])) if row else None

    def put(self, bill_url: str, text: str, grounded: bool, model: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO plain_bills VALUES (?,?,?,?,?)", (bill_url, text, int(grounded), model, time.time()))
        self.db.commit()
