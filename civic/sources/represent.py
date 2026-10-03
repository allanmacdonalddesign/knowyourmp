"""Represent API (Open North): postal code or name -> MP(s)."""
import re
import unicodedata
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


class InvalidName(ValueError):
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
    # Never cached: the URL contains the postal code, which we promise not to store.
    return parse_mps(fetcher.get_json(f"{BASE}/postcodes/{code}/", cache=False))


def _mp_from(r: dict) -> MP:
    return MP(name=r["name"], party=r.get("party_name", ""), riding=r.get("district_name", ""), email=r.get("email"),
              ourcommons_url=r.get("url"), offices=tuple(r.get("offices", [])))


def _fold(text: str) -> str:
    """Lowercase, accents and punctuation removed, so 'Rene Cote' finds 'René Côté' and 'O Regan' finds \"O'Regan\"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]+", " ", plain.casefold())


def match_name(data: dict, query: str) -> list[MP]:
    """MPs whose name contains every word of the query (any order). An exact full-name match wins outright."""
    words = _fold(query).split()
    if not words:
        raise InvalidName("Please type an MP's name.")
    mps = [_mp_from(r) for r in data.get("objects", []) if r.get("elected_office") == "MP"]
    exact = [m for m in mps if _fold(m.name).split() == words]
    return exact or [m for m in mps if all(w in _fold(m.name) for w in words)]


def search(fetcher: Fetcher, query: str) -> list[MP]:
    # The roster is public and the same for everyone, so unlike postal codes it is safe to cache.
    return match_name(fetcher.get_json(f"{BASE}/representatives/house-of-commons/?limit=500&format=json"), query)
