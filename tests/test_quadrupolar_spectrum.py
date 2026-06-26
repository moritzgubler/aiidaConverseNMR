"""Tests for the quadrupolar powder spectrum simulator core (no AiiDA)."""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.postprocessing.quadrupolar_spectrum import (
    powder_spectrum,
    _transition_m_values,
    _AB,
)


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
