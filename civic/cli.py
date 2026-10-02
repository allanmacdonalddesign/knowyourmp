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


def _rank(postal_code, interests, pick, show_all):
    """Shared by opportunities / letter / brief so item numbers always match."""
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
    return mp, profile, roles, shown, fetcher, db


@app.command("opportunities")
def opportunities_cmd(
    postal_code: str,
    interests: str = typer.Option(..., help="Comma-separated, e.g. housing,climate"),
    pick: int = typer.Option(None, help="Choose a riding when the postal code is split"),
    limit: int = typer.Option(10, help="How many to show"),
    show_all: bool = typer.Option(False, "--all", help="Include opportunities that don't match your interests"),
):
    """Ranked, explained opportunities to act on, for your MP and interests."""
    mp, _, _, shown, _, _ = _rank(postal_code, interests, pick, show_all)
    typer.echo(f"\nOpportunities for {mp.name} ({mp.riding})")
    if not shown:
        typer.echo("Nothing open matches those interests right now. Try --all or other interests.")
    for i, o in enumerate(shown[:limit], 1):
        typer.echo(f"\n{i}. [{o.score}] {o.title}")
        typer.echo(f"   {o.kind.replace('_', ' ')}; {o.detail}" + (f"; deadline {o.deadline}" if o.deadline else ""))
        typer.echo("   Ranked high because: " + "; ".join(o.reasons))
        typer.echo(f"   Do this: {o.action}")
        typer.echo(f"   Link: {o.url}")
    if shown:
        typer.echo("\nNext: `letter` or `brief` with the same postal code and --interests, plus --item N.")


def _item(shown, n):
    if not 1 <= n <= len(shown):
        typer.echo(f"--item must be between 1 and {len(shown)} (numbers match the `opportunities` list).")
        raise typer.Exit(1)
    return shown[n - 1]


@app.command("brief")
def brief_cmd(
    postal_code: str,
    interests: str = typer.Option(..., help="Same interests you used for `opportunities`"),
    item: int = typer.Option(..., help="Item number from `opportunities` (must be a committee study)"),
    pick: int = typer.Option(None),
):
    """Guide to submitting a brief to a committee: real deadline, limits, conditions and form."""
    from datetime import date

    from .actions import brief_guide
    from .sources import committees

    mp, _, _, shown, fetcher, _ = _rank(postal_code, interests, pick, False)
    o = _item(shown, item)
    if o.kind != "committee_study":
        typer.echo(f"Item {item} is a {o.kind.replace('_', ' ')}, not a committee study; briefs only apply to studies.")
        raise typer.Exit(1)
    sub = committees.fetch_submission(fetcher, o.ref)
    members = committees.fetch_members(fetcher, o.ref.code)
    typer.echo("\n" + brief_guide.render(o.ref, sub, members, date.today(), mp.name))


@app.command("letter")
def letter_cmd(
    postal_code: str,
    interests: str = typer.Option(..., help="Same interests you used for `opportunities`"),
    item: int = typer.Option(..., help="Item number from `opportunities` (a bill or committee study)"),
    why: str = typer.Option("", help="Why it matters to you, in your own words (strongly recommended)"),
    ask: str = typer.Option("", help="Your own specific ask; replaces the default"),
    position: str = typer.Option("support", help="support or oppose (for bills)"),
    pick: int = typer.Option(None),
):
    """Draft a short personal letter to your MP citing their real statements. Prints it; never sends."""
    from .actions import letter

    mp, profile, roles, shown, _, db = _rank(postal_code, interests, pick, False)
    o = _item(shown, item)
    if o.kind == "petition":
        typer.echo("For a petition the action is to sign it (link below); a letter isn't needed.\n" + o.url)
        raise typer.Exit(0)
    mine = {code for code, _ in roles.committees} if roles else set()
    code = o.ref.code if o.kind == "committee_study" and o.ref.code in mine else None
    li = letter.LetterInput(mp.name, mp.riding, o.title, o.url, o.kind, why, ask, position, code, o.topics)
    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        client = anthropic.Anthropic()
    typer.echo("\n" + letter.draft(li, profile.champions, client))
