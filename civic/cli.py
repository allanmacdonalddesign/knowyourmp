import os
import re

import typer

from . import cache
from .analysis import classify, profile as prof
from .http import Fetcher
from .sources import openparliament as op
from .sources import ourcommons_member, represent

app = typer.Typer(help="Civic Leverage Tool")


@app.callback()
def main():
    """Civic Leverage Tool."""


def _choose_mp(mps: list[represent.MP], pick: int | None) -> represent.MP:
    if len(mps) == 1:
        return mps[0]
    typer.echo("This postal code covers more than one riding. Re-run with --pick N, or use a full address:")
    for i, m in enumerate(mps, 1):
        typer.echo(f"  {i}. {m.name} ({m.party}), {m.riding}")
    if pick is None or not 1 <= pick <= len(mps):
        raise typer.Exit(2)
    return mps[pick - 1]


def _classifier(db):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    import anthropic

    return classify.Classifier(anthropic.Anthropic(), cache.ClassificationCache(db))


def _mp_context(db, fetcher, mp):
    slug = op.find_slug(fetcher, mp.name)
    roles = ourcommons_member.fetch_roles(fetcher, mp.ourcommons_url) if mp.ourcommons_url else None
    speeches = op.speeches(fetcher, slug) if slug else []
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    p = prof.build_profile(mp, slug, roles, speeches, bills, _classifier(db))
    return p, slug, roles


@app.command("profile")
def profile_cmd(postal_code: str, pick: int = typer.Option(None, help="Choose a riding when the postal code is split")):
    """Print the MP for a postal code with a cited profile."""
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    try:
        mps = represent.lookup(fetcher, postal_code)
    except represent.InvalidPostalCode as e:
        typer.echo(str(e))
        raise typer.Exit(1)
    if not mps:
        typer.echo("No MP found for that postal code.")
        raise typer.Exit(1)
    mp = _choose_mp(mps, pick)
    p, slug, _ = _mp_context(db, fetcher, mp)
    _render(p, slug)


def _render(p: prof.Profile, slug):
    typer.echo(f"\n{p.name} ({p.party}), {p.riding}")
    if slug:
        typer.echo(f"Record: {op.SITE}/politicians/{slug}/")
    typer.echo("\nRESPONSIBLE FOR (roles assigned by position or party)")
    for c in p.responsible_for:
        typer.echo(f"  - {c.text}\n    source: {c.url}")
    typer.echo("\nPERSONALLY CHAMPIONS (chosen: members' statements, private members' bills)")
    if p.topic_counts:
        typer.echo("  Topics: " + ", ".join(f"{t} ({n})" for t, n in p.topic_counts.most_common(5)))
    for c in p.champions[:15]:
        tags = f" [{', '.join(c.topics)}]" if c.topics else ""
        typer.echo(f"  - {c.text}{tags}\n    source: {c.url}")
    if p.assigned_activity:
        typer.echo("\nOTHER ACTIVITY (assigned by role; lightly weighted): "
                   + ", ".join(f"{k} ({n})" for k, n in p.assigned_activity.most_common(5)))
    for n in p.notes:
        typer.echo(f"\nNote: {n}")


@app.command("opportunities")
def opportunities_cmd(
    postal_code: str,
    interests: str = typer.Option(..., help="Comma-separated, e.g. housing,climate"),
    pick: int = typer.Option(None, help="Choose a riding when the postal code is split"),
    limit: int = typer.Option(10, help="How many to show"),
    show_all: bool = typer.Option(False, "--all", help="Include opportunities that don't match your interests"),
):
    """Ranked, explained opportunities to act on, for your MP and interests."""
    from datetime import date

    from .analysis.interests import resolve
    from .ranking import opportunities as opp
    from .sources import committees, legisinfo, petitions

    try:
        wanted = resolve(interests)
    except ValueError as e:
        typer.echo(str(e))
        raise typer.Exit(1)
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    clf = _classifier(db)
    if clf is None:
        typer.echo("Set ANTHROPIC_API_KEY: opportunities are matched to your interests by topic tagging.")
        raise typer.Exit(1)
    try:
        mps = represent.lookup(fetcher, postal_code)
    except represent.InvalidPostalCode as e:
        typer.echo(str(e))
        raise typer.Exit(1)
    if not mps:
        typer.echo("No MP found for that postal code.")
        raise typer.Exit(1)
    mp = _choose_mp(mps, pick)
    profile, _, roles = _mp_context(db, fetcher, mp)
    mp_topics = set(profile.topic_counts)
    my_committees = {code for code, _ in roles.committees} if roles else set()

    scored: list[opp.Opportunity] = []
    studies = committees.fetch_open_studies(fetcher)
    study_bills = {m.group(0) for s in studies if (m := re.search(r"Bill [CS]-\d+", s.title))}
    for s in studies:
        scored.append(opp.score(opp.from_study(s, clf.classify(s.url, s.title)), wanted, mp_topics, my_committees, date.today(), s=s))
    for b in legisinfo.fetch_active(fetcher):
        if f"Bill {b.number}" in study_bills:
            continue  # already shown as an open committee study
        scored.append(opp.score(opp.from_bill(b, clf.classify(b.url, b.title)), wanted, mp_topics, my_committees, date.today(), b=b))
    for p in petitions.fetch_open(fetcher):
        text = petitions.fetch_text(fetcher, p)
        topics = clf.classify(p.url, f"{p.category}. {', '.join(p.keywords)}. {text}")
        scored.append(opp.score(opp.from_petition(p, text, topics), wanted, mp_topics, my_committees, date.today(), p=p))

    shown = [o for o in scored if o.score >= 0 and (show_all or set(o.topics) & wanted)]
    shown.sort(key=lambda o: o.score, reverse=True)
    typer.echo(f"\nOpportunities for {mp.name} ({mp.riding}); interests: {', '.join(sorted(wanted))}")
    if not shown:
        typer.echo("Nothing open matches those interests right now. Try --all or other interests.")
    for i, o in enumerate(shown[:limit], 1):
        typer.echo(f"\n{i}. [{o.score}] {o.title}")
        typer.echo(f"   {o.kind.replace('_', ' ')}; {o.detail}" + (f"; deadline {o.deadline}" if o.deadline else ""))
        typer.echo("   Ranked high because: " + "; ".join(o.reasons))
        typer.echo(f"   Do this: {o.action}")
        typer.echo(f"   Link: {o.url}")
