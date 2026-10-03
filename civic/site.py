"""Static site build: one page per sitting MP, a directory home page, sitemap and robots.txt.

Run with `python -m civic site`. Everything it reads is cached, so after the first full build a rebuild only fetches what
changed and the AI only writes text for bills it has not described before."""
import json
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from . import cache, service, web
from .config import SITE_URL
from .http import Fetcher
from .sources import openparliament as op
from .sources import represent


@dataclass
class Result:
    built: list = field(default_factory=list)  # (slug, MP)
    failed: list = field(default_factory=list)  # (name, error)
    skipped: int = 0  # not attempted because the time budget ran out
    total: int = 0

    @property
    def complete(self) -> bool:
        return self.skipped == 0


def assign_slugs(mps: list[represent.MP]) -> list[tuple[str, represent.MP]]:
    """Stable, readable URLs from the name; two MPs with the same name get their riding appended."""
    names = [op.slugify(m.name) for m in mps]
    out, used = [], set()
    for m, base in zip(mps, names):
        slug = base if names.count(base) == 1 else f"{base}-{op.slugify(m.riding.replace(chr(8212), ' ').replace(chr(8211), ' '))}"
        while slug in used:
            slug += "-2"
        used.add(slug)
        out.append((slug, m))
    return out


def stamp(today: date | None = None) -> tuple[str, str]:
    d = today or date.today()
    return f"{d:%b} {d.day}, {d.year}", d.isoformat()


def sitemap(slugs: list[str], lastmod: str, base: str = SITE_URL) -> str:
    urls = [f"{base}/"] + [f"{base}/mp/{s}/" for s in sorted(slugs)]
    body = "".join(f"<url><loc>{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n'


def write_index_files(out: Path, built: list[tuple[str, represent.MP]], today: date | None = None, base: str = SITE_URL) -> None:
    updated, iso = stamp(today)
    mps = [{"name": m.name, "party": m.party, "riding": m.riding, "slug": s} for s, m in built]
    (out / "index.html").write_bytes(web.site_home(mps, updated, base))
    # Read by the postal-code function to turn a Represent result into a page address.
    (out / "search.json").write_text(json.dumps(mps, separators=(",", ":"), ensure_ascii=False))
    (out / "sitemap.xml").write_text(sitemap([s for s, _ in built], iso, base))
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: {base}/sitemap.xml\n")
    (out / "404.html").write_bytes(web.page("Page not found", f'{web.topbar("Not found", web.LEAF)}'
                                            '<div class="grid"><div class="cell s12"><h1 class="name">Not found</h1>'
                                            '<p class="lead"><a href="/">Find your MP</a></p></div></div>'))
    (out / "_headers").write_text("/mp/*\n  Cache-Control: public, max-age=3600\n/search.json\n  Cache-Control: public, max-age=3600\n")


def build(out: Path, limit: int | None = None, only: str | None = None, budget_minutes: float | None = None,
          base: str = SITE_URL, log=print) -> Result:
    db = cache.connect()
    fetcher = Fetcher(cache.HttpCache(db))
    people = assign_slugs(represent.roster(fetcher))
    res = Result(total=len(people))
    if only:
        people = [(s, m) for s, m in people if s == only]
    if limit:
        people = people[:limit]
    updated, iso = stamp()
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    for i, (slug, mp) in enumerate(people, 1):
        if budget_minutes and (time.monotonic() - started) / 60 > budget_minutes:
            res.skipped = len(people) - i + 1
            log(f"Time budget reached; {res.skipped} MPs not attempted. Run again to continue (everything fetched so far is cached).")
            break
        url = f"{base}/mp/{slug}/"
        try:
            card = service.card_for(mp, db, fetcher)
            html = web.card_page(card, "", None, site={"url": url, "updated": updated, "updated_iso": iso})
        except Exception as e:  # one bad MP must not stop the other 342
            res.failed.append((mp.name, f"{type(e).__name__}: {e}"))
            log(f"[{i}/{len(people)}] FAILED {mp.name}: {type(e).__name__}: {e}")
            continue
        (out / "mp" / slug).mkdir(parents=True, exist_ok=True)
        (out / "mp" / slug / "index.html").write_bytes(html)
        res.built.append((slug, mp))
        log(f"[{i}/{len(people)}] {mp.name}")
    # The index covers every MP page present on disk, so a partial or resumed build still lists what exists.
    present = [(s, m) for s, m in assign_slugs(represent.roster(fetcher)) if (out / "mp" / s / "index.html").exists()]
    write_index_files(out, present, base=base)
    return res
