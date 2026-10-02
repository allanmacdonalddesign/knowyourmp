"""The MP 'baseball card': service, plain-language stance, party-line record, bills, committees. All cited."""
from collections import Counter
from dataclasses import dataclass, field

from ..sources import openparliament as op
from . import overview as overview_mod
from . import plain, stance

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
    bill_plain: dict = field(default_factory=dict)  # bill url -> plain sentence
    key_votes: list[stance.KeyVote] = field(default_factory=list)
    other_votes: int = 0
    overview: list[dict] = field(default_factory=list)  # [{"text", "refs": [ids]}]
    ref_links: dict = field(default_factory=dict)  # id -> (label, url)
    notes: list[str] = field(default_factory=list)

    @property
    def attendance(self) -> float | None:
        return sum(self.ballots_cast.values()) / self.votes_total if self.votes_total else None

    @property
    def party_line(self) -> tuple[int, int]:
        """(votes with party, votes where comparison was possible) over the recent sample."""
        comparable = [v for v in self.recent if v.with_party is not None]
        return sum(1 for v in comparable if v.with_party), len(comparable)

    @property
    def backed(self):
        return [v for v in self.key_votes if v.ballot == "Yes"]

    @property
    def opposed(self):
        return [v for v in self.key_votes if v.ballot == "No"]


def party_matches(party_name: str, short: str) -> bool:
    a, b = party_name.casefold(), short.casefold()
    return a == b or a.startswith(b) or b.startswith(a)


def compare(ballot: str, positions: dict, party_name: str) -> tuple[str | None, bool | None]:
    pos = next((v for k, v in positions.items() if party_matches(party_name, k)), None)
    if pos in ("Yes", "No") and ballot in ("Yes", "No"):
        return pos, ballot == pos
    return pos, None


def build_card(fetcher, mp, profile, slug, bills, session: str = "45-1", classifier=None, explainer=None, llm=None) -> Card:
    """`classifier`/`explainer`/`llm` are optional: without an API key the card still shows cited facts."""
    card = Card(mp, profile, slug, None, None, session, bills=list(bills))
    if not slug:
        card.notes.append("Could not match this MP to the voting-record site, so no voting data is shown.")
        return card
    info = op.politician(fetcher, slug)
    if info.get("image"):
        card.photo_url = op.SITE + info["image"]
    starts = [m["start_date"] for m in info.get("memberships", []) if m.get("start_date")]
    card.mp_since = min(starts) if starts else None
    ended = [m["end_date"] for m in info.get("memberships", []) if m.get("end_date")]
    if ended and not any(not m.get("end_date") for m in info.get("memberships", [])):
        card.notes.append(
            f"openparliament.ca shows {mp.name}'s time as an MP ended on {max(ended)}. The lookup service may be out of date: "
            "the seat could be vacant or held by someone new. The record below is their past work, so check the official page before contacting them."
        )
    bl = op.ballots(fetcher, slug, session)
    card.ballots_cast = Counter(b.ballot for b in bl)
    card.votes_total = op.latest_vote_number(fetcher, session)

    # party-line record on the most recent votes
    for b in bl[:RECENT_VOTES]:
        d = op.vote_detail(fetcher, b.vote_url)
        pos, with_party = compare(b.ballot, d.party_positions, mp.party)
        card.recent.append(VoteLine(b.vote_url, d.date, d.description, d.result, b.ballot, pos, with_party))

    # plain-language: bills they sponsored, and bills they voted on at 2nd/3rd reading
    for b in card.bills:
        bi = op.bill_info(fetcher, b.url)
        card.bill_plain[b.url] = explainer.explain(bi)[0] if explainer else plain.fallback(bi)
    picked, card.other_votes = stance.select_key_votes(op.votes_list(fetcher, session), {b.vote_url: b.ballot for b in bl})
    for v, ballot in picked:
        bi = op.bill_info(fetcher, v.bill_url)
        text, grounded = explainer.explain(bi) if explainer else (plain.fallback(bi), False)
        card.key_votes.append(stance.KeyVote(v.bill_url, bi.number, bi.title, text, grounded, stance.stage_of(v.description),
                                             ballot, v.result, v.date, v.url))
    if classifier:
        for b in card.bills:
            card.bill_topics[b.url] = classifier.classify(op.SITE + b.url, card.bill_plain[b.url])
        for kv in card.key_votes:
            kv.topics = classifier.classify(op.SITE + kv.bill_url, kv.plain)

    card.overview, card.ref_links = _overview(card, llm)
    return card


def _overview(card: Card, llm) -> tuple[list[dict], dict]:
    items: dict[str, str] = {}
    links: dict[str, tuple[str, str]] = {}
    for i, v in enumerate(card.key_votes[:20], 1):
        k = f"v{i}"
        items[k] = f"Voted {'FOR' if v.ballot == 'Yes' else 'AGAINST'} (at {v.stage}): {v.plain}"
        links[k] = (f"Bill {v.number} vote", op.SITE + v.vote_url)
    for i, b in enumerate(card.bills[:8], 1):
        k = f"b{i}"
        items[k] = f"Sponsored a bill ({b.status}): {card.bill_plain.get(b.url, b.title)}"
        links[k] = (f"Bill {b.number}", op.SITE + b.url)
    stmts = [c for c in card.profile.champions if c.quote]
    for i, c in enumerate(stmts[:12], 1):
        k = f"s{i}"
        items[k] = f"Chose to speak about: {c.text.split(': ', 1)[-1]}" + (f" [{', '.join(c.topics)}]" if c.topics else "")
        links[k] = (c.text.split(":")[0], c.url)
    y, n = len(card.backed), len(card.opposed)
    stats = (f"{y} bills voted for and {n} against at 2nd/3rd reading this session; "
             f"{card.party_line[0]} of {card.party_line[1]} recent votes with their party.")
    sentences = overview_mod.generate(llm, card.mp.name, card.mp.party, items, stats)
    return sentences, links
