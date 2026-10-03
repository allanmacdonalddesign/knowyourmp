import json
from pathlib import Path

import pytest

from civic.sources import represent

FIX = Path(__file__).parent / "fixtures"


def test_normalize():
    assert represent.normalize("m5v 3l9") == "M5V3L9"
    with pytest.raises(represent.InvalidPostalCode):
        represent.normalize("12345")


def test_single_mp_from_real_sample():
    mps = represent.parse_mps(json.loads((FIX / "represent_postcode_M5V3L9.json").read_text()))
    assert [(m.name, m.riding) for m in mps] == [("Chi Nguyen", "Spadina—Harbourfront")]


def test_split_postcode_returns_both_mps():
    # SYNTHETIC fixture: no real straddling federal postcode found yet (see docs/data-notes.md).
    rep = lambda n, d: {"elected_office": "MP", "name": n, "district_name": d, "party_name": "X"}
    data = {
        "representatives_centroid": [rep("A", "Riding 1"), {"elected_office": "MLA", "name": "Z"}],
        "representatives_concordance": [rep("B", "Riding 2"), rep("A", "Riding 1")],
    }
    assert [m.name for m in represent.parse_mps(data)] == ["A", "B"]


def test_postcode_lookup_is_never_cached():
    import httpx

    from civic import cache
    from civic.http import Fetcher

    body = (FIX / "represent_postcode_M5V3L9.json").read_text()
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=body)))
    db = cache.connect(":memory:")
    f = Fetcher(cache.HttpCache(db), min_interval=0, client=client)
    assert [m.name for m in represent.lookup(f, "M5V 3L9")] == ["Chi Nguyen"]
    assert db.execute("SELECT COUNT(*) FROM http_cache").fetchone()[0] == 0


def test_connect_purges_old_postcode_rows(tmp_path):
    from civic import cache

    path = tmp_path / "cache.db"
    db = cache.connect(path)
    db.execute("INSERT INTO http_cache VALUES (?,?,?)", ("https://represent.opennorth.ca/postcodes/A1A1A1/", "{}", 0))
    db.execute("INSERT INTO http_cache VALUES (?,?,?)", ("https://api.openparliament.ca/bills/", "{}", 0))
    db.commit()
    db.close()
    keys = [k for (k,) in cache.connect(path).execute("SELECT key FROM http_cache")]
    assert keys == ["https://api.openparliament.ca/bills/"]


ROSTER = {"objects": [
    {"elected_office": "MP", "name": "René Côté", "district_name": "A", "party_name": "X"},
    {"elected_office": "MP", "name": "Chi Nguyen", "district_name": "B", "party_name": "X"},
    {"elected_office": "MP", "name": "Chi Nguyen-Smith", "district_name": "C", "party_name": "X"},
    {"elected_office": "MP", "name": "Erin O'Toole", "district_name": "D", "party_name": "X"},
    {"elected_office": "MLA", "name": "Chi Nguyen", "district_name": "E"},
]}


def test_name_match_ignores_accents_case_and_word_order():
    assert [m.name for m in represent.match_name(ROSTER, "rene cote")] == ["René Côté"]
    assert [m.name for m in represent.match_name(ROSTER, "COTE rené")] == ["René Côté"]
    assert [m.name for m in represent.match_name(ROSTER, "o toole")] == ["Erin O'Toole"]


def test_exact_name_beats_partial_matches():
    assert [m.riding for m in represent.match_name(ROSTER, "Chi Nguyen")] == ["B"]
    assert len(represent.match_name(ROSTER, "nguyen")) == 2  # last name alone: user must choose


def test_name_match_skips_non_mps_and_rejects_blank():
    assert represent.match_name(ROSTER, "zzz") == []
    with pytest.raises(represent.InvalidName):
        represent.match_name(ROSTER, "  ")
