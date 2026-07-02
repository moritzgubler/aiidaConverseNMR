"""Tests for recomputing quadrupolar parameters from the EFG tensor (no AiiDA)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.postprocessing.efg_analysis import (
    CQ_MHZ_PER_Q_VZZ,
    principal_values,
    quadrupolar_parameters_from_tensor,
)

# symmetric traceless tensor with an off-diagonal block (O-site-like)
O_TENSOR = [
    [-0.30, 0.05, 0.00],
    [0.05, -0.40, 0.00],
    [0.00, 0.00, 0.70],
]


def test_principal_values_ordering_and_eigen():
    v, axes = principal_values(O_TENSOR)
    # |Vzz| >= |Vyy| >= |Vxx|
    assert abs(v[2]) >= abs(v[1]) >= abs(v[0])
    # exact eigenvalues of the 2x2 block: -0.35 +- sqrt(2)*0.05; plus 0.7
    lo = -0.35 - 0.05 * np.sqrt(2)
    hi = -0.35 + 0.05 * np.sqrt(2)
    assert np.isclose(v[2], 0.70)
    assert np.isclose(v[1], lo)
    assert np.isclose(v[0], hi)
    # eigenvectors: A @ e_k = v_k e_k
    t = np.array(O_TENSOR)
    for k in range(3):
        assert np.allclose(t @ axes[:, k], v[k] * axes[:, k], atol=1e-12)


def test_full_parameters_17O():
    qp = quadrupolar_parameters_from_tensor(O_TENSOR, quadrupole_moment=-2.558, spin=2.5)
    assert np.isclose(qp["Vzz"], 0.70)
    # eta = (Vxx - Vyy)/Vzz in [0, 1]
    assert 0.0 <= qp["eta"] <= 1.0
    assert np.isclose(qp["eta"], (qp["Vxx"] - qp["Vyy"]) / qp["Vzz"])
    # Cq = const * Q * Vzz, with the efg.f90 constant (~2.3496 MHz per Q*Vzz)
    assert np.isclose(CQ_MHZ_PER_Q_VZZ, 2.3496, atol=2e-3)
    assert np.isclose(qp["Cq"], CQ_MHZ_PER_Q_VZZ * (-2.558) * 0.70)
    # nu_Q = 3 Cq / (2I(2I-1)) = 3 Cq / 20 for I=5/2
    assert np.isclose(qp["nu_Q"], 3.0 * qp["Cq"] / 20.0)
    # eigenvector dict format matches the parser output convention
    assert set(qp["eigenvectors"]) == {"Vxx", "Vyy", "Vzz"}
    assert np.allclose(qp["eigenvectors"]["Vzz"], [0, 0, 1]) or \
        np.allclose(qp["eigenvectors"]["Vzz"], [0, 0, -1])


def test_q_zero_and_spin_half_give_none():
    qp = quadrupolar_parameters_from_tensor(O_TENSOR, quadrupole_moment=0.0, spin=2.5)
    assert qp["Cq"] is None and qp["nu_Q"] is None
    # Q != 0 but I = 1/2: Cq defined, nu_Q not
    qp = quadrupolar_parameters_from_tensor(O_TENSOR, quadrupole_moment=-2.558, spin=0.5)
    assert qp["Cq"] is not None and qp["nu_Q"] is None


def test_asymmetric_input_is_symmetrized():
    # small parsing round-off asymmetry must not break eigh-based analysis
    t = np.array(O_TENSOR)
    t[0, 1] += 1e-6
    qp = quadrupolar_parameters_from_tensor(t, quadrupole_moment=1.0, spin=1.5)
    assert np.isclose(qp["Vzz"], 0.70, atol=1e-5)
