"""Build an MP profile: 'Responsible for' (assigned) vs 'Personally champions' (chosen). Every claim has a source URL."""
import re
from collections import Counter
from dataclasses import dataclass, field

from ..sources import openparliament as op
from ..sources.ourcommons_member import MemberRoles

MEMBERS_STATEMENTS_H1 = "Statements by Members"


@dataclass
class Claim:
    text: str
    url: str
    topics: list[str] = field(default_factory=list)
    quote: str = ""  # short excerpt for letters; empty for roles and bills


@dataclass
class Profile:
    name: str
    riding: str
    party: str
    responsible_for: list[Claim]
    champions: list[Claim]
    assigned_activity: Counter  # light-weight context: where else they speak
    topic_counts: Counter  # from chosen signals only
    notes: list[str]


def build_profile(mp, slug: str | None, roles: MemberRoles | None, speeches, bills, classifier=None) -> Profile:
    notes: list[str] = []
    responsible: list[Claim] = []
    if roles:
        for r in roles.roles:
            responsible.append(Claim(r, mp.ourcommons_url or ""))
        for code, name in roles.committees:
            responsible.append(Claim(f"Member, {name} ({code})", mp.ourcommons_url or ""))
    else:
        notes.append("Roles unavailable (member page could not be read).")

    champions: list[Claim] = []
    for b in bills:
        if not b.is_private_member_bill:
            continue
        c = Claim(f"Sponsored Bill {b.number}: {b.title} [{b.status}]", op.SITE + b.url)
        champions.append(c)
    for s in speeches:
        if s.h1 == MEMBERS_STATEMENTS_H1:
            champions.append(Claim(f"Members' statement ({s.time[:10]}): {s.h2 or 'untitled'}", op.SITE + s.url,
                                   quote=re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s.text)).strip()[:400]))
    if classifier:
        for c in champions:
            source_text = c.text
            if "statement" in c.text.lower():
                match = next((s for s in speeches if op.SITE + s.url == c.url), None)
                if match:
                    source_text = f"{match.h2}\n{match.text}"
            c.topics = classifier.classify(c.url, source_text)
    else:
        notes.append("Topics not tagged (no ANTHROPIC_API_KEY set); showing cited items only.")

    if not champions:
        notes.append("No members' statements or sponsored private members' bills found, so no 'champions' signal.")

    assigned = Counter(s.h1 or "Committee" for s in speeches if s.h1 != MEMBERS_STATEMENTS_H1)
    topics = Counter(t for c in champions for t in c.topics if t != "other")
    return Profile(mp.name, mp.riding, mp.party, responsible, champions, assigned, topics, notes)
