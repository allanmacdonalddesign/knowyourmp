from pathlib import Path

import typer

from . import cache, service
from .analysis import profile as prof
from .http import Fetcher
from .sources import openparliament as op

app = typer.Typer(help="MP baseball cards")


@app.callback()
def main():
    """MP baseball cards."""


@app.command("profile")
def profile_cmd(postal_code: str, pick: int = typer.Option(None, help="Choose a riding when the postal code is split")):
    """Print the MP for a postal code with a cited profile."""
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    try:
        mp = service.find_mp(fetcher, postal_code, pick)
    except service.SplitPostcode as e:
        typer.echo("This postal code covers more than one riding. Re-run with --pick N:")
        for i, m in enumerate(e.mps, 1):
            typer.echo(f"  {i}. {m.name} ({m.party}), {m.riding}")
        raise typer.Exit(2)
    except service.UserError as e:
        typer.echo(str(e))
        raise typer.Exit(1)
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
    for n in p.notes:
        typer.echo(f"\nNote: {n}")


@app.command("web")
def web_cmd(port: int = typer.Option(8000, help="Local port")):
    """Run the local web page (this machine only)."""
    from . import web

    web.serve(port)


@app.command("site")
def site_cmd(
    out: Path = typer.Option(Path("dist"), help="Where to write the site"),
    limit: int = typer.Option(None, help="Only build the first N MPs (for testing)"),
    only: str = typer.Option(None, help="Only build this MP's page, e.g. chi-nguyen"),
    budget_minutes: float = typer.Option(None, help="Stop starting new MPs after this long; run again to continue"),
):
    """Build the static site: a page for every sitting MP, a directory page, sitemap and robots.txt."""
    from . import site

    try:
        res = site.build(out, limit=limit, only=only, budget_minutes=budget_minutes)
    except site.AccountProblem as e:
        typer.echo(f"Stopped: {e}")
        raise typer.Exit(4)
    typer.echo(f"Built {len(res.built)} pages, {len(res.failed)} failed, {res.skipped} not attempted.")
    for name, err in res.failed:
        typer.echo(f"  failed: {name}: {err}")
    if res.skipped:
        raise typer.Exit(3)  # incomplete: do not publish
    if len(res.failed) > max(3, res.total // 20):
        raise typer.Exit(1)  # too many missing pages to publish
