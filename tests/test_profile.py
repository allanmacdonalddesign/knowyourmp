from civic.analysis.profile import build_profile
from civic.sources.openparliament import Bill, Speech
from civic.sources.ourcommons_member import MemberRoles
from civic.sources.represent import MP

MP_ = MP("A B", "Liberal", "Somewhere", None, "https://www.ourcommons.ca/x")


def test_separates_chosen_from_assigned_and_cites():
    speeches = [
        Speech("/debates/1/", "2026-01-01 10:00", "Statements by Members", "Arena", "text", None),
        Speech("/debates/2/", "2026-01-02 10:00", "Government Orders", "Bill", "text", None),
        Speech("/committees/x/", "2026-01-03 10:00", None, None, "text", None),
    ]
    bills = [Bill("/bills/45-1/C-1/", "C-1", "45-1", "T", True, "s"), Bill("/bills/45-1/C-2/", "C-2", "45-1", "T", False, "s")]
    p = build_profile(MP_, "a-b", MemberRoles(["Member of Parliament"], [("TRAN", "Transport")]), speeches, bills)
    assert len(p.champions) == 2  # statement + PMB only; government bill and debate speeches excluded
    assert all(c.url.startswith("https://") for c in p.champions + p.responsible_for)
    assert p.assigned_activity == {"Government Orders": 1, "Committee": 1}
