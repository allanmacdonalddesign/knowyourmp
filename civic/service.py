"""Shared by the CLI and the web UI: rank opportunities, build a brief guide, draft a letter."""
import os
import re
from dataclasses import dataclass
from datetime import date

from . import cache
from .actions import brief_guide, letter
from .analysis import classify, profile as prof
from .analysis.interests import resolve
from .http import Fetcher
from .ranking import opportunities as opp
from .sources import committees, legisinfo, petitions, represent
from .sources import openparliament as op
from .sources import ourcommons_member


class UserError(Exception):
    """A problem the user can fix; the message is safe to show."""


class SplitPostcode(UserError):
    def __init__(self, mps):
        super().__init__("This postal code covers more than one riding. Please choose yours.")
        self.mps = mps


@dataclass
class Ranked:
    mp: represent.MP
    profile: prof.Profile
    roles: object
    shown: list
    fetcher: Fetcher


def classifier(db):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic

    return classify.Classifier(anthropic.Anthropic(), cache.ClassificationCache(db))


def find_mp(fetcher, postal_code: str, pick: int | None = None):
    try:
        mps = represent.lookup(fetcher, postal_code)
    except represent.InvalidPostalCode as e:
        raise UserError(str(e))
    if not mps:
        raise UserError("No MP found for that postal code.")
    if len(mps) > 1:
        if pick is None or not 1 <= pick <= len(mps):
            raise SplitPostcode(mps)
        return mps[pick - 1]
    return mps[0]


def mp_context(db, fetcher, mp):
    slug = op.find_slug(fetcher, mp.name, op.parl_id_from_url(mp.ourcommons_url))
    roles = ourcommons_member.fetch_roles(fetcher, mp.ourcommons_url) if mp.ourcommons_url else None
    speeches = op.speeches(fetcher, slug) if slug else []
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    return prof.build_profile(mp, slug, roles, speeches, bills, classifier(db)), slug, roles


def rank(postal_code: str, interests: str, pick: int | None = None, show_all: bool = False) -> Ranked:
    try:
        wanted = resolve(interests)
    except ValueError as e:
        raise UserError(str(e))
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    clf = classifier(db)
    if clf is None:
        raise UserError("Set ANTHROPIC_API_KEY: opportunities are matched to your interests by topic tagging.")
    mp = find_mp(fetcher, postal_code, pick)
    profile, _, roles = mp_context(db, fetcher, mp)
    mp_topics = set(profile.topic_counts)
    my_committees = {code for code, _ in roles.committees} if roles else set()
    today = date.today()

    scored: list[opp.Opportunity] = []
    studies = committees.fetch_open_studies(fetcher)
    study_bills = {m.group(0) for s in studies if (m := re.search(r"Bill [CS]-\d+", s.title))}
    for s in studies:
        scored.append(opp.score(opp.from_study(s, clf.classify(s.url, s.title)), wanted, mp_topics, my_committees, today, s=s))
    for b in legisinfo.fetch_active(fetcher):
        if f"Bill {b.number}" in study_bills:
            continue  # already shown as an open committee study
        scored.append(opp.score(opp.from_bill(b, clf.classify(b.url, b.title)), wanted, mp_topics, my_committees, today, b=b))
    for p in petitions.fetch_open(fetcher):
        text = petitions.fetch_text(fetcher, p)
        topics = clf.classify(p.url, f"{p.category}. {', '.join(p.keywords)}. {text}")
        scored.append(opp.score(opp.from_petition(p, text, topics), wanted, mp_topics, my_committees, today, p=p))

    shown = [o for o in scored if o.score >= 0 and (show_all or set(o.topics) & wanted)]
    shown.sort(key=lambda o: o.score, reverse=True)
    return Ranked(mp, profile, roles, shown, fetcher)


def item(r: Ranked, n: int):
    if not 1 <= n <= len(r.shown):
        raise UserError(f"Item must be between 1 and {len(r.shown)}.")
    return r.shown[n - 1]


def brief_text(r: Ranked, n: int) -> str:
    o = item(r, n)
    if o.kind != "committee_study":
        raise UserError(f"Item {n} is a {o.kind.replace('_', ' ')}, not a committee study; briefs only apply to studies.")
    sub = committees.fetch_submission(r.fetcher, o.ref)
    members = committees.fetch_members(r.fetcher, o.ref.code)
    return brief_guide.render(o.ref, sub, members, date.today(), r.mp.name)


def letter_text(r: Ranked, n: int, why: str = "", ask: str = "", position: str = "support") -> str:
    o = item(r, n)
    if o.kind == "petition":
        raise UserError("For a petition the action is to sign it; a letter isn't needed. " + o.url)
    mine = {code for code, _ in r.roles.committees} if r.roles else set()
    code = o.ref.code if o.kind == "committee_study" and o.ref.code in mine else None
    li = letter.LetterInput(r.mp.name, r.mp.riding, o.title, o.url, o.kind, why, ask, position, code, o.topics)
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        client = anthropic.Anthropic()
    return letter.draft(li, r.profile.champions, client)


def card(postal_code: str, pick: int | None = None):
    """The MP 'baseball card' for a postal code."""
    from .analysis import card as cardmod

    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    mp = find_mp(fetcher, postal_code, pick)
    profile, slug, _ = mp_context(db, fetcher, mp)
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    return cardmod.build_card(fetcher, mp, profile, slug, bills, classifier=classifier(db))
