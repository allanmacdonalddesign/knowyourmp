"""Plain-language descriptions of bills, grounded in the official title and Parliament's own summary."""
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
