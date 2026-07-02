"""
Recompute quadrupolar NMR parameters from a stored EFG tensor.

``qe-efg.x`` needs Q and I only for the final Cq/nu_Q printout -- the EFG tensor
itself is a pure ground-state property. Since the workchain stores the full
symmetrized tensor (Ha/bohr^2), everything downstream (principal values, eta,
Cq, nu_Q, principal axes) can be re-derived for *any* choice of nuclear
quadrupole moment Q and spin I, e.g. to switch isotopes at plot time without
re-running the calculation.

Pure numpy, no AiiDA -- unit-testable.
"""

import numpy as np

# Cq[MHz] = CQ_MHZ_PER_Q_VZZ * Q[1e-30 m^2] * Vzz[Ha/bohr^2]
# Same expression and constants as QE-CONVERSE src/efg.f90:
#   Cq = Vzz * Q * rytoev * 2 * angstrom_au**2 * electronvolt_si * 1e18 / 6.62620
# so recomputed values match the Fortran-printed ones to printed precision.
_RYTOEV = 13.605692           # Ry in eV (QE constants)
_ANGSTROM_AU = 1.8897261      # 1 Angstrom in bohr
_ELECTRONVOLT_SI = 1.602176487e-19
CQ_MHZ_PER_Q_VZZ = _RYTOEV * 2.0 * _ANGSTROM_AU**2 * _ELECTRONVOLT_SI * 1e18 / 6.62620


def principal_values(tensor):
    """Diagonalize a (symmetric) EFG tensor.

    Returns ``(v, axes)`` with eigenvalues ``v = [Vxx, Vyy, Vzz]`` ordered by
    increasing magnitude (``|Vzz| >= |Vyy| >= |Vxx|``, the NMR convention) and
    ``axes`` the corresponding eigenvectors as columns (``axes[:, k]`` belongs
    to ``v[k]``).
    """
    t = np.asarray(tensor, dtype=float)
    t = 0.5 * (t + t.T)  # enforce symmetry against parsing round-off
    eigvals, eigvecs = np.linalg.eigh(t)
    order = np.argsort(np.abs(eigvals))
    return eigvals[order], eigvecs[:, order]


def quadrupolar_parameters_from_tensor(tensor, quadrupole_moment=0.0, spin=0.0):
    """Derive all quadrupolar NMR parameters from an EFG tensor.

    Args:
        tensor: 3x3 symmetrized EFG tensor in Ha/bohr^2 (as stored by the
            EFG workchain).
        quadrupole_moment: nuclear quadrupole moment Q in 1e-30 m^2 (= 10 mbarn).
        spin: nuclear spin I.

    Returns a dict with ``Vxx``, ``Vyy``, ``Vzz`` (Ha/bohr^2), ``eta``,
    ``eigenvectors`` (``{'Vxx'|'Vyy'|'Vzz': [x, y, z]}``, same format as the
    parser output), ``Cq`` (MHz, None when Q == 0) and ``nu_Q`` (MHz, None
    unless Q != 0 and I >= 1).
    """
    v, axes = principal_values(tensor)
    vxx, vyy, vzz = (float(x) for x in v)
    eta = (vxx - vyy) / vzz if abs(vzz) > 1e-12 else 0.0

    result = {
        'Vxx': vxx,
        'Vyy': vyy,
        'Vzz': vzz,
        'eta': float(eta),
        'eigenvectors': {
            'Vxx': axes[:, 0].tolist(),
            'Vyy': axes[:, 1].tolist(),
            'Vzz': axes[:, 2].tolist(),
        },
        'Cq': None,
        'nu_Q': None,
    }

    quadrupole_moment = float(quadrupole_moment)
    spin = float(spin)
    if abs(quadrupole_moment) > 1e-12:
        cq = CQ_MHZ_PER_Q_VZZ * quadrupole_moment * vzz
        result['Cq'] = float(cq)
        denom = 2.0 * spin * (2.0 * spin - 1.0)
        if denom > 1e-12:
            result['nu_Q'] = float(3.0 * cq / denom)

    return result
