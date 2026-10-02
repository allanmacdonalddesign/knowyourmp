"""Open e-petitions from the House of Commons.

Uses ONLY the unfiltered default search the site's own page makes; the reCAPTCHA-gated XML/CSV export
and filtered searches are deliberately not used (see docs/data-notes.md). Scraping lives here only.
"""
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from html import unescape

from ..http import Fetcher

BASE = "https://www.ourcommons.ca/petitions/en/Petition"
THRESHOLD = 500


@dataclass(frozen=True)
class Petition:
    id: str
    category: str
    keywords: tuple[str, ...]
    closes: date | None
    sponsor: str
    signatures: int
    url: str


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def parse_list(fragment: str) -> list[Petition]:
    out = []
    for row in re.findall(r'<tr class="Pub".*?</tr>', fragment, flags=re.S):
        tds = re.findall(r"<td.*?>(.*?)</td>", row, flags=re.S)
        m = re.search(r'Details\?Petition=(e-\d+)', row)
        if len(tds) < 6 or not m:
            continue
        pid = m.group(1)
        category = _clean(re.sub(r'<span class="spTitle">.*?</span>', "", tds[0]))
        keywords = tuple(_clean(k) for k in re.findall(r"<a [^>]*>(.*?)</a>", tds[1], flags=re.S))
        status = _clean(tds[3])
        dm = re.search(r"until ([A-Z][a-z]+ \d{1,2}, \d{4})", status)
        closes = datetime.strptime(dm.group(1), "%B %d, %Y").date() if dm else None
        if "Open for signature" not in status:
            continue
        sig = re.sub(r"\D", "", _clean(tds[5]))
        out.append(Petition(pid, category, keywords, closes, _clean(tds[4]), int(sig or 0), f"{BASE}/Details?Petition={pid}"))
    return out


def fetch_open(fetcher: Fetcher, max_pages: int = 10) -> list[Petition]:
    seen: dict[str, Petition] = {}
    for page in range(1, max_pages + 1):
        raw = fetcher.post_text(f"{BASE}/SearchAsync", {"reCaptchaAction": "SEARCH"}, {"Page": page, "RPP": 20})
        rows = parse_list(json.loads(raw)["html"])
        new = [r for r in rows if r.id not in seen]
        if not new:
            break
        seen.update({r.id: r for r in new})
    return list(seen.values())


def parse_detail_text(html: str) -> str:
    """The petitioners' request: from 'We, the undersigned' to the 'History' block."""
    t = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.S | re.I)
    t = _clean(re.sub(r"<[^>]+>", "|", t))
    i = t.find("We, the undersigned")
    j = t.find("History", i)
    return re.sub(r"\s*\|\s*", " ", t[i:j] if i >= 0 else "").strip()


def fetch_text(fetcher: Fetcher, p: Petition) -> str:
    return parse_detail_text(fetcher.get_text(p.url, max_age=7 * 86400))
