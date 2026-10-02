import json
from datetime import date
from pathlib import Path

from civic.ranking import opportunities as opp
from civic.sources import committees, legisinfo, petitions

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 10, 1)


def test_petition_list_parses_real_sample():
    ps = petitions.parse_list(json.loads((FIX / "petitions_searchasync.json").read_text())["html"])
    assert len(ps) == 20 and all(p.id.startswith("e-") for p in ps)
    assert ps[0].signatures >= 0 and ps[0].closes is not None


def test_petition_detail_text():
    text = petitions.parse_detail_text((FIX / "petition_detail.html").read_text())
    assert text.startswith("We, the undersigned") and "homelessness" in text


def test_committee_study_parse_deadline_and_counts():
    base = committees.parse_participate((FIX / "committees_participate.html").read_text())[0]
    s = committees.parse_study((FIX / "committee_study.html").read_text(), base)
    assert s.deadline == date(2026, 10, 23) and s.briefs == 8 and s.witnesses == 11


def test_legisinfo_only_house_bills():
    bills = legisinfo.parse(json.loads((FIX / "legisinfo_small.json").read_text()))
    assert bills and all(b.url.startswith("https://www.parl.ca/legisinfo/") for b in bills)


def _petition(sig):
    return petitions.Petition("e-1", "Health", ("x",), date(2026, 10, 10), "A", sig, "u")


def test_ally_bonus_needs_user_interest_overlap():
    p = _petition(400)
    o = opp.score(opp.from_petition(p, "text", ["economy_cost_of_living"]), {"housing"}, {"economy_cost_of_living"}, set(), TODAY, p=p)
    assert not any("arming an ally" in r for r in o.reasons)
    o = opp.score(opp.from_petition(p, "text", ["housing"]), {"housing"}, {"housing"}, set(), TODAY, p=p)
    assert any("arming an ally" in r for r in o.reasons)


def test_petition_past_500_ranks_below_near_500_and_expired_excluded():
    near, past = _petition(450), _petition(900)
    s_near = opp.score(opp.from_petition(near, "t", ["housing"]), {"housing"}, set(), set(), TODAY, p=near)
    s_past = opp.score(opp.from_petition(past, "t", ["housing"]), {"housing"}, set(), set(), TODAY, p=past)
    assert s_near.score > s_past.score
    old = petitions.Petition("e-2", "c", (), date(2026, 9, 1), "A", 10, "u")
    assert opp.score(opp.from_petition(old, "t", ["housing"]), {"housing"}, set(), set(), TODAY, p=old).score == -1
