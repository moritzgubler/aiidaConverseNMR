"""Tests for the spectrum CSV serializer (no AiiDA)."""
import io
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.postprocessing.spectrum_export import spectrum_csv


def _sample():
    meta = [
        ("atom", "Cu1"),
        ("isotope", "63Cu"),
        ("B_T", 9.4),
        ("nu_Q_MHz", "21.0625 (override)"),
        ("second_order", True),
    ]
    x = np.array([-10.0, 0.0, 10.0])
    y = np.array([0.0, 1.0, 0.5])
    blocks = [("powder lineshape",
               ["nu_minus_nuL_kHz", "nu_MHz", "intensity_total"],
               [x, 100.0 + x / 1000.0, y])]
    return meta, blocks


def test_header_and_data_lines():
    meta, blocks = _sample()
    text = spectrum_csv(meta, blocks)
    lines = text.splitlines()
    assert lines[0].startswith("# EFG quadrupolar NMR spectrum")
    assert "# atom = Cu1" in lines
    assert "# B_T = 9.4" in lines
    assert "# nu_Q_MHz = 21.0625 (override)" in lines
    assert "# second_order = yes" in lines
    # column names are a plain CSV row so spreadsheets align them with the data
    assert "nu_minus_nuL_kHz,nu_MHz,intensity_total" in lines
    # every line is a comment, blank, or a names/data row with the right column count
    for line in lines:
        if line.startswith("#") or not line:
            continue
        assert len(line.split(",")) == 3


def test_numpy_roundtrip():
    meta, blocks = _sample()
    text = spectrum_csv(meta, blocks)
    # the documented numpy recipe: drop comments/blanks, first row = names
    rows = [l for l in text.splitlines() if l and not l.startswith("#")]
    assert rows[0].split(",") == ["nu_minus_nuL_kHz", "nu_MHz", "intensity_total"]
    data = np.loadtxt(rows[1:], delimiter=",")
    assert data.shape == (3, 3)
    np.testing.assert_allclose(data[:, 0], [-10.0, 0.0, 10.0])
    np.testing.assert_allclose(data[:, 2], [0.0, 1.0, 0.5])


def test_multiple_blocks_and_string_column():
    meta, blocks = _sample()
    blocks.append(("single-crystal peak positions",
                   ["nu_minus_nuL_kHz", "weight", "transition"],
                   [[-5.0, 5.0], [1.0, 0.75], ["-1/2<->1/2", "1/2<->3/2"]]))
    text = spectrum_csv(meta, blocks)
    # two blank lines between blocks (gnuplot index convention)
    assert "\n\n\n# single-crystal peak positions\n" in text
    assert "nu_minus_nuL_kHz,weight,transition" in text
    assert "-5,1,-1/2<->1/2" in text


def test_mismatched_columns_raise():
    import pytest
    with pytest.raises(ValueError):
        spectrum_csv([], [("b", ["a", "b"], [[1.0]])])
    with pytest.raises(ValueError):
        spectrum_csv([], [("b", ["a", "b"], [[1.0], [1.0, 2.0]])])
