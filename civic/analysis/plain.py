"""Plain-language descriptions of bills, grounded in the official title and Parliament's own summary."""
import json
import re
import time

from ..cache import PlainBillCache
from ..config import CLASSIFIER_MODEL
from ..sources import billtext
from ..sources import openparliament as op
from .classify import reply_text


def _prompt(info: op.BillInfo, summary: str | None) -> str:
    return f"""Explain what this Canadian bill does in ONE plain-English sentence of at most 25 words, for someone with no legal background.

Rules:
- Use only the information below. Do not add facts from memory.
- Say what the bill does, not whether it is good or bad. Neutral, no loaded words.
- No legal jargon, no "An Act", no bill number.
- Start with a verb in the third person (e.g. "Removes...", "Creates...", "Makes...", "Sets...").

Official title: {info.title}
Common name: {info.short_title or "(none)"}
Official summary written by Parliament: {summary or "(not available: base your sentence only on the title)"}

Reply with only the sentence."""


class BillExplainer:
    def __init__(self, client, fetcher, cache: PlainBillCache):
        self.client, self.fetcher, self.cache = client, fetcher, cache

    def explain(self, info: op.BillInfo) -> tuple[str, bool]:
        """Returns (sentence, grounded_in_official_summary). Cached per bill."""
        hit = self.cache.get(info.url)
        if hit and usable(hit[0]):
            return hit
        summary = billtext.fetch_summary(self.fetcher, info.text_url)
        resp = self.client.messages.create(
            model=CLASSIFIER_MODEL, max_tokens=200, messages=[{"role": "user", "content": _prompt(info, summary)}]
        )
        text = reply_text(resp).strip().strip('"')
        if not usable(text):
            return fallback(info), False  # never show a refusal; the official title is honest if less friendly
        self.cache.put(info.url, text, bool(summary), CLASSIFIER_MODEL)
        return text, bool(summary)


REFUSAL_MARKERS = ("i don't", "i do not", "i cannot", "i can't", "unable to", "not available", "no information", "don't have access", "as an ai")


def usable(text: str) -> bool:
    """A real one-sentence description, not a refusal or a rambling answer."""
    t = text.strip()
    return 15 <= len(t) <= 220 and not any(m in t.lower() for m in REFUSAL_MARKERS) and "\n" not in t


def fallback(info: op.BillInfo) -> str:
    """No API key: still better than nothing, and honest that it is the official title."""
    return info.short_title or info.title


# ---------------------------------------------------------------- "make it human" rewrites (optional, AI)
HUMAN_PROMPT = """Rewrite each bill description below the way a friend would explain it over coffee: everyday words, one sentence, at most 25 words.

Rules:
- Keep the meaning exactly. Use only what the description and official title say; add no facts, numbers or examples from memory.
- Say what the bill does, not whether it is good or bad. Neutral: no opinions, no loaded words, no jokes, no "you should".
- No legal jargon, no bill numbers, no "An Act".

Bills (each has an id in brackets):
{listing}

Reply with only JSON: {{"b1": "sentence", "b2": "sentence", ...}}"""


class HumanBillCache:
    """Everyday-language rewrites, one per bill, kept forever (the source sentence for a bill does not change)."""

    def __init__(self, db):
        self.db = db
        db.execute("CREATE TABLE IF NOT EXISTS human_bills (bill_url TEXT PRIMARY KEY, text TEXT, model TEXT, created_at REAL)")

    def get(self, bill_url: str) -> str | None:
        row = self.db.execute("SELECT text FROM human_bills WHERE bill_url=?", (bill_url,)).fetchone()
        return row[0] if row else None

    def put(self, bill_url: str, text: str, model: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO human_bills VALUES (?,?,?,?)", (bill_url, text, model, time.time()))
        self.db.commit()


class Humanizer:
    def __init__(self, client, cache: HumanBillCache):
        self.client, self.cache = client, cache

    def rewrite(self, bills: list[tuple[str, str, str]]) -> dict[str, str]:
        """bills: (url, plain sentence, official title). Returns url -> rewrite; bills that fail validation are left out."""
        out = {url: hit for url, _, _ in bills if (hit := self.cache.get(url))}
        todo = [(url, text, title) for url, text, title in bills if url not in out]
        if not todo:
            return out
        ids = {f"b{i}": b for i, b in enumerate(todo, 1)}
        listing = "\n".join(f"[{k}] {text} (official title: {title})" for k, (_, text, title) in ids.items())
        resp = self.client.messages.create(
            model=CLASSIFIER_MODEL, max_tokens=4000, messages=[{"role": "user", "content": HUMAN_PROMPT.format(listing=listing)}]
        )
        for k, text in parse_rewrites(reply_text(resp)).items():
            if k in ids and usable(text):
                url = ids[k][0]
                out[url] = text.strip().strip('"')
                self.cache.put(url, out[url], CLASSIFIER_MODEL)
        return out


def parse_rewrites(reply: str) -> dict[str, str]:
    m = re.search(r"\{.*\}", reply, flags=re.S)
    if not m:
        return {}
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(raw, dict) else {}
