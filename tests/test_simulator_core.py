"""Tests for the standalone simulator's pure computation layer.

No AiiDA profile needed. Importing ``app_simulator`` pulls in the app's full
dependency stack (ipywidgets/plotly); skip when it is not installed.
"""

import numpy as np
import pytest

pytest.importorskip("ipywidgets")
pytest.importorskip("plotly")

from aiida_qe_converse.app_simulator import core
from aiida_qe_converse.postprocessing.efg_analysis import (
    quadrupolar_parameters_from_tensor,
)


def _diagonal_tensor(vzz, eta):
    """Traceless diagonal EFG tensor with the given Vzz and eta."""
    return np.diag([-(1.0 - eta) * vzz / 2.0, -(1.0 + eta) * vzz / 2.0, vzz])


@pytest.mark.parametrize("vzz,eta,q,spin", [
    (0.1, 0.0, 10.4, 1.5),    # 23Na-like
    (-0.35, 0.6, -2.558, 2.5),  # 17O-like
])
def test_derived_parameters_matches_tensor_path(vzz, eta, q, spin):
    """Entering the DFT-derived Cq reproduces the DFT-tensor path's nu_Q."""
    ref = quadrupolar_parameters_from_tensor(_diagonal_tensor(vzz, eta), q, spin)
    got = core.derived_parameters(ref["Cq"], spin, gamma=11.0, field_T=9.4)
    assert got["nu_Q"] == pytest.approx(ref["nu_Q"])
    assert got["nu_L"] == pytest.approx(11.0 * 9.4)


def test_cq_nuq_roundtrip():
    for cq, spin in [(3.0, 1.5), (-1.2, 2.5), (0.7, 4.5)]:
        nuq = core.nu_q_from_cq(cq, spin)
        assert core.cq_from_nu_q(nuq, spin) == pytest.approx(cq)
    # I = 3/2: nu_Q = Cq / 2
    assert core.nu_q_from_cq(3.0, 1.5) == pytest.approx(1.5)
    # singular for I < 1 (no quadrupole interaction)
    assert core.nu_q_from_cq(3.0, 0.5) is None
    assert core.cq_from_nu_q(1.5, 0.5) is None


def test_derived_parameters_none_cases():
    assert core.derived_parameters(3.0, 0.5, 11.0, 9.4)["nu_Q"] is None
    # neither the gamma sign nor the field sign may matter (nu_L = |gamma.B|)
    assert core.derived_parameters(3.0, 1.5, -11.0, 9.4)["nu_L"] == \
        pytest.approx(11.0 * 9.4)
    assert core.derived_parameters(3.0, 1.5, 11.0, -9.4)["nu_L"] == \
        pytest.approx(11.0 * 9.4)


def test_powder_decomposition_sums_to_total():
    result = core.simulate(1.2, 0.3, 2.5, 100.0, mode="powder",
                           n_grid=80, decompose=True)
    per_sum = np.sum([inten for _m, inten in result["per_transition"]], axis=0)
    assert np.allclose(per_sum, result["total"])
    assert len(result["per_transition"]) == 5  # 2I transitions for I = 5/2
    assert result["lines"] is None and result["envelope"] is None


def test_powder_first_order_central_transition_at_nu_L():
    """Without the 2nd-order term the central transition sits exactly at nu_L."""
    nu_L = 100.0
    result = core.simulate(1.2, 0.0, 1.5, nu_L, mode="powder",
                           n_grid=80, decompose=True, second_order=False)
    central = next(inten for m, inten in result["per_transition"]
                   if abs(m - 0.5) < 1e-9)
    freqs = result["freqs"]
    mean = np.sum(freqs * central) / np.sum(central)
    bin_width = freqs[1] - freqs[0]
    assert abs(mean - nu_L) < bin_width


