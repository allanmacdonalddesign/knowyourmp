"""Opportunities and a transparent leverage score. Every point comes with a plain-language reason."""
import re
from dataclasses import dataclass, field
from datetime import date

from ..sources import committees, legisinfo, petitions


@dataclass
class Opportunity:
    kind: str  # "committee_study" | "bill" | "petition"
    title: str
    url: str
    topics: list[str]
    detail: str
    action: str
    deadline: date | None = None
    score: int = 0
    reasons: list[str] = field(default_factory=list)


def from_study(s: committees.Study, topics: list[str]) -> Opportunity:
    bits = []
    if s.briefs is not None:
        bits.append(f"{s.briefs} briefs" + (f" and {s.witnesses} witnesses" if s.witnesses is not None else "") + " so far")
    if s.brief_limit:
        bits.append(s.brief_limit)
    return Opportunity(
        "committee_study", f"{s.code}: {s.title}", s.url, topics, "; ".join(bits),
        "Submit a short written brief to the committee, and email the committee members (not only your own MP). "
        "Use the study page for how to submit.",
        s.deadline,
    )


def from_bill(b: legisinfo.LegisBill, topics: list[str]) -> Opportunity:
    kind = "private member's bill" if b.is_private_member else "government bill"
    if b.status == legisinfo.COMMITTEE:
        action = "The bill is in committee: ask the committee (and your MP) for a specific amendment or to hear witnesses."
    elif b.is_private_member:
        action = "Private members' bills often get free votes: write your MP a personal letter asking for their vote and why."
    else:
        action = "Whipped vote likely: a personal letter to your MP is low leverage; consider contacting the committee or a minister's office instead."
    return Opportunity("bill", f"Bill {b.number}: {b.title}", b.url, topics, f"{kind}; {b.status}", action)


def from_petition(p: petitions.Petition, text: str, topics: list[str]) -> Opportunity:
    first = re.sub(r"^We, the undersigned,.*?call upon [^:]*?:\s*(\d\.\s*)?", "", text, flags=re.I)[:140]
    detail = f"{p.signatures} signatures (sponsor: {p.sponsor})"
    action = "Read and sign on the House of Commons petitions site."
    if p.signatures >= petitions.THRESHOLD:
        detail += "; already past the 500 needed for a government response"
    else:
        action += f" It needs {petitions.THRESHOLD - p.signatures} more for a mandatory government response; share it with people it affects."
    return Opportunity("petition", f"Petition {p.id}: {first or p.category}", p.url, topics, detail, action, p.closes)


def score(o: Opportunity, user_topics: set[str], mp_topics: set[str], my_committees: set[str],
          today: date, p: petitions.Petition | None = None, s: committees.Study | None = None,
          b: legisinfo.LegisBill | None = None) -> Opportunity:
    pts: list[tuple[int, str]] = []
    topics = set(o.topics) - {"other"}
    mine = topics & user_topics
    if mine:
        pts.append((40, f"matches your interest in {', '.join(sorted(mine))}"))
    ally = mine & mp_topics  # only count the MP's interests when they overlap the user's too
    if ally:
        pts.append((20, f"your MP has chosen to speak or sponsor on {', '.join(sorted(ally))}, so you'd be arming an ally"))

    if o.kind == "committee_study":
        pts.append((30, "committee stage with an open call for briefs, where anyone can influence the outcome"))
        if s and s.code in my_committees:
            pts.append((10, f"your MP sits on {s.code}"))
        if s and s.briefs is not None and s.briefs <= 10:
            pts.append((10, f"few briefs so far ({s.briefs})"))
    elif o.kind == "bill" and b:
        if b.status == legisinfo.COMMITTEE:
            pts.append((20 if b.is_private_member else 15, "bill is at committee, where amendments happen"))
        elif b.is_private_member:
            pts.append((20, "private members' bills often get free votes"))
        else:
            pts.append((5, "government bill at a late stage; whipped votes rarely change"))
    elif o.kind == "petition" and p:
        if p.signatures >= petitions.THRESHOLD:
            pts.append((5, f"already has the 500 signatures that force a government response ({p.signatures}), so your signature adds less"))
        else:
            pts.append((15, "e-petition: signatures are the direct action"))
        if 300 <= p.signatures < petitions.THRESHOLD:
            pts.append((15, f"close to the 500 needed for a government response ({p.signatures})"))
        elif 100 <= p.signatures < 300:
            pts.append((8, f"{p.signatures} signatures, still a long way from 500"))

    if o.deadline:
        days = (o.deadline - today).days
        if days < 0:
            o.score, o.reasons = -1, ["deadline has passed"]
            return o
        if days <= 14:
            pts.append((15, f"deadline in {days} days"))
        elif days <= 45:
            pts.append((10, f"deadline in {days} days"))
        else:
            pts.append((5, f"deadline in {days} days"))
    o.score = sum(p_ for p_, _ in pts)
    o.reasons = [r for _, r in pts]
    return o
