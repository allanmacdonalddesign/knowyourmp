from pathlib import Path

from civic.sources import openparliament as op
from civic.sources.ourcommons_member import parse_roles

FIX = Path(__file__).parent / "fixtures"


class FakeFetcher:
    """name filter finds nothing (as happened for Steven Guilbeault); direct slug works."""

    def __init__(self, records):
        self.records = records

    def get_json(self, url, params=None, max_age=0):
        if url.endswith("/politicians/"):
            return {"objects": []}
        slug = url.rstrip("/").split("/")[-1]
        if slug not in self.records:
            raise RuntimeError("404")
        return self.records[slug]


def test_slugify_handles_accents_and_punctuation():
    assert op.slugify("Joël Godin") == "joel-godin"
    assert op.slugify("Ginette Petitpas Taylor") == "ginette-petitpas-taylor"
    assert op.slugify("Xavier Barsalou-Duval") == "xavier-barsalou-duval"


def test_find_slug_falls_back_to_direct_slug_and_verifies_member_id():
    f = FakeFetcher({"steven-guilbeault": {"name": "Steven Guilbeault", "other_info": {"parl_mp_id": ["14171"]}}})
    assert op.find_slug(f, "Steven Guilbeault", "14171") == "steven-guilbeault"
    assert op.find_slug(f, "Steven Guilbeault", "99999") is None  # same name, different person: never guess


def test_parl_id_from_url():
    assert op.parl_id_from_url("https://www.ourcommons.ca/Members/en/steven-guilbeault(14171)") == "14171"
    assert op.parl_id_from_url(None) is None


def test_roles_stop_at_all_roles():
    kwan = parse_roles((FIX / "member_roles_kwan.html").read_text())
    assert kwan.roles == ["Member of Parliament", "Vancouver East, British Columbia"]  # was 270 junk lines
    pt = parse_roles((FIX / "member_roles_petitpas.html").read_text())
    assert "Member of the Joint Interparliamentary Council" in pt.roles and len(pt.roles) == 4