def test_single_crystal_identity_frame():
    """Identity cell/eigenvectors with direction (0,0,1) means theta = 0."""
    result = core.simulate(1.2, 0.3, 1.5, 100.0, mode="single",
                           cell=np.eye(3), eigenvectors=np.eye(3),
                           direction=[0.0, 0.0, 1.0])
    assert result["theta"] == pytest.approx(0.0)
    assert len(result["lines"]) == 3  # 2I transitions for I = 3/2
    assert result["envelope"] is None  # no broadening requested


def test_single_crystal_rotated_frame_matches_identity():
    """Rotating eigenvectors and direction together leaves the lines unchanged."""
    rng = np.random.default_rng(42)
    rot = core.orthonormalize(rng.normal(size=(3, 3)))
    direction = np.array([0.3, -0.2, 0.9])
    ref = core.simulate(1.2, 0.6, 2.5, 100.0, mode="single",
                        cell=np.eye(3), eigenvectors=np.eye(3),
                        direction=direction)
    # rows of `rot` are the rotated principal axes; the field must rotate the
    # same way to keep its coordinates in the EFG frame: b' = b @ rot solves
    # b' . row_i = b_i since rot is orthogonal
    got = core.simulate(1.2, 0.6, 2.5, 100.0, mode="single",
                        cell=np.eye(3), eigenvectors=rot,
                        direction=direction @ rot)
    for (f1, w1, m1), (f2, w2, m2) in zip(ref["lines"], got["lines"]):
        assert f2 == pytest.approx(f1)
        assert w2 == pytest.approx(w1)
        assert m2 == m1


def test_powder_overlay_peaks():
    result = core.simulate(1.2, 0.3, 1.5, 100.0, mode="powder", n_grid=40,
                           overlay_peaks=True, cell=np.eye(3),
                           eigenvectors=np.eye(3), direction=[0, 0, 1])
    assert result["total"] is not None
    assert len(result["lines"]) == 3
    assert result["theta"] == pytest.approx(0.0)


def test_single_crystal_broadening_envelope():
    result = core.simulate(1.2, 0.3, 1.5, 100.0, mode="single",
                           broadening=0.005, cell=np.eye(3),
                           eigenvectors=np.eye(3), direction=[0, 0, 1])
    gx, gy = result["envelope"]
    assert len(gx) and gy.max() == pytest.approx(1.0)


def test_validate_and_orthonormalize():
    ok, dev = core.validate_eigenvectors(np.eye(3))
    assert ok and dev == pytest.approx(0.0)
    # pure row scaling is fine (rows get normalized)
    ok, _ = core.validate_eigenvectors(np.diag([2.0, 0.5, 7.0]))
    assert ok
    sheared = np.eye(3) + 0.1 * np.array([[0, 1, 0], [0, 0, 0], [0, 0, 0]])
    ok, dev = core.validate_eigenvectors(sheared)
    assert not ok and dev > 1e-3
    fixed = core.orthonormalize(sheared)
    ok, _ = core.validate_eigenvectors(fixed)
    assert ok
    assert np.max(np.abs(fixed - np.eye(3))) < 0.1  # close to the input
    # a zero row can never be orthonormalized by scaling
    ok, dev = core.validate_eigenvectors([[1, 0, 0], [0, 0, 0], [0, 0, 1]])
    assert not ok


def test_error_messages():
    with pytest.raises(ValueError, match="I >= 1"):
        core.simulate(1.2, 0.0, 0.5, 100.0)
    with pytest.raises(ValueError, match="nu_Q is zero"):
        core.simulate(0.0, 0.0, 1.5, 100.0)
    with pytest.raises(ValueError, match="zero vector"):
        core.simulate(1.2, 0.0, 1.5, 100.0, mode="single", cell=np.eye(3),
                      eigenvectors=np.eye(3), direction=[0.0, 0.0, 0.0])


def test_axes_dict():
    axes = core.axes_dict(np.arange(9.0).reshape(3, 3))
    assert axes["Vxx"] == [0.0, 1.0, 2.0]
    assert axes["Vzz"] == [6.0, 7.0, 8.0]
