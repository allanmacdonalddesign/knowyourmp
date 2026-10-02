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
    from civic.analysis.stance import KeyVote

    mp = SimpleNamespace(name="A B", party="Liberal", riding="R", email="a@parl.gc.ca", ourcommons_url="https://www.ourcommons.ca/x", offices=[])
    p = Profile("A B", "R", "Liberal", [Claim("Member of Parliament", "u")],
                [Claim("Members' statement (2026-01-01): Arena", "https://openparliament.ca/debates/1/", ["housing"], quote="We need <b>housing</b>.")],
                Counter({"Government Orders": 3}), Counter({"housing": 1}), [])
    v = cardmod.VoteLine("/votes/45-1/1/", "2026-01-01", "Bill C-1 <script>", "Passed", "Yes", "Yes", True)
    kv = KeyVote("/bills/45-1/C-1/", "C-1", "An Act <script>", "Builds <i>homes</i>.", True, "3rd reading", "Yes", "Passed", "2026-01-01", "/votes/45-1/1/", ["housing"])
    c = cardmod.Card(mp, p, "a-b", None, "2020-01-01", "45-1", 10, Counter({"Yes": 9, "No": 1}), [v], [], {}, {}, [kv], 4,
                     [{"text": "Voted for a housing bill.", "refs": ["v1"]}], {"v1": ("Bill C-1 vote", "https://openparliament.ca/votes/45-1/1/")}, [])
    return c


def test_card_page_renders_filterable_items_and_escapes():
    html = web.card_page(_card(), "M5V3L9", None).decode()
    assert 'data-topics="housing"' in html and 'name="topic"' in html
    body = html.split("</style>")[1].split("<script>")[0]
    assert "<script>" not in body and "<i>" not in body  # injected text is escaped
    assert "&lt;script&gt;" in html and "&lt;b&gt;housing" in html and "Builds &lt;i&gt;homes" in html
    assert "With their party" in html and "1<span style='font-size:.4em'> of 1" in html
    assert "Voted for" in html and "At a glance" in html and 'title="Bill C-1 vote"' in html
    assert "4 other votes" in html
    text = html.split("</style>")[1].lower()
    assert "opportunit" not in text and "draft a letter" not in text


def test_overview_drops_claims_without_valid_sources():
    from civic.analysis.overview import validate

    reply = '[{"text":"ok","refs":["v1","zz"]},{"text":"invented","refs":["nope"]},{"text":"no refs","refs":[]}]'
    assert validate(reply, {"v1", "s1"}) == [{"text": "ok", "refs": ["v1"]}]
    assert validate("not json", {"v1"}) == []


def test_key_votes_only_bill_deciding_and_prefer_third_reading():
    from civic.analysis import stance
    from civic.sources.openparliament import VoteSummary

    V = lambda n, d, b="/bills/45-1/C-1/": VoteSummary(f"/votes/45-1/{n}/", n, "2026-01-01", d, "Passed", b)
    votes = [V(5, "Government Business No. 13 (Proceedings on Bill C-22)", None), V(4, "3rd reading and adoption of Bill C-1, An Act"),
             V(3, "Bill C-1, An Act (report stage amendment) (Motion No. 2)"), V(2, "2nd reading of Bill C-1, An Act"),
             V(1, "2nd reading of Bill C-9, An Act", "/bills/45-1/C-9/")]
    ballots = {v.url: "Yes" for v in votes}
    ballots["/votes/45-1/1/"] = "No"
    picked, other = stance.select_key_votes(votes, ballots)
    assert [(v.number, b) for v, b in picked] == [(4, "Yes"), (1, "No")] and other == 3


def test_identity_line_uses_chosen_topics_and_committees():
    c = _card()
    c.profile.responsible_for.append(Claim("Member, Standing Committee on Transport (TRAN)", "u"))
    assert web.identity_line(c) == "Chooses to speak about housing. Sits on TRAN."
