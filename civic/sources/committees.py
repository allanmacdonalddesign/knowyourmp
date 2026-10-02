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


@dataclass(frozen=True)
class Submission:
    form_url: str | None
    conditions: list[str]
    guide_url: str | None
    clerk_url: str | None


@dataclass(frozen=True)
class CommitteeMember:
    name: str
    role: str
    party: str
    riding: str


def parse_submission(study_html: str, form_html: str | None) -> Submission:
    m = re.search(r'href="(/committee-participation/en/submit-brief/[^"]+)"', study_html)
    form_url = SITE + m.group(1) if m else None
    conditions: list[str] = []
    guide = clerk = None
    if form_html:
        t = _text(form_html)
        a = t.find("Conditions for submission")
        b = t.find("Your contact information")
        if a >= 0 and b > a:
            body = re.sub(r"\|", " ", t[a + len("Conditions for submission"):b])
            conditions = [x.strip() for x in re.split(r"(?<=\.)\s+", body) if x.strip()]
        g = re.search(r'href="([^"]*)"[^>]*>\s*Guide for Submitting Briefs', form_html)
        guide = (SITE + g.group(1) if g.group(1).startswith("/") else g.group(1)) if g else None
        c = re.search(r'href="([^"]*)"[^>]*>\s*Clerk of the committee', form_html)
        clerk = (SITE + c.group(1) if c.group(1).startswith("/") else c.group(1)) if c else None
        clerk = clerk.replace("//www.", "https://www.") if clerk and clerk.startswith("//") else clerk
    return Submission(form_url, conditions, guide, clerk)


def fetch_submission(fetcher: Fetcher, study: Study) -> Submission:
    study_html = fetcher.get_text(study.url, max_age=6 * 3600)
    m = re.search(r'href="(/committee-participation/en/submit-brief/[^"]+)"', study_html)
    form_html = fetcher.get_text(SITE + m.group(1), max_age=6 * 3600) if m else None
    return parse_submission(study_html, form_html)


def parse_members(html: str) -> list[CommitteeMember]:
    """Entries appear as 5 consecutive text runs (first, last, party, riding, province), each listed twice."""
    t = unescape(re.sub(r"<(script|style).*?</\1>", "", html, flags=re.S | re.I))
    runs = [r.strip() for r in re.sub(r"<[^>]+>", "\n", t).split("\n") if r.strip()]
    out: list[CommitteeMember] = []
    headers = {"Chair": "Chair", "Vice-Chairs": "Vice-Chair", "Members": "Member"}
    role = None
    i = 0
    while i < len(runs):
        r = runs[i]
        if r in headers:
            role = headers[r]
            i += 1
            continue
        if role and i + 4 < len(runs) and runs[i + 5 : i + 7] == runs[i : i + 2] if i + 6 < len(runs) else False:
            m = CommitteeMember(f"{runs[i]} {runs[i + 1]}", role, runs[i + 2], runs[i + 3])
            if m not in out:
                out.append(m)
            i += 10
            continue
        i += 1
    return out


def fetch_members(fetcher: Fetcher, code: str) -> list[CommitteeMember]:
    return parse_members(fetcher.get_text(f"{SITE}/Committees/en/{code}/Members", max_age=DAY_S))


DAY_S = 86400
