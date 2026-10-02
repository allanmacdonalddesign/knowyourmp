"""openparliament.ca: the historical record (House of Commons only)."""
import re
import unicodedata
from dataclasses import dataclass

from ..http import Fetcher

API = "https://api.openparliament.ca"
SITE = "https://openparliament.ca"


@dataclass(frozen=True)
class Speech:
    url: str  # path on openparliament.ca; link with SITE + url
    time: str
    h1: str | None
    h2: str | None
    text: str
    document_url: str | None


@dataclass(frozen=True)
class Bill:
    url: str
    number: str
    session: str
    title: str
    is_private_member_bill: bool
    status: str
    became_law: bool = False


def _en(value) -> str | None:
    if isinstance(value, dict):
        return value.get("en")
    return value


def slugify(name: str) -> str:
    base = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", base).strip("-")


def parl_id_from_url(ourcommons_url: str | None) -> str | None:
    m = re.search(r"\((\d+)\)", ourcommons_url or "")
    return m.group(1) if m else None


def find_slug(fetcher: Fetcher, name: str, parl_id: str | None = None) -> str | None:
    """Match an MP to their openparliament slug, verifying by House member id when we have it.

    The `?name=` filter misses some members (e.g. Steven Guilbeault), so also try the slugified name directly.
    Never guesses: returns None unless the name or the member id confirms the match.
    """
    candidates = []
    data = fetcher.get_json(f"{API}/politicians/", {"name": name, "format": "json"})
    candidates += [o["url"].strip("/").split("/")[-1] for o in data.get("objects", []) if o["name"].casefold() == name.casefold()]
    guess = slugify(name)
    if guess and guess not in candidates:
        candidates.append(guess)
    for slug in candidates:
        try:
            info = fetcher.get_json(f"{API}/politicians/{slug}/", {"format": "json"}, max_age=30 * 86400)
        except Exception:
            continue
        ids = (info.get("other_info") or {}).get("parl_mp_id") or []
        if parl_id and parl_id in ids:
            return slug
        if not parl_id and info.get("name", "").casefold() == name.casefold():
            return slug
    return None


def speeches(fetcher: Fetcher, slug: str, max_pages: int = 10, page_size: int = 100) -> list[Speech]:
    out: list[Speech] = []
    offset = 0
    for _ in range(max_pages):
        data = fetcher.get_json(
            f"{API}/speeches/",
            {"politician": slug, "format": "json", "limit": page_size, "offset": offset},
        )
        for o in data["objects"]:
            out.append(
                Speech(
                    url=o["url"],
                    time=o["time"],
                    h1=_en(o.get("h1")),
                    h2=_en(o.get("h2")),
                    text=_en(o.get("content")) or "",
                    document_url=o.get("document_url"),
                )
            )
        if not data["pagination"].get("next_url"):
            break
        offset += page_size
    return out


def sponsored_bills(fetcher: Fetcher, slug: str) -> list[Bill]:
    listing = fetcher.get_json(f"{API}/bills/", {"sponsor_politician": slug, "format": "json", "limit": 50})
    bills = []
    for o in listing["objects"]:
        d = fetcher.get_json(API + o["url"], {"format": "json"})
        bills.append(
            Bill(
                url=o["url"],
                number=d["number"],
                session=d["session"],
                title=_en(d["name"]) or "",
                is_private_member_bill=bool(d.get("private_member_bill")),
                status=_en(d.get("status")) or "",
                became_law=bool(d.get("law")),
            )
        )
    return bills


@dataclass(frozen=True)
class Ballot:
    vote_url: str
    ballot: str  # Yes / No / Paired


@dataclass(frozen=True)
class VoteDetail:
    url: str
    date: str
    description: str
    result: str
    bill_url: str | None
    party_positions: dict  # short party name -> "Yes" / "No" / ...


def politician(fetcher: Fetcher, slug: str) -> dict:
    return fetcher.get_json(f"{API}/politicians/{slug}/", {"format": "json"})


def ballots(fetcher: Fetcher, slug: str, session: str) -> list[Ballot]:
    """All ballots this MP cast in a session, newest first. Absences are not listed by the API."""
    data = fetcher.get_json(f"{API}/votes/ballots/", {"politician": slug, "format": "json", "limit": 1000})
    return [Ballot(o["vote_url"], o["ballot"]) for o in data["objects"] if f"/votes/{session}/" in o["vote_url"]]


def latest_vote_number(fetcher: Fetcher, session: str) -> int:
    data = fetcher.get_json(f"{API}/votes/", {"session": session, "format": "json", "limit": 1})
    return data["objects"][0]["number"] if data["objects"] else 0


def vote_detail(fetcher: Fetcher, vote_url: str) -> VoteDetail:
    d = fetcher.get_json(API + vote_url, {"format": "json"}, max_age=30 * 86400)
    return VoteDetail(
        vote_url, d["date"], _en(d["description"]) or "", d["result"], d.get("bill_url"),
        {_en(p["party"]["short_name"]): p["vote"] for p in d.get("party_votes", [])},
    )
