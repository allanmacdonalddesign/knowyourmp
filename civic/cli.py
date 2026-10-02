import os

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

    slug = op.find_slug(fetcher, mp.name)
    roles = ourcommons_member.fetch_roles(fetcher, mp.ourcommons_url) if mp.ourcommons_url else None
    speeches = op.speeches(fetcher, slug) if slug else []
    bills = op.sponsored_bills(fetcher, slug) if slug else []
    classifier = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        classifier = classify.Classifier(anthropic.Anthropic(), cache.ClassificationCache(db))

    p = prof.build_profile(mp, slug, roles, speeches, bills, classifier)
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
