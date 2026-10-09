"""The hospedaria register reader, minus the models: which pages it reads."""
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
mod = runpy.run_path(str(ROOT / "scripts" / "read_hospedaria.py"))


def test_only_the_odd_pages_carry_names_and_a_read_page_is_skipped(tmp_path):
    pdf = tmp_path / "BR_RJANRIO_OB_0_EPE_HIF_0110_d0001de0001.pdf"
    pdf.write_bytes(b"")
    mod["page_file"](tmp_path, "0110", 3).write_text("{}")
    got = mod["pages_wanted"]([pdf], tmp_path, parity="odd", count=lambda pdf: 6)
    assert [(b, n) for _, b, n in got] == [("0110", 1), ("0110", 5)]
    assert len(mod["pages_wanted"]([pdf], tmp_path, count=lambda pdf: 6)) == 5
