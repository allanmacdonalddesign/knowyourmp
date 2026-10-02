"""openparliament.ca: the historical record (House of Commons only)."""
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


def _en(value) -> str | None:
    if isinstance(value, dict):
        return value.get("en")
    return value


def find_slug(fetcher: Fetcher, name: str) -> str | None:
    data = fetcher.get_json(f"{API}/politicians/", {"name": name, "format": "json"})
    objs = data.get("objects", [])
    # The name filter can be loose; require an exact (case-insensitive) match.
    exact = [o for o in objs if o["name"].casefold() == name.casefold()]
    return exact[0]["url"].strip("/").split("/")[-1] if len(exact) == 1 else None


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
            )
        )
    return bills
