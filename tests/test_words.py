import math
from types import SimpleNamespace

from civic.analysis import words
from civic.sources import openparliament as op

S = lambda text, when="2026-01-01 10:00:00": SimpleNamespace(text=text, time=when)


def test_phrases_are_counted_once_and_filler_is_dropped():
    speeches = [S("<p>Mr. Speaker, carbon pricing works. Carbon pricing cuts emissions.</p>"),
                S("We need carbon pricing and a price on pollution.", "2026-03-02 11:00:00"),
                S("Carbon pricing again. A price on pollution, a price on pollution, a price on pollution.")]
    got = {t.term: t for t in words.top_terms(speeches)}
    assert got["carbon pricing"].count == 4 and got["carbon pricing"].speeches == 3
    assert got["price on pollution"].count == 4 and got["price on pollution"].last_said == "2026-03-02"
    assert "carbon" not in got and "pricing" not in got  # their uses all sit inside the phrase
    assert "speaker" not in got and "need" not in got


def test_years_count_but_stray_numbers_do_not():
    got = {t.term for t in words.top_terms([S("By 2030 we cut 45 percent. 2030 matters.")])}
    assert "2030" in got and "45" not in got


def test_pack_has_no_overlaps_and_stays_inside():
    counts = [214, 198, 171, 120, 96, 60, 40, 20, 12, 9, 9, 9]
    placed = words.pack(counts, 600, 300)
    assert len(placed) == len(counts)
    for i, (x, y, r) in enumerate(placed):
        assert r > 0 and x - r >= -0.01 and y - r >= -0.01 and x + r <= 600.01 and y + r <= 300.01
        for x2, y2, r2 in placed[i + 1:]:
            assert math.hypot(x - x2, y - y2) >= r + r2 - 0.01
    assert placed[0][2] > placed[-1][2]  # bigger count, bigger circle


class FakeFetcher:
    def __init__(self, page):
        self.page = page

    def get_text(self, url, params=None, max_age=0):
        return self.page


def test_last_election_parsed_from_openparliament_page():
    page = '<p><strong>Won</strong> his last election, in 2025, with 52% of the vote.</p>'
    e = op.last_election(FakeFetcher(page), "steven-guilbeault")
    assert (e.won, e.year, e.share) == (True, "2025", 52)
    assert op.last_election(FakeFetcher("<p>nothing here</p>"), "x") is None
    assert op.favourite_word({"other_info": {"favourite_word": ["conservative"]}}) == "conservative"
    assert op.favourite_word({}) is None
