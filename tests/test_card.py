from datetime import date
from types import SimpleNamespace

from civic import web
from civic.analysis import card as cardmod
from civic.analysis.profile import Claim, Profile
from collections import Counter


def test_party_matching_and_comparison():
    assert cardmod.party_matches("Bloc Québécois", "Bloc")
    assert cardmod.party_matches("Liberal", "Liberal") and not cardmod.party_matches("Liberal", "Conservative")
    pos = {"Liberal": "Yes", "Bloc": "No"}
    assert cardmod.compare("Yes", pos, "Liberal") == ("Yes", True)
    assert cardmod.compare("No", pos, "Liberal") == ("Yes", False)
    assert cardmod.compare("Paired", pos, "Liberal") == ("Yes", None)  # can't compare


def _card():
    mp = SimpleNamespace(name="A B", party="Liberal", riding="R", email="a@parl.gc.ca", ourcommons_url="https://www.ourcommons.ca/x", offices=[])
    p = Profile("A B", "R", "Liberal", [Claim("Member of Parliament", "u")],
                [Claim("Members' statement (2026-01-01): Arena", "https://openparliament.ca/debates/1/", ["housing"], quote="We need <b>housing</b>.")],
                Counter({"Government Orders": 3}), Counter({"housing": 1}), [])
    v = cardmod.VoteLine("/votes/45-1/1/", "2026-01-01", "Bill C-1 <script>", "Passed", "Yes", "Yes", True, ["housing"])
    return cardmod.Card(mp, p, "a-b", None, "2020-01-01", "45-1", 10, Counter({"Yes": 9, "No": 1}), [v], [], {}, [])


def test_card_page_renders_filterable_items_and_escapes():
    html = web.card_page(_card(), "M5V3L9", None).decode()
    assert 'data-topics="housing"' in html and 'action="/opportunities"' in html
    assert "<script>" not in html.split("</style>")[1].split("<script>")[0]  # injected text escaped
    assert "&lt;script&gt;" in html and "&lt;b&gt;housing" in html
    assert "1 of 1 with their party" in html or "1 of 1" in html
