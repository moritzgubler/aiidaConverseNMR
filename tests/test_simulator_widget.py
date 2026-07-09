"""Headless smoke tests for the standalone simulator widget.

Skipped when the GUI stack (ipywidgets/plotly + anywidget) is unavailable --
the rest of the suite stays numpy/scipy-only.
"""

import pytest

ipw = pytest.importorskip("ipywidgets")
go = pytest.importorskip("plotly.graph_objects")
pytest.importorskip("anywidget")  # plotly's FigureWidget backend

from aiida_qe_converse.app_simulator.widget import QuadrupolarSimulatorWidget


@pytest.fixture
def widget():
    return QuadrupolarSimulatorWidget()


def _figure(widget):
    (child,) = widget._plot.children
    assert isinstance(child, go.FigureWidget)
    return child


def test_initial_powder_plot(widget):
    """Default state (23Na, 9.4 T, Vzz=0.1) renders a powder lineshape."""
    fig = _figure(widget)
    assert len(fig.data) == 1
    assert not widget._download.disabled
    assert "ν<sub>L</sub>" in widget._info.value
    assert widget._export["blocks"][0][0] == "powder lineshape"


def test_isotope_seeding(widget):
    widget._element.value = "Al"
    assert widget._isotope.value == "27Al"
    assert widget._I.value == pytest.approx(2.5)
    assert widget._gamma.value == pytest.approx(11.1031)
    # C_q kept as typed; nu_Q follows the new I: 3*3.0 / (2*2.5*4) = 0.45
    assert widget._cq.value == pytest.approx(3.0)
    assert widget._nuq.value == pytest.approx(0.45)


def test_manual_ig_edit_flips_to_custom(widget):
    widget._I.value = 2.5  # Na has no I = 5/2 isotope
    assert widget._isotope.value == "custom"
    # restoring the tabulated (I, gamma) flips back to the matching isotope
    widget._I.value = 1.5
    assert widget._isotope.value == "23Na"


def test_cq_nuq_linkage(widget):
    # default 23Na (I = 3/2): nu_Q = C_q / 2
    assert widget._nuq.value == pytest.approx(widget._cq.value / 2.0)
    widget._cq.value = 2.0
    assert widget._nuq.value == pytest.approx(1.0)
    widget._nuq.value = 3.0
    assert widget._cq.value == pytest.approx(6.0)
    # I change keeps C_q, re-derives nu_Q: 3*6 / (2*2.5*4) = 0.9
    widget._I.value = 2.5
    assert widget._cq.value == pytest.approx(6.0)
    assert widget._nuq.value == pytest.approx(0.9)
    # spin-1/2: conversion singular, nu_Q disabled, C_q untouched
    widget._element.value = "C"
    assert widget._nuq.disabled
    assert widget._cq.value == pytest.approx(6.0)
    widget._element.value = "Na"
    assert not widget._nuq.disabled
    assert widget._nuq.value == pytest.approx(3.0)  # 6.0 / 2 for I = 3/2


def test_spin_half_shows_hint(widget):
    widget._element.value = "C"  # 13C: I = 1/2
    (child,) = widget._plot.children
    assert isinstance(child, ipw.HTML)
    assert "I >= 1" in child.value
    assert widget._download.disabled


def test_single_crystal_mode(widget):
    widget._mode.value = "single"
    fig = _figure(widget)
    # broadened envelope + (stick + label) per transition, 2I = 3 for 23Na
    assert len(fig.data) == 1 + 2 * 3
    assert widget._crystal_box.layout.display != "none"
    assert widget._powder_box.layout.display == "none"
    assert "θ = 0.0°" in widget._info.value


def test_powder_decompose_and_overlay(widget):
    widget._decompose.value = True
    widget._overlay.value = True
    fig = _figure(widget)
    # total + 3 per-transition curves + 3 sticks x 2 traces
    assert len(fig.data) == 1 + 3 + 6
    titles = [b[0] for b in widget._export["blocks"]]
    assert titles == ["powder lineshape, decomposed by transition",
                      "single-crystal peak positions"]


def test_eigenvector_warning_and_orthonormalize(widget):
    widget._mode.value = "single"
    widget._eig_cells[0][1].value = 0.4  # shear Vxx towards Vyy
    assert "not" in widget._eig_warning.value
    assert widget._eig_fix.layout.display != "none"
    widget._on_orthonormalize()
    assert widget._eig_warning.value == ""
    assert widget._eig_fix.layout.display == "none"
    # still plots fine after the fix
    assert isinstance(widget._plot.children[0], go.FigureWidget)


def test_second_order_inactive_at_zero_field(widget):
    """At nu_L = 0 the backend drops eq 2.29: the CSV must say so, not lie."""
    widget._B.value = 0.0
    assert widget._second.value  # checkbox still checked
    assert dict(widget._export["meta"])["second_order"] is False
    assert "2nd-order term inactive" in widget._info.value


def test_gamma_reseeded_on_isotope_switch(widget):
    """Switching to an isotope without tabulated gamma must not keep the old one."""
    widget._element.value = "H"  # default 1H: spin 1/2, gamma None -> 0.0
    assert widget._gamma.value == 0.0
    widget._isotope.value = "2H"
    assert widget._gamma.value == pytest.approx(6.5359)
    widget._isotope.value = "1H"
    assert widget._gamma.value == 0.0


def test_broadening_cannot_go_negative(widget):
    widget._broad.value = -5.0  # BoundedFloatText clamps to min
    assert widget._broad.value == 0.0


def test_csv_export_payload(widget):
    from aiida_qe_converse.postprocessing.spectrum_export import spectrum_csv

    meta_keys = [k for k, _v in widget._export["meta"]]
    for key in ("isotope", "B_T", "gamma_MHz_per_T", "nu_L_MHz", "I",
                "Cq_MHz", "nu_Q_MHz", "eta", "second_order"):
        assert key in meta_keys
    text = spectrum_csv(widget._export["meta"], widget._export["blocks"])
    assert "nu_minus_nuL_kHz" in text
