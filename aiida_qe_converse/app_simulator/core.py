"""Pure computation layer of the standalone quadrupolar NMR simulator app.

Bridges user-entered values (Vzz, eta, Q, I, gamma, B, lattice/eigenvector
matrices) to the physics backend in ``postprocessing/quadrupolar_spectrum.py``.
No widgets, no AiiDA -- unit-testable headless. All frequencies in MHz
(the GUI converts to kHz only at the display boundary).
"""

import numpy as np

from ..postprocessing.efg_analysis import cq_nuq_from_vzz
from ..postprocessing.quadrupolar_spectrum import (
    broaden_lines,
    lattice_direction_to_angles,
    powder_spectrum_by_transition,
    single_crystal_lines,
)


def derived_parameters(vzz, q_moment, spin_I, gamma, field_T):
    """Cq, nu_Q and nu_L (MHz) from user-entered values.

    Cq/nu_Q via ``efg_analysis.cq_nuq_from_vzz`` (Cq None when Q == 0,
    nu_Q None unless also I >= 1); nu_L = |gamma . B| -- the field magnitude
    sets the Larmor frequency, so the sign of either entry is irrelevant.
    """
    cq, nu_q = cq_nuq_from_vzz(vzz, q_moment, spin_I)
    return {'Cq': cq, 'nu_Q': nu_q,
            'nu_L': abs(float(gamma) * float(field_T))}


def validate_eigenvectors(matrix, tol=1e-6):
    """Check that the rows of ``matrix`` are orthonormal (after normalization).

    Rows are the Vxx/Vyy/Vzz principal axes. Each row is unit-normalized
    first (the backend normalizes too, so pure scaling is harmless); the
    check is on mutual orthogonality: ``max |M Mt - 1|``. Returns
    ``(ok, max_deviation)``.
    """
    m = np.asarray(matrix, dtype=float)
    norms = np.linalg.norm(m, axis=1)
    if np.any(norms < 1e-12):
        return False, float('inf')
    m = m / norms[:, None]
    dev = float(np.max(np.abs(m @ m.T - np.eye(3))))
    return dev <= tol, dev


def orthonormalize(matrix):
    """Nearest orthonormal matrix (Frobenius) via SVD: ``U @ Vt``."""
    u, _s, vt = np.linalg.svd(np.asarray(matrix, dtype=float))
    return u @ vt


def axes_dict(matrix):
    """Rows of a 3x3 matrix as the ``{'Vxx','Vyy','Vzz': [x,y,z]}`` dict
    expected by ``lattice_direction_to_angles``."""
    m = np.asarray(matrix, dtype=float)
    return {'Vxx': m[0].tolist(), 'Vyy': m[1].tolist(), 'Vzz': m[2].tolist()}


def simulate(nu_Q, eta, spin_I, nu_L, mode='powder', n_grid=1000,
             broadening=None, second_order=True, decompose=False,
             overlay_peaks=False, cell=None, eigenvectors=None,
             direction=None):
    """Compute the spectrum for one user-entered parameter set.

    Args:
        nu_Q, eta, spin_I, nu_L: quadrupolar frequency (MHz), asymmetry,
            spin, Larmor frequency (MHz).
        mode: ``'powder'`` or ``'single'``.
        n_grid: powder orientation grid size (n_theta = n_phi = n_grid).
        broadening: Gaussian FWHM in MHz, or None/0 for none.
        second_order: include the second-order shift (thesis eq 2.29).
        decompose: powder only -- keep the per-transition curves.
        overlay_peaks: powder only -- also compute the single-crystal
            sticks for ``direction`` (needs cell + eigenvectors too).
        cell: 3x3, rows = Cartesian lattice vectors.
        eigenvectors: 3x3, rows = Vxx/Vyy/Vzz principal axes (Cartesian).
        direction: field direction as 3 lattice-vector coefficients.

    Returns a dict with ``freqs``, ``per_transition``, ``total`` (powder),
    ``lines``, ``envelope`` (sticks / broadened envelope), ``theta``,
    ``phi`` (radians); keys not produced by the chosen mode are None.
    Raises ValueError for unusable inputs (I < 1, nu_Q == 0, zero
    direction) with a message suitable for direct display.
    """
    spin_I = float(spin_I)
    if spin_I < 1.0:
        raise ValueError('A quadrupolar spectrum needs I >= 1 '
                         '(spin-1/2 isotopes have no quadrupole interaction)')
    if abs(float(nu_Q)) < 1e-12:
        raise ValueError('nu_Q is zero -- Vzz and Q must both be nonzero')
    broadening = float(broadening) if broadening else None

    result = {'freqs': None, 'per_transition': None, 'total': None,
              'lines': None, 'envelope': None, 'theta': None, 'phi': None}

    def _angles():
        theta, phi = lattice_direction_to_angles(
            direction, cell, axes_dict(eigenvectors))
        result['theta'], result['phi'] = theta, phi
        return theta, phi

    if mode == 'powder':
        n = max(int(n_grid), 8)
        freqs, per, total = powder_spectrum_by_transition(
            nu_Q, eta, spin_I, nu_L, n_theta=n, n_phi=n,
            broadening=broadening, second_order=second_order)
        result['freqs'], result['total'] = freqs, total
        if decompose:
            result['per_transition'] = per
        if overlay_peaks:
            theta, phi = _angles()
            result['lines'] = single_crystal_lines(
                nu_Q, eta, spin_I, nu_L, theta, phi,
                second_order=second_order)
    else:
        theta, phi = _angles()
        lines = single_crystal_lines(nu_Q, eta, spin_I, nu_L, theta, phi,
                                     second_order=second_order)
        result['lines'] = lines
        if broadening:
            result['envelope'] = broaden_lines(lines, broadening)
    return result
