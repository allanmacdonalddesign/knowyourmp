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
    def __init__(self, mps):
        super().__init__("This postal code covers more than one riding. Please choose yours.")
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


def mp_context(db, fetcher, mp):
    slug = op.find_slug(fetcher, mp.name, op.parl_id_from_url(mp.ourcommons_url))
    roles = ourcommons_member.fetch_roles(fetcher, mp.ourcommons_url) if mp.ourcommons_url else None
    speeches = op.speeches(fetcher, slug) if slug else []
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    return prof.build_profile(mp, slug, roles, speeches, bills, classifier(db)), slug, roles


def card(postal_code: str, pick: int | None = None):
    """The MP 'baseball card' for a postal code."""
    from .analysis import card as cardmod
    from .analysis import plain

    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    mp = find_mp(fetcher, postal_code, pick)
    profile, slug, _ = mp_context(db, fetcher, mp)
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    llm = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        llm = anthropic.Anthropic()
    explainer = plain.BillExplainer(llm, fetcher, cache.PlainBillCache(db)) if llm else None
    return cardmod.build_card(fetcher, mp, profile, slug, bills, classifier=classifier(db), explainer=explainer, llm=llm)
