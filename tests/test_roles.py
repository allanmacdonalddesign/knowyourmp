from pathlib import Path

from civic.sources.ourcommons_member import parse_roles

FIX = Path(__file__).parent / "fixtures"


def test_parse_roles_from_real_page():
    r = parse_roles((FIX / "ourcommons_member.html").read_text())
    assert ("FEWO", "Standing Committee on the Status of Women") in r.committees
    assert ("TRAN", "Standing Committee on Transport, Infrastructure and Communities") in r.committees
    assert "Member of Parliament" in r.roles
