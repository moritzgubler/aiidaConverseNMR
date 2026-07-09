"""Unit tests for the qe-efg.x output parser (no AiiDA required)."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.parsers.efg_parsing import parse_efg_output
# plain module import (pytest puts this file's directory on sys.path): the
# top-level name `tests` is too generic — conda envs can contain a stray
# site-packages `tests` package that would shadow a `tests.…` import
from sample_efg_output import build_sample_output


# A symmetric, traceless EFG tensor for an O site, with principal values that
# satisfy |Vzz| >= |Vyy| >= |Vxx| (diagonal here for an exact known answer).
O_TENSOR = [
    [-0.30, 0.05, 0.00],
    [0.05, -0.40, 0.00],
    [0.00, 0.00, 0.70],
]
# Diagonal symmetric traceless tensor for an Si site (Q=0 case).
SI_TENSOR = [
    [0.10, 0.00, 0.00],
    [0.00, 0.10, 0.00],
    [0.00, 0.00, -0.20],
]

ATOMS = [
    {
        'elem': 'Si', 'na': 1, 'tensor': SI_TENSOR,
        'principal': {'Vxx': 0.10, 'Vyy': 0.10, 'Vzz': -0.20},
        'axes': {'Vxx': [1, 0, 0], 'Vyy': [0, 1, 0], 'Vzz': [0, 0, 1]},
        'Q': 0.0, 'I': 0.5, 'Cq': 0.0, 'eta': 0.00000, 'nu_Q': 0.0,
    },
    {
        'elem': 'O', 'na': 2, 'tensor': O_TENSOR,
        'principal': {'Vxx': -0.3107, 'Vyy': -0.3893, 'Vzz': 0.7000},
        'axes': {'Vxx': [0.987, -0.159, 0.0], 'Vyy': [0.159, 0.987, 0.0], 'Vzz': [0, 0, 1]},
        'Q': -2.5580, 'I': 2.5, 'Cq': -4.2069, 'eta': 0.11229, 'nu_Q': -0.6310,
    },
    {
        'elem': 'O', 'na': 3, 'tensor': O_TENSOR,
        'principal': {'Vxx': -0.3107, 'Vyy': -0.3893, 'Vzz': 0.7000},
        'axes': {'Vxx': [0.987, -0.159, 0.0], 'Vyy': [0.159, 0.987, 0.0], 'Vzz': [0, 0, 1]},
        'Q': -2.5580, 'I': 2.5, 'Cq': -4.2069, 'eta': 0.11229, 'nu_Q': -0.6310,
    },
]


def _parsed():
    return parse_efg_output(build_sample_output(ATOMS))


def test_natoms_and_convergence():
    result = _parsed()
    assert result['converged'] is True
    # Critical: summary 'Vzz=/eta=' lines must NOT be miscounted as tensor rows.
    assert result['natoms'] == 3


def test_symmetrized_tensor_values():
    result = _parsed()
    si = np.array(result['efg_tensors']['1'])
    o = np.array(result['efg_tensors']['2'])
    assert np.allclose(si, np.array(SI_TENSOR), atol=1e-6)
    assert np.allclose(o, np.array(O_TENSOR), atol=1e-6)


def test_tensor_symmetric_and_traceless():
    result = _parsed()
    for key in ('1', '2', '3'):
        t = np.array(result['efg_tensors'][key])
        assert np.allclose(t, t.T, atol=1e-6), 'EFG tensor must be symmetric'
        assert abs(np.trace(t)) < 1e-6, 'EFG tensor must be traceless'


def test_principal_values_and_eigenvectors():
    result = _parsed()
    pv = result['principal_values']['2']
    assert abs(pv['Vxx'] - (-0.3107)) < 1e-4
    assert abs(pv['Vyy'] - (-0.3893)) < 1e-4
    assert abs(pv['Vzz'] - 0.7000) < 1e-4
    # ordering |Vzz| >= |Vyy| >= |Vxx|
    assert abs(pv['Vzz']) >= abs(pv['Vyy']) >= abs(pv['Vxx'])
    ev = result['eigenvectors']['2']
    assert np.allclose(ev['Vzz'], [0.0, 0.0, 1.0], atol=1e-6)


def test_quadrupolar_parameters_quadrupolar_atom():
    result = _parsed()
    qp = result['quadrupolar_parameters']['2']
    assert abs(qp['Q'] - (-2.5580)) < 1e-4
    assert abs(qp['Cq'] - (-4.2069)) < 1e-4
    assert abs(qp['eta'] - 0.11229) < 1e-5
    assert abs(qp['I'] - 2.5) < 1e-6
    # nu_Q present only for I >= 1
    assert abs(qp['nu_Q'] - (-0.6310)) < 1e-4


def test_quadrupolar_parameters_spin_half_atom():
    result = _parsed()
    qp = result['quadrupolar_parameters']['1']
    # Q == 0 -> summary prints Vzz/eta only, no Cq/nu_Q
    assert 'Cq' not in qp
    assert 'nu_Q' not in qp
    assert abs(qp['Vzz'] - (-0.20)) < 1e-4
    assert abs(qp['eta'] - 0.0) < 1e-5


def test_nuq_not_mistaken_for_q():
    # Regression: the 'Q=' inside 'nu_Q=' must not overwrite the standalone Q.
    result = _parsed()
    qp = result['quadrupolar_parameters']['2']
    assert qp['Q'] != qp['nu_Q']


def test_missing_block_returns_unconverged():
    result = parse_efg_output('some unrelated output\nwith no EFG block\n')
    assert result['converged'] is False
    assert result['natoms'] == 0
    assert result['warnings']
