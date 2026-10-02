"""Represent API (Open North): postal code -> MP(s)."""
import re
from dataclasses import dataclass

from ..http import Fetcher

BASE = "https://represent.opennorth.ca"


@dataclass(frozen=True)
class MP:
    name: str
    party: str
    riding: str
    email: str | None
    ourcommons_url: str | None
    offices: tuple[dict, ...] = ()


class InvalidPostalCode(ValueError):
    pass


def normalize(postal: str) -> str:
    code = re.sub(r"\s+", "", postal).upper()
    if not re.fullmatch(r"[A-Z]\d[A-Z]\d[A-Z]\d", code):
        raise InvalidPostalCode(f"{postal!r} is not a valid Canadian postal code")
    return code


def parse_mps(data: dict) -> list[MP]:
    """Collect MPs from both centroid and concordance lists, deduped by (name, riding).

    More than one result means the postal code straddles ridings; callers must ask the user.
    """
    seen: dict[tuple[str, str], MP] = {}
    for key in ("representatives_centroid", "representatives_concordance"):
        for r in data.get(key, []):
            if r.get("elected_office") != "MP":
                continue
            mp = MP(
                name=r["name"],
                party=r.get("party_name", ""),
                riding=r.get("district_name", ""),
                email=r.get("email"),
                ourcommons_url=r.get("url"),
                offices=tuple(r.get("offices", [])),
            )
            seen.setdefault((mp.name, mp.riding), mp)
    return list(seen.values())


def lookup(fetcher: Fetcher, postal: str) -> list[MP]:
    code = normalize(postal)
    return parse_mps(fetcher.get_json(f"{BASE}/postcodes/{code}/"))
