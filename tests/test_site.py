import json
from datetime import date

from civic import site, web
from civic.sources.represent import MP


def mp(name, riding="R"):
    return MP(name=name, party="X", riding=riding, email=None, ourcommons_url=None)


def test_slugs_are_readable_and_unique():
    got = site.assign_slugs([mp("René Côté", "A"), mp("John Smith", "B—C"), mp("John Smith", "D"), mp("Chi Nguyen")])
    assert [s for s, _ in got] == ["rene-cote", "john-smith-b-c", "john-smith-d", "chi-nguyen"]


def test_sitemap_lists_home_and_every_page():
    xml = site.sitemap(["b", "a"], "2026-10-03", "https://x.test")
    assert xml.index("/mp/a/") < xml.index("/mp/b/") and "<loc>https://x.test/</loc>" in xml and "2026-10-03" in xml


def test_index_files(tmp_path):
    built = [("chi-nguyen", mp("Chi Nguyen", "Spadina—Harbourfront")), ("a-b", mp("A B"))]
    site.write_index_files(tmp_path, built, today=date(2026, 10, 3), base="https://x.test")
    home = (tmp_path / "index.html").read_text()
    assert 'href="/mp/chi-nguyen/"' in home and "All 2 MPs" in home and "Oct 3, 2026" in home
    assert 'rel="canonical" href="https://x.test/"' in home
    assert json.loads((tmp_path / "search.json").read_text())[0] == {"name": "Chi Nguyen", "party": "X", "riding": "Spadina—Harbourfront", "slug": "chi-nguyen"}
    robots = (tmp_path / "robots.txt").read_text()
    assert "Sitemap: https://x.test/sitemap.xml" in robots and "Disallow: /api/" in robots


def test_home_never_puts_a_postal_code_in_the_address():
    html = web.site_home([{"name": "A", "party": "X", "riding": "R", "slug": "a"}], "Oct 3, 2026", "https://x.test").decode()
    assert 'method="post" action="/api/postal"' in html and "<script src" not in html


def test_home_escapes_names():
    html = web.site_home([{"name": "<b>x</b>", "party": "X", "riding": "R", "slug": "a"}], "d", "https://x.test").decode()
    assert "<b>x</b>" not in html
