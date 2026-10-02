from datetime import date
from pathlib import Path
from types import SimpleNamespace

from civic.actions import brief_guide, letter
from civic.analysis.profile import Claim
from civic.sources import committees

FIX = Path(__file__).parent / "fixtures"
CLAIMS = [
    Claim("Members' statement (2025-10-20): Gender Equality", "https://openparliament.ca/debates/2025/10/20/chi-nguyen-1/",
          ["gender_equality_rights"], quote="Across Canada, women are transforming government."),
    Claim("Members' statement: Lunar New Year", "https://openparliament.ca/debates/x/", ["arts_culture_sport"], quote="Happy new year."),
    Claim("Sponsored Bill C-1", "https://openparliament.ca/bills/45-1/C-1/", ["housing"]),  # no quote: never cited
]


def _input(**kw):
    base = dict(mp_name="A B", riding="R", opportunity_title="Study", opportunity_url="https://x/study", kind="committee_study",
                topics=["gender_equality_rights"])
    base.update(kw)
    return letter.LetterInput(**base)


def test_only_relevant_quoted_statements_are_cited():
    cited = letter.pick_statements(CLAIMS, ["gender_equality_rights"])
    assert [c.url for c in cited] == ["https://openparliament.ca/debates/2025/10/20/chi-nguyen-1/"]
    assert letter.pick_statements(CLAIMS, ["defence_foreign_affairs"]) == []  # never force a citation


def test_invented_url_is_rejected_and_falls_back_to_template():
    class Fake:
        class messages:
            @staticmethod
            def create(**kw):
                return SimpleNamespace(content=[SimpleNamespace(text="Dear A B, see https://evil.example/made-up")])

    out = letter.draft(_input(), CLAIMS, Fake)
    assert "evil.example" not in out and "https://openparliament.ca/debates/2025/10/20/chi-nguyen-1/" in out
    assert "rewrite it in your own words" in out and "does not send" in out


def test_valid_draft_is_accepted_as_is():
    class Fake:
        class messages:
            @staticmethod
            def create(**kw):
                return SimpleNamespace(content=[SimpleNamespace(text="Dear A B, (https://openparliament.ca/debates/2025/10/20/chi-nguyen-1/) ask.")])

    assert letter.draft(_input(), CLAIMS, Fake).startswith("Dear A B, (https://openparliament")


def test_ask_depends_on_situation():
    assert "member of this committee" in letter.default_ask(_input(mp_on_committee="FEWO"))
    assert "vote against" in letter.default_ask(_input(kind="bill", position="oppose"))
    assert letter.default_ask(_input(ask="Meet me")) == "Meet me"


def test_brief_guide_uses_real_study_data():
    base = committees.parse_participate((FIX / "committees_participate.html").read_text())[0]
    study = committees.parse_study((FIX / "committee_study.html").read_text(), base)
    sub = committees.parse_submission((FIX / "committee_study.html").read_text(), (FIX / "submit_brief.html").read_text())
    text = brief_guide.render(study, sub, [], date(2026, 10, 1), None)
    assert "October 23, 2026 (22 days left)" in text and "submit-brief/fewo/13509506" in text
    assert "does not submit anything" in text


def test_committee_members_parsed():
    ms = committees.parse_members((FIX / "committee_members.html").read_text())
    assert len(ms) == 10 and ms[0].role == "Chair" and any(m.name == "Chi Nguyen" for m in ms)


def test_reply_text_skips_thinking_blocks():
    from civic.analysis.classify import reply_text

    resp = SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking="hmm"), SimpleNamespace(type="text", text="Dear A B")])
    assert reply_text(resp) == "Dear A B"
