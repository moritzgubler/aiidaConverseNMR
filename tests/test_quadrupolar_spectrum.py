"""Tests for the quadrupolar powder spectrum simulator core (no AiiDA)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.postprocessing.quadrupolar_spectrum import (
    powder_spectrum,
    single_crystal_lines,
    lattice_direction_to_angles,
    transition_weight,
    _transition_m_values,
    _AB,
)
from aiida_qe_converse.data.nuclear import larmor_frequency, default_gamma


def test_transition_count():
    # number of transitions |m-1>->|m> equals 2I
    assert len(_transition_m_values(1.0)) == 2
    assert len(_transition_m_values(1.5)) == 3
    assert len(_transition_m_values(2.5)) == 5
    # central transition (m=1/2) present for half-integer spin
    assert any(abs(m - 0.5) < 1e-9 for m in _transition_m_values(1.5))


def test_requires_spin_one():
    with pytest.raises(ValueError):
        powder_spectrum(nu_Q=3.0, eta=0.0, spin_I=0.5, nu_L=10.0)


def test_output_shapes_and_normalisation():
    freqs, inten = powder_spectrum(nu_Q=3.0, eta=0.0, spin_I=1.5, nu_L=10.0,
                                   n_theta=60, n_phi=60, n_bins=500)
    assert freqs.shape == (500,)
    assert inten.shape == (500,)
    assert np.isfinite(inten).all()
    assert abs(inten.max() - 1.0) < 1e-12   # normalised to unit maximum
    assert (inten >= 0).all()


def test_first_order_satellites_span_nu_Q():
    # For I=3/2, eta=0, the first-order satellites extend out to about +-nu_Q
    # around nu_L (theta=0 feature at +-nu_Q). Window should comfortably include them.
    nu_L, nu_Q = 10.0, 3.0
    freqs, inten = powder_spectrum(nu_Q=nu_Q, eta=0.0, spin_I=1.5, nu_L=nu_L,
                                   n_theta=120, n_phi=120, n_bins=800)
    # intensity-weighted spread of the spectrum, relative to nu_L
    mask = inten > 1e-3
    spread = (freqs[mask] - nu_L)
    assert spread.max() > 0.5 * nu_Q
    assert spread.min() < -0.5 * nu_Q


def test_central_transition_at_larmor_for_eta_zero():
    # The central -1/2<->1/2 line sits at nu_L (first order vanishes); the global
    # spectrum should carry significant weight in a narrow band around nu_L.
    nu_L = 10.0
    freqs, inten = powder_spectrum(nu_Q=2.0, eta=0.0, spin_I=1.5, nu_L=nu_L,
                                   n_theta=120, n_phi=120, n_bins=800,
                                   broadening=0.05)
    near = inten[np.abs(freqs - nu_L) < 0.3]
    assert near.size > 0 and near.max() > 0.1


def test_AB_finite_over_grid():
    theta = np.linspace(0, np.pi, 11)
    phi = np.linspace(0, 2 * np.pi, 13)
    tg, pg = np.meshgrid(theta, phi)
    A, B = _AB(0.5, tg.ravel(), pg.ravel())
    assert np.isfinite(A).all() and np.isfinite(B).all()


def test_single_crystal_central_line_at_larmor():
    # I=3/2, central transition m=1/2 -> 1-2m=0 so first order vanishes; with
    # nu_L large the second-order shift is tiny, so the central line ~ nu_L.
    lines = single_crystal_lines(nu_Q=2.0, eta=0.0, spin_I=1.5, nu_L=100.0,
                                 theta=0.3, phi=0.7)
    central = [f for (f, w, m) in lines if abs(m - 0.5) < 1e-9][0]
    assert abs(central - 100.0) < 1.0  # within ~1 MHz of nu_L
    # 2I transitions, weights match eq 2.33
    assert len(lines) == 3
    for f, w, m in lines:
        assert abs(w - transition_weight(m, 1.5)) < 1e-9


def test_single_crystal_first_order_satellites_symmetric():
    # eta=0, theta=0: first-order satellite shift = (1/4) nu_Q (1-2m) * 2.
    # For m=3/2 and m=-1/2 (the two satellites of I=3/2) the shifts are +-nu_Q.
    nuL, nuQ = 1000.0, 3.0  # huge nu_L so 2nd order ~ 0
    lines = single_crystal_lines(nu_Q=nuQ, eta=0.0, spin_I=1.5, nu_L=nuL,
                                 theta=0.0, phi=0.0)
    shifts = sorted(round(f - nuL, 3) for (f, w, m) in lines)
    # central ~0, satellites ~ +-nu_Q
    assert abs(shifts[1]) < 1e-2
    assert abs(shifts[0] + nuQ) < 1e-2
    assert abs(shifts[2] - nuQ) < 1e-2


def test_lattice_direction_to_angles_aligned():
    import numpy as np
    cell = np.eye(3)  # cubic, Cartesian == lattice
    axes = {"Vxx": [1, 0, 0], "Vyy": [0, 1, 0], "Vzz": [0, 0, 1]}
    # field along c -> along Vzz -> theta = 0
    theta, phi = lattice_direction_to_angles([0, 0, 5.0], cell, axes)
    assert abs(theta) < 1e-9
    # field along a -> in plane, theta = 90 deg, phi = 0
    theta, phi = lattice_direction_to_angles([2.0, 0, 0], cell, axes)
    assert abs(theta - np.pi / 2) < 1e-9
    assert abs(phi) < 1e-9
    # field along b -> theta = 90, phi = 90 deg
    theta, phi = lattice_direction_to_angles([0, 1.0, 0], cell, axes)
    assert abs(phi - np.pi / 2) < 1e-9


def test_lattice_direction_uses_cell_vectors():
    import numpy as np
    # non-orthogonal cell: a1 along x, a2 in xy-plane; field = a2 should not be along x
    cell = np.array([[1.0, 0, 0], [1.0, 1.0, 0], [0, 0, 1.0]])
    axes = {"Vxx": [1, 0, 0], "Vyy": [0, 1, 0], "Vzz": [0, 0, 1]}
    theta, phi = lattice_direction_to_angles([0, 1.0, 0], cell, axes)
    # a2 = (1,1,0)/sqrt2 -> in xy plane (theta=90), phi=45 deg
    assert abs(theta - np.pi / 2) < 1e-9
    assert abs(phi - np.pi / 4) < 1e-9


def test_larmor_frequency():
    # 17O gamma ~5.7742 MHz/T -> at 9.4 T, nu_L ~ 54.3 MHz
    nu = larmor_frequency("O", 9.4)
    assert nu is not None and abs(nu - 5.7742 * 9.4) < 1e-3
    # override gamma
    assert abs(larmor_frequency("O", 10.0, gamma=4.0) - 40.0) < 1e-9
    # unknown / non-quadrupolar element -> None
    assert default_gamma("Si") is None
    assert larmor_frequency("Si", 9.4) is None


def test_lebedev_method_matches_grid_shape_and_norm():
    import numpy as np
    f1, i1 = powder_spectrum(3.0, 0.2, 1.5, 10.0, n_bins=400, method="grid")
    f2, i2 = powder_spectrum(3.0, 0.2, 1.5, 10.0, n_bins=400, method="lebedev",
                             lebedev_order=53)
    assert f1.shape == i1.shape == (400,)
    assert f2.shape == i2.shape == (400,)
    assert abs(i2.max() - 1.0) < 1e-12
    # both methods should place the spectral weight in a similar window
    assert abs((f1[i1 > 0.1].mean()) - (f2[i2 > 0.1].mean())) < 0.5


def test_broaden_lines():
    import numpy as np
    from aiida_qe_converse.postprocessing.quadrupolar_spectrum import (
        broaden_lines, single_crystal_lines)
    lines = single_crystal_lines(3.0, 0.0, 1.5, 1000.0, theta=0.0, phi=0.0)
    x, y = broaden_lines(lines, broadening=0.1, n_points=4000)
    assert x.shape == y.shape == (4000,)
    assert abs(y.max() - 1.0) < 1e-9
    # peaks should sit near the line positions
    for f, w, m in lines:
        assert y[np.argmin(np.abs(x - f))] > 0.3
