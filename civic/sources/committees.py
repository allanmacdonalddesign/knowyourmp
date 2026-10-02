"""House committees currently seeking input (calls for briefs). HTML scraping isolated here."""
import re
from dataclasses import dataclass
from datetime import date, datetime
from html import unescape

from ..http import Fetcher

SITE = "https://www.ourcommons.ca"
PARTICIPATE = f"{SITE}/Committees/en/Participate"


@dataclass(frozen=True)
class Study:
    code: str
    committee: str
    title: str
    url: str
    deadline: date | None = None
    briefs: int | None = None
    witnesses: int | None = None
    brief_limit: str | None = None


def _text(html: str) -> str:
    t = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.S | re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "|", t)))


def parse_participate(html: str) -> list[Study]:
    out = []
    for m in re.finditer(r'<a class="study-title" href="(/[Cc]ommittees/en/(\w+)/StudyActivity\?studyActivityId=\d+)"[^>]*>(.*?)</a>', html, flags=re.S):
        title = re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", m.group(3)))).strip()
        out.append(Study(m.group(2), "", title, SITE + m.group(1)))
    return out


def parse_study(html: str, base: Study) -> Study:
    t = _text(html)
    dl = re.search(r"Submit a brief[\s|]*before [^|]*? on \w+, ([A-Z][a-z]+ \d{1,2}, \d{4})", t)
    deadline = datetime.strptime(dl.group(1), "%B %d, %Y").date() if dl else None
    briefs = re.search(r"Briefs \((\d+)\)", t)
    witnesses = re.search(r"Witnesses \((\d+)\)", t)
    limit = re.search(r"(Briefs should not exceed[^|]*)", t)
    return Study(
        base.code, base.committee, base.title, base.url, deadline,
        int(briefs.group(1)) if briefs else None,
        int(witnesses.group(1)) if witnesses else None,
        limit.group(1).strip() if limit else None,
    )


def fetch_open_studies(fetcher: Fetcher) -> list[Study]:
    studies = parse_participate(fetcher.get_text(PARTICIPATE))
    return [parse_study(fetcher.get_text(s.url, max_age=6 * 3600), s) for s in studies]
