from datetime import date
from types import SimpleNamespace

from civic import web
from civic.ranking.opportunities import Opportunity


def test_home_escapes_user_input():
    html = web.home("<script>x</script>", '"><img src=x>').decode()
    assert "<script>x</script>" not in html and '"><img' not in html


def test_linkify_only_https_and_escapes():
    out = web.linkify('see https://a.example/x and <b>bold</b> javascript:alert(1)')
    assert 'href="https://a.example/x"' in out and "<b>" not in out and 'href="javascript' not in out


def test_results_page_has_actions_by_kind_and_no_inline_secrets():
    study = Opportunity("committee_study", "FEWO: T", "https://x/s", ["health"], "8 briefs", "Submit", date(2026, 10, 23), 90, ["why one"])
    pet = Opportunity("petition", "Petition e-1: P", "https://x/p", ["health"], "10 signatures", "Sign", None, 50, ["why two"])
    r = SimpleNamespace(mp=SimpleNamespace(name="A B", party="X", riding="R"), shown=[study, pet])
    html = web.results(r, "M5V3L9", ["health"], None).decode()
    assert 'action="/letter"' in html and 'action="/brief"' in html
    assert html.count('action="/letter"') == 1 and html.count('action="/brief"') == 1  # petition gets neither
    assert 'rel="noopener noreferrer"' in html
