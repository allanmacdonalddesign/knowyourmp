from pathlib import Path

from civic.sources import billtext

FIX = Path(__file__).parent / "fixtures"


def test_summary_skips_table_of_contents_entry():
    s = billtext.parse_summary((FIX / "bill_text_excerpt.html").read_text())
    assert s.startswith("Part 1 enacts") and "interprovincial trade" in s
    assert billtext.parse_summary("<p>SUMMARY</p><p>TABLE OF PROVISIONS</p>") is None


def test_table_of_contents_under_summary_is_not_a_summary():
    html = "<p>SUMMARY</p><p>1 Short Title 1 Short Title 2 Interpretation 2 Interpretation 3 National Framework on the Durability of Electronic Products</p>"
    assert billtext.parse_summary(html) is None


def test_refusals_and_rambles_are_not_usable_descriptions():
    from civic.analysis.plain import usable

    assert usable("Creates a national framework to make home appliances last longer.")
    assert not usable("I don't have access to the actual content of this bill, only its title.")
    assert not usable("Short")
    assert not usable("x" * 300)
