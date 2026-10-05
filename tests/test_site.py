import json
from datetime import date

from civic import site, web
from civic.sources.represent import MP


def mp(name, riding="R"):
    return MP(name=name, party="X", riding=riding, email=None, ourcommons_url=None)


def test_slugs_are_readable_and_unique():
    got = site.assign_slugs([mp("René Côté", "A"), mp("John Smith", "B—C"), mp("John Smith", "D"), mp("Chi Nguyen")])
    assert [s for s, _ in got] == ["rene-cote", "john-smith-b-c", "john-smith-d", "chi-nguyen"]


def test_sitemap_lists_home_the_directory_and_every_page():
    xml = site.sitemap(["b", "a"], "2026-10-03", "https://x.test")
    assert xml.index("/mp/a/") < xml.index("/mp/b/") and "<loc>https://x.test/</loc>" in xml and "2026-10-03" in xml
    assert "<loc>https://x.test/mps/</loc>" in xml


def test_index_files(tmp_path):
    built = [("chi-nguyen", mp("Chi Nguyen", "Spadina—Harbourfront")), ("a-b", mp("A B"))]
    site.write_index_files(tmp_path, built, today=date(2026, 10, 3), base="https://x.test")
    home = (tmp_path / "index.html").read_text()
    assert 'rel="canonical" href="https://x.test/"' in home and 'href="/mps/"' in home and "Browse all 2 MPs" in home
    assert "/mp/chi-nguyen/" not in home and "mprow" not in home  # the landing page does not list MPs
    directory = (tmp_path / "mps" / "index.html").read_text()
    assert 'href="/mp/chi-nguyen/"' in directory and 'href="/mp/a-b/"' in directory and "Oct 3, 2026" in directory
    assert 'rel="canonical" href="https://x.test/mps/"' in directory
    assert json.loads((tmp_path / "search.json").read_text())[0] == {"name": "Chi Nguyen", "party": "X", "riding": "Spadina—Harbourfront", "slug": "chi-nguyen"}
    robots = (tmp_path / "robots.txt").read_text()
    assert "Sitemap: https://x.test/sitemap.xml" in robots and "Disallow: /api/" in robots


def test_home_never_puts_a_postal_code_in_the_address():
    html = web.site_home([{"name": "A", "party": "X", "riding": "R", "slug": "a"}], "Oct 3, 2026", "https://x.test").decode()
    assert 'method="post" action="/api/postal"' in html and "<script src" not in html


def test_directory_has_photos_party_filters_and_escapes_names():
    mps = [{"name": "<b>x</b>", "party": "Liberal", "riding": "R", "slug": "a", "photo": "https://photos.test/a.jpg"},
           {"name": "Chi Nguyen", "party": "Liberal", "riding": "R2", "slug": "c"},
           {"name": "Bo Li", "party": "Green Party", "riding": "R3", "slug": "b"}]
    html = web.mps_page(mps, "Oct 3, 2026", "https://x.test").decode()
    assert "<b>x</b>" not in html
    assert 'src="https://photos.test/a.jpg"' in html and 'loading="lazy"' in html and 'referrerpolicy="no-referrer"' in html
    assert 'value="Liberal"' in html and "Liberal &middot; 2" in html and "Green Party &middot; 1" in html  # party filters with counts
    assert html.count('class="face"') == 3 and ">CN<" in html  # initials stand in when there is no photo


def test_a_rejected_key_stops_the_build_instead_of_failing_every_mp():
    import anthropic
    import httpx

    resp = httpx.Response(401, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    bad_key = anthropic.AuthenticationError("invalid x-api-key", response=resp, body=None)
    assert "rejected" in site.account_problem(bad_key)
    assert site.account_problem(ValueError("one MP had odd data")) is None
    out_of_credit = anthropic.BadRequestError("Your credit balance is too low", response=httpx.Response(400, request=resp.request), body=None)
    assert "out of credit" in site.account_problem(out_of_credit)
