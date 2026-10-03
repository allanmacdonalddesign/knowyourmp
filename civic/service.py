"""Shared by the CLI and the web UI: look up an MP and build their card."""
import os

from . import cache
from .analysis import classify, profile as prof
from .http import Fetcher
from .sources import openparliament as op
from .sources import ourcommons_member, represent


class UserError(Exception):
    """A problem the user can fix; the message is safe to show."""


class SplitPostcode(UserError):
    """More than one possible MP: the user has to pick. Also used for name searches that match several MPs."""

    def __init__(self, mps, message="This postal code covers more than one riding. Please choose yours."):
        super().__init__(message)
        self.mps = mps


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


MAX_NAME_MATCHES = 12


def find_mp_by_name(fetcher, query: str, pick: int | None = None):
    try:
        mps = represent.search(fetcher, query)
    except represent.InvalidName as e:
        raise UserError(str(e))
    if not mps:
        raise UserError("No sitting MP has a name like that. Check the spelling, or try just a last name.")
    if len(mps) > MAX_NAME_MATCHES:
        raise UserError("That matches too many MPs. Please type more of the name.")
    if len(mps) > 1:
        if pick is None or not 1 <= pick <= len(mps):
            raise SplitPostcode(mps, "More than one MP matches that name. Please choose yours.")
        return mps[pick - 1]
    return mps[0]


def mp_context(db, fetcher, mp):
    slug = op.find_slug(fetcher, mp.name, op.parl_id_from_url(mp.ourcommons_url))
    roles = ourcommons_member.fetch_roles(fetcher, mp.ourcommons_url) if mp.ourcommons_url else None
    speeches = op.speeches(fetcher, slug) if slug else []
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    return prof.build_profile(mp, slug, roles, speeches, bills, classifier(db)), slug, roles


def card(query: str, pick: int | None = None, by_name: bool = False):
    """The MP 'baseball card' for a postal code (or, with by_name, an MP's name)."""
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    mp = (find_mp_by_name if by_name else find_mp)(fetcher, query, pick)
    return card_for(mp, db, fetcher)


def card_for(mp, db=None, fetcher=None):
    """The card for an MP we already have (also used by the static site build)."""
    from .analysis import card as cardmod
    from .analysis import plain

    db = db or cache.connect()
    fetcher = fetcher or Fetcher(cache.HttpCache(db))
    profile, slug, _ = mp_context(db, fetcher, mp)
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    llm = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        llm = anthropic.Anthropic()
    explainer = plain.BillExplainer(llm, fetcher, cache.PlainBillCache(db)) if llm else None
    humanizer = plain.Humanizer(llm, plain.HumanBillCache(db)) if llm else None
    speeches = op.speeches(fetcher, slug) if slug else []  # cached by mp_context's fetch
    return cardmod.build_card(fetcher, mp, profile, slug, bills, classifier=classifier(db), explainer=explainer, llm=llm,
                              speeches=speeches, humanizer=humanizer)
