from datetime import date
from types import SimpleNamespace

from civic import web
from civic.analysis import card as cardmod
from civic.analysis.profile import Claim, Profile
from collections import Counter
import re

from civic.analysis.words import Term


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
                     [{"text": "Voted for a housing bill.", "kind": "for", "refs": ["v1"]}], {"v1": ("Bill C-1 vote", "https://openparliament.ca/votes/45-1/1/")}, [])
    c.election = SimpleNamespace(won=True, year="2025", share=52, url="https://openparliament.ca/politicians/a-b/")
    c.terms = [Term("carbon <pricing>", 12, 9, "2026-06-01"), Term("housing", 5, 4, "2026-05-01")]
    c.speech_count, c.speeches_since, c.favourite_word = 40, "2025-01-01", "<support>"
    return c


def test_card_page_renders_filterable_items_and_escapes():
    html = web.card_page(_card(), "M5V3L9", None).decode()
    assert 'data-topics="housing"' in html and 'name="topic"' in html
    body = html.split("</style>")[1].split("<script>")[0]
    assert "<script>" not in body and "<i>" not in body  # injected text is escaped
    assert "&lt;script&gt;" in html and "Builds &lt;i&gt;homes" in html and "carbon &lt;pricing&gt;" in html and "&lt;support&gt;" in html
    assert "Voted for" in html and "At a glance" in html and 'title="Bill C-1 vote"' in html
    assert "4 other votes" in html
    text = html.split("</style>")[1].lower()
    assert "opportunit" not in text and "draft a letter" not in text


def test_card_layout_matches_the_design():
    html = web.card_page(_card(), "M5V3L9", None).decode()
    stats = re.findall(r'<div class="cell s3"><div class="mono soft">([^<]+)<', html)
    assert stats == ["Time in office", "Bills sponsored", "Won their election with", "House votes"]
    assert "52%" in html and "of the vote, in 2025" in html
    assert ('href="#bills"' in html) == ('id="bills"' in html)  # the stat only links to the section when it exists
    assert "--party:#bc241a" in html  # Liberal red behind the photo
    assert ">Pro<" in html and ">Anti<" in html and 'href="#votes-for"' in html
    assert 'ul" href="#votes-against"' not in html  # no votes against on record, so no link to an empty list
    assert 'data-ballot="for"' in html and 'id="votes-view" class="hidden"' in html
    assert html.count('<g class="bub') == 4 and 'data-term="carbon &lt;pricing&gt;"' in html  # two layouts x two terms
    assert "M5V3L9" not in html.split("</style>")[1]  # the postal code never ends up in the page


def test_party_colours():
    assert web.party_colour("Liberal") == "#bc241a" and web.party_colour("Bloc Québécois") == "#33b2cc"
    assert web.party_colour("NDP") == "#f37021" and web.party_colour("Independent") == "#888888"


def test_overview_drops_claims_without_valid_sources():
    from civic.analysis.overview import validate

    reply = '[{"text":"ok","refs":["v1","zz"]},{"text":"invented","refs":["nope"]},{"text":"no refs","refs":[]}]'
    assert validate(reply, {"v1", "s1"}) == [{"text": "ok", "kind": "other", "refs": ["v1"]}]
    assert validate('[{"text":"a","kind":"for","refs":["v1"]},{"text":"b","kind":"sneaky","refs":["v1"]}]', {"v1"})[1]["kind"] == "other"
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


class FakeLLM:
    """Stands in for the Anthropic client: returns canned replies and records the prompts it was sent."""

    def __init__(self, reply):
        self.reply, self.prompts = reply, []
        self.messages = self

    def create(self, model, max_tokens, messages):
        self.prompts.append(messages[0]["content"])
        text = self.reply(messages[0]["content"]) if callable(self.reply) else self.reply
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def test_at_a_glance_sides_only_see_their_own_votes():
    from civic.analysis.stance import KeyVote

    c = _card()
    c.key_votes.append(KeyVote("/bills/45-1/C-2/", "C-2", "An Act two", "Changes bail rules.", True, "2nd reading", "No", "Failed", "2026-01-02", "/votes/45-1/2/"))
    llm = FakeLLM(lambda p: '[{"text": "A B voted for housing.", "refs": ["v1"]}]' if "voted FOR" in p
                  else '[{"text": "A B voted against bail changes.", "refs": ["v1", "v2"]}]')
    sentences, links = cardmod._overview(c, llm)
    by_kind = {s["kind"]: s for s in sentences}
    assert by_kind["for"]["refs"] == ["v1"]
    assert by_kind["against"]["refs"] == ["v2"]  # v1 is a yes vote, so the "against" side can't cite it
    for_prompt = next(p for p in llm.prompts if "voted FOR" in p)
    assert "Builds" in for_prompt and "bail" not in for_prompt


def test_human_rewrites_are_cached_validated_and_toggleable():
    from civic import cache
    from civic.analysis import plain

    db = cache.connect(":memory:")
    llm = FakeLLM('{"b1": "Gets more homes built faster.", "b2": "I cannot help with that."}')
    h = plain.Humanizer(llm, plain.HumanBillCache(db))
    got = h.rewrite([("/bills/45-1/C-1/", "Builds homes.", "An Act"), ("/bills/45-1/C-2/", "Changes bail.", "An Act two")])
    assert got == {"/bills/45-1/C-1/": "Gets more homes built faster."}  # the refusal is dropped, never shown
    assert h.rewrite([("/bills/45-1/C-1/", "Builds homes.", "An Act")]) == got and len(llm.prompts) == 1  # served from cache

    c = _card()
    c.human = {"/bills/45-1/C-1/": "Gets <more> homes built."}
    html = web.card_page(c, "", None).decode()
    assert 'class="hum mono" aria-pressed="false"' in html and "vitem has-human" in html
    assert '<span class="t-human">Gets &lt;more&gt; homes built.</span>' in html
    assert "hum mono" not in web.card_page(_card(), "", None).decode()  # no rewrites, no toggle
