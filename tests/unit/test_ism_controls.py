from src.shared.ism_controls import get_ism_control, ISMControlSpec


def test_lookup_known_control():
    c = get_ism_control("ISM-1546")
    assert isinstance(c, ISMControlSpec)
    assert "MFA" in c.intent or "multi-factor" in c.intent.lower()


def test_lookup_unknown_raises():
    import pytest
    with pytest.raises(KeyError):
        get_ism_control("ISM-9999")
