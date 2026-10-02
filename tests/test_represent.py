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
