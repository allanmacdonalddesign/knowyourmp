"""Tag speeches/bills against the fixed taxonomy in topics.json using Claude. Cached per source URL."""
import json
import re

from ..cache import ClassificationCache
from ..config import CLASSIFIER_MODEL, TOPICS_PATH


def load_taxonomy() -> dict[str, str]:
    return json.loads(TOPICS_PATH.read_text())


def strip_html(text: str, limit: int = 1500) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()[:limit]


def reply_text(resp) -> str:
    """Join the text blocks of a reply, ignoring thinking or other block types."""
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "text") == "text").strip()


def _prompt(text: str, taxonomy: dict[str, str]) -> str:
    topics = "\n".join(f"- {k}: {v}" for k, v in taxonomy.items())
    return (
        "Classify the parliamentary text below into at most two topics from this fixed list.\n"
        f"{topics}\n\n"
        'Reply with only a JSON array of topic keys, e.g. ["housing"]. Use ["other"] if none fit.\n\n'
        f"Text:\n{text}"
    )


def parse_topics(reply: str, taxonomy: dict[str, str]) -> list[str]:
    m = re.search(r"\[.*?\]", reply, flags=re.S)
    if not m:
        return ["other"]
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        return ["other"]
    valid = [t for t in raw if t in taxonomy]
    return valid[:2] or ["other"]


class Classifier:
    """`client` is an anthropic.Anthropic (or any object with .messages.create). Never re-classifies a cached URL."""

    def __init__(self, client, cache: ClassificationCache, taxonomy: dict[str, str] | None = None):
        self.client = client
        self.cache = cache
        self.taxonomy = taxonomy or load_taxonomy()

    def classify(self, source_url: str, text: str) -> list[str]:
        cached = self.cache.get(source_url)
        if cached is not None:
            return cached
        resp = self.client.messages.create(
            model=CLASSIFIER_MODEL,
            max_tokens=60,
            messages=[{"role": "user", "content": _prompt(strip_html(text), self.taxonomy)}],
        )
        topics = parse_topics(reply_text(resp), self.taxonomy)
        self.cache.put(source_url, topics, CLASSIFIER_MODEL)
        return topics
