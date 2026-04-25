from src.entity_grounding_gate.entity_extraction import extract_entities


def test_extracts_principals_from_narrative_text():
    txt = "Login `svc_etl` has admin on `appdb_prod` per ISM-1546."
    e = extract_entities(txt)
    assert "svc_etl" in e["principals"]
    assert "appdb_prod" in e["databases"]
    assert "ISM-1546" in e["controls"]


def test_extracts_dates_and_numbers():
    txt = "12 findings detected on 2026-04-25"
    e = extract_entities(txt)
    assert "2026-04-25" in e["dates"]
    assert 12 in e["numbers"]


def test_handles_empty_narrative():
    e = extract_entities("")
    assert e == {
        "principals": set(),
        "databases": set(),
        "controls": set(),
        "dates": set(),
        "numbers": set(),
    }
