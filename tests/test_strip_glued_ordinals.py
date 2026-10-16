import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "strip_glued_ordinals",
    Path(__file__).resolve().parents[1] / "scripts" / "strip_glued_ordinals.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_glued_ordinals_come_off_read_rows_but_not_typed_ones():
    record = {"rows": [
        {"n": 1, "name_raw": "1Ismenia Pinto Saldanha"},
        {"n": 7, "name_raw": "Elli Bardavid"},
        {"n": 15, "name_raw": "5Haim Bardavid", "verified": True},
    ]}
    changed = mod.strip_record(record)
    assert changed == [("1Ismenia Pinto Saldanha", "Ismenia Pinto Saldanha")]
    assert record["rows"][0]["name_raw"] == "Ismenia Pinto Saldanha"
    assert record["rows"][2]["name_raw"] == "5Haim Bardavid"
