"""What an MP backed and opposed: only votes that decided a bill (2nd/3rd reading), in plain language."""
import re
from dataclasses import dataclass, field

from ..sources import openparliament as op

STAGE_RE = re.compile(r"^(2nd|3rd) reading", re.I)
MAX_BILLS = 30  # keeps the first load bounded; each bill needs one text fetch and one explanation


@dataclass
class KeyVote:
    bill_url: str
    number: str
    legal_title: str
    plain: str
    grounded: bool  # plain sentence was based on Parliament's official summary
    stage: str  # "2nd reading" / "3rd reading"
    ballot: str  # Yes / No
    result: str
    date: str
    vote_url: str
    topics: list[str] = field(default_factory=list)


def select_key_votes(votes: list[op.VoteSummary], ballots: dict[str, str]) -> tuple[list[tuple[op.VoteSummary, str]], int]:
    """One entry per bill (prefer the 3rd reading vote), newest first. Returns (picked, count of other votes).

    Amendments, procedural motions, supply and the like are not bill-passage votes, so they are counted, not described.
    """
    per_bill: dict[str, tuple[op.VoteSummary, str]] = {}
    for v in votes:  # newest first
        b = ballots.get(v.url)
        m = STAGE_RE.match(v.description)
        if not (b in ("Yes", "No") and m and v.bill_url):
            continue
        cur = per_bill.get(v.bill_url)
        if cur is None or (m.group(1) == "3rd" and not cur[0].description.lower().startswith("3rd")):
            per_bill[v.bill_url] = (v, b)
    picked = sorted(per_bill.values(), key=lambda x: x[0].number, reverse=True)
    other = max(0, len(ballots) - len(picked))
    return picked[:MAX_BILLS], other


def stage_of(description: str) -> str:
    m = STAGE_RE.match(description)
    return f"{m.group(1)} reading" if m else "vote"
