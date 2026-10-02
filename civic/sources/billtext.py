"""Official bill text on parl.ca: pull the 'SUMMARY' Parliament writes at the top of each bill."""
import re
from html import unescape

from ..http import Fetcher


def looks_like_prose(text: str) -> bool:
    """Bills not yet through first reading show a table of contents under SUMMARY, not a real summary."""
    return not re.match(r"^\d+ ", text) and "Short Title" not in text[:300] and not text.startswith("First Session")


def parse_summary(html: str, limit: int = 1800) -> str | None:
    t = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.S | re.I)
    lines = [re.sub(r"\s+", " ", unescape(x)).strip() for x in re.sub(r"<[^>]+>", "\n", t).split("\n")]
    lines = [x for x in lines if x]
    for i, line in enumerate(lines):
        if line != "SUMMARY":
            continue
        nxt = lines[i + 1] if i + 1 < len(lines) else ""
        if nxt in ("SUMMARY", "TABLE OF PROVISIONS") or nxt.startswith("TABLE OF"):
            continue  # table-of-contents entry, not the summary itself
        body = []
        for x in lines[i + 1:]:
            if x.startswith(("Available on the House of Commons", "Also available", "TABLE OF", "BILL ")) or x.isupper() and len(x) > 8:
                break
            body.append(x)
        text = " ".join(body).strip()
        if len(text) > 40 and looks_like_prose(text):
            return text[:limit]
    return None


def fetch_summary(fetcher: Fetcher, text_url: str | None) -> str | None:
    if not text_url:
        return None
    return parse_summary(fetcher.get_text(text_url, max_age=30 * 86400))
