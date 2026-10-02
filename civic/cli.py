import typer

from . import cache, service
from .analysis import profile as prof
from .http import Fetcher
from .sources import openparliament as op

app = typer.Typer(help="Civic Leverage Tool")


@app.callback()
def main():
    """Civic Leverage Tool."""


def _run(fn, *args, **kwargs):
    """Run a service call, turning user-fixable problems into plain messages."""
    try:
        return fn(*args, **kwargs)
    except service.SplitPostcode as e:
        typer.echo("This postal code covers more than one riding. Re-run with --pick N:")
        for i, m in enumerate(e.mps, 1):
            typer.echo(f"  {i}. {m.name} ({m.party}), {m.riding}")
        raise typer.Exit(2)
    except service.UserError as e:
        typer.echo(str(e))
        raise typer.Exit(1)


@app.command("profile")
def profile_cmd(postal_code: str, pick: int = typer.Option(None, help="Choose a riding when the postal code is split")):
    """Print the MP for a postal code with a cited profile."""
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    mp = _run(service.find_mp, fetcher, postal_code, pick)
    p, slug, _ = service.mp_context(db, fetcher, mp)
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
    r = _run(service.rank, postal_code, interests, pick, show_all)
    typer.echo(f"\nOpportunities for {r.mp.name} ({r.mp.riding})")
    if not r.shown:
        typer.echo("Nothing open matches those interests right now. Try --all or other interests.")
    for i, o in enumerate(r.shown[:limit], 1):
        typer.echo(f"\n{i}. [{o.score}] {o.title}")
        typer.echo(f"   {o.kind.replace('_', ' ')}; {o.detail}" + (f"; deadline {o.deadline}" if o.deadline else ""))
        typer.echo("   Ranked high because: " + "; ".join(o.reasons))
        typer.echo(f"   Do this: {o.action}")
        typer.echo(f"   Link: {o.url}")
    if r.shown:
        typer.echo("\nNext: `letter` or `brief` with the same postal code and --interests, plus --item N.")


@app.command("brief")
def brief_cmd(
    postal_code: str,
    interests: str = typer.Option(..., help="Same interests you used for `opportunities`"),
    item: int = typer.Option(..., help="Item number from `opportunities` (must be a committee study)"),
    pick: int = typer.Option(None),
):
    """Guide to submitting a brief to a committee: real deadline, limits, conditions and form."""
    r = _run(service.rank, postal_code, interests, pick)
    typer.echo("\n" + _run(service.brief_text, r, item))


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
    r = _run(service.rank, postal_code, interests, pick)
    typer.echo("\n" + _run(service.letter_text, r, item, why, ask, position))


@app.command("web")
def web_cmd(port: int = typer.Option(8000, help="Local port")):
    """Run the simple local web page (this machine only)."""
    from . import web

    web.serve(port)
