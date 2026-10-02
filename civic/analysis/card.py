"""The MP 'baseball card': service, voting record, party-line record, bills, committees, chosen interests. All cited."""
from collections import Counter
from dataclasses import dataclass, field

from ..sources import openparliament as op

RECENT_VOTES = 40  # votes checked for party-line behaviour (each needs one cached request)


@dataclass
class VoteLine:
    url: str
    date: str
    description: str
    result: str
    ballot: str
    party_vote: str | None
    with_party: bool | None  # None when it can't be compared (paired, party had no clear position)
    topics: list[str] = field(default_factory=list)


@dataclass
class Card:
    mp: object  # sources.represent.MP
    profile: object  # analysis.profile.Profile
    slug: str | None
    photo_url: str | None
    mp_since: str | None
    session: str
    votes_total: int = 0
    ballots_cast: Counter = field(default_factory=Counter)
    recent: list[VoteLine] = field(default_factory=list)
    bills: list[op.Bill] = field(default_factory=list)
    bill_topics: dict = field(default_factory=dict)  # bill url -> topics
    notes: list[str] = field(default_factory=list)

    @property
    def attendance(self) -> float | None:
        return sum(self.ballots_cast.values()) / self.votes_total if self.votes_total else None

    @property
    def party_line(self) -> tuple[int, int]:
        """(votes with party, votes where comparison was possible) over the recent sample."""
        comparable = [v for v in self.recent if v.with_party is not None]
        return sum(1 for v in comparable if v.with_party), len(comparable)


def party_matches(party_name: str, short: str) -> bool:
    a, b = party_name.casefold(), short.casefold()
    return a == b or a.startswith(b) or b.startswith(a)


def compare(ballot: str, positions: dict, party_name: str) -> tuple[str | None, bool | None]:
    pos = next((v for k, v in positions.items() if party_matches(party_name, k)), None)
    if pos in ("Yes", "No") and ballot in ("Yes", "No"):
        return pos, ballot == pos
    return pos, None


def build_card(fetcher, mp, profile, slug, bills, session: str = "45-1", classifier=None) -> Card:
    card = Card(mp, profile, slug, None, None, session, bills=list(bills))
    if classifier:
        for b in card.bills:
            card.bill_topics[b.url] = classifier.classify(op.SITE + b.url, b.title)
    if not slug:
        card.notes.append("Could not match this MP to the voting-record site, so no voting data is shown.")
        return card
    info = op.politician(fetcher, slug)
    if info.get("image"):
        card.photo_url = op.SITE + info["image"]
    starts = [m["start_date"] for m in info.get("memberships", []) if m.get("start_date")]
    card.mp_since = min(starts) if starts else None
    ended = [m["end_date"] for m in info.get("memberships", []) if m.get("end_date")]
    open_now = any(not m.get("end_date") for m in info.get("memberships", []))
    if ended and not open_now:
        card.notes.append(
            f"openparliament.ca shows {mp.name}'s time as an MP ended on {max(ended)}. The lookup service may be out of date: "
            "the seat could be vacant or held by someone new. The record below is their past work, so check the official page before contacting them."
        )
    bl = op.ballots(fetcher, slug, session)
    card.ballots_cast = Counter(b.ballot for b in bl)
    card.votes_total = op.latest_vote_number(fetcher, session)
    for b in bl[:RECENT_VOTES]:
        d = op.vote_detail(fetcher, b.vote_url)
        pos, with_party = compare(b.ballot, d.party_positions, mp.party)
        card.recent.append(VoteLine(b.vote_url, d.date, d.description, d.result, b.ballot, pos, with_party))
    if classifier:
        for v in card.recent:
            v.topics = classifier.classify(op.SITE + v.url, v.description)
    return card
