"""
Powder quadrupolar NMR spectrum simulator.

Implements the first- and second-order quadrupolar perturbation of the Zeeman
levels for a polycrystalline (powder) sample, following the thesis equations
2.28-2.33:

* 2.28  first-order shift   nu1_{m-1,m} = (1/4) nu_Q (1-2m) [3cos^2 th - 1 + eta sin^2 th cos 2ph]
* 2.29  second-order shift  nu2_{m-1,m} = -(nu_Q^2/nu_L) { -A[m(m-1) - I(I+1)/6 + 3/8]
                                                          + B[m(m-1)/2 - I(I+1)/6 + 1/4] }
* 2.30  A(eta,ph,th),  2.31  B(eta,ph,th)
* 2.32  total frequency     nu = nu_L + nu1 + nu2
* 2.33  transition weight   p(I,m) = I(I+1) - m(m-1)

The powder average is taken over an (almost) uniform set of crystal orientations
(uniform in cos(theta) and in phi, i.e. uniform on the unit sphere), and the
weighted transition frequencies are binned into a histogram.  An optional
Gaussian broadening smooths the singularities.

The core :func:`powder_spectrum` is pure numpy (no AiiDA) so it is unit-testable;
:func:`simulate_powder_spectrum` is the AiiDA ``calcfunction`` wrapper that
returns an ``ArrayData`` with ``frequency_MHz`` and ``intensity`` arrays.
"""

import numpy as np


def _transition_m_values(spin_I):
    """Return the m values labelling the transitions |m-1> -> |m>.

    For spin I the Zeeman states are m = -I .. I; transitions connect
    consecutive states, so m runs from -I+1 to I (2I transitions).
    """
    n_trans = int(round(2 * spin_I))
    return np.array([-spin_I + 1 + k for k in range(n_trans)], dtype=float)


def _AB(eta, theta, phi):
    """Evaluate the second-order angular functions A (2.30) and B (2.31)."""
    c2 = np.cos(theta) ** 2
    c4 = c2 ** 2
    cos2p = np.cos(2.0 * phi)
    cos2p2 = cos2p ** 2

    A = (
        c4 * (-(1.0 / 3.0) * eta**2 * cos2p2 + 2.0 * eta * cos2p - 3.0)
        + c2 * ((2.0 / 3.0) * eta**2 * cos2p2 - 2.0 * eta * cos2p - (1.0 / 3.0) * eta**2 + 3.0)
        + (1.0 / 3.0) * eta**2 * (1.0 - cos2p2)
    )
    B = (
        c4 * ((1.0 / 24.0) * eta**2 * cos2p2 - (1.0 / 4.0) * eta * cos2p + 3.0 / 8.0)
        + c2 * (-(1.0 / 12.0) * eta**2 * cos2p2 + (1.0 / 6.0) * eta**2 - 3.0 / 4.0)
        + (1.0 / 24.0) * eta**2 * cos2p2 + (1.0 / 4.0) * eta * cos2p + 3.0 / 8.0
    )
    return A, B


def _quadrupolar_shift(m, nu_Q, eta, spin_I, nu_L, theta, phi):
    """First- and second-order quadrupolar shifts for transition |m-1> -> |m>.

    Implements eqs 2.28 (``nu1``) and 2.29 (``nu2``); ``theta``/``phi`` (the
    field direction in the EFG principal-axis frame) may be scalars or numpy
    arrays. Returns ``(nu1, nu2)`` in MHz.
    """
    sin2 = np.sin(theta) ** 2
    cos2 = np.cos(theta) ** 2
    cos2phi = np.cos(2.0 * phi)
    nu1 = 0.25 * nu_Q * (1.0 - 2.0 * m) * (3.0 * cos2 - 1.0 + eta * sin2 * cos2phi)
    if nu_L != 0.0:
        A, B = _AB(eta, theta, phi)
        II1 = spin_I * (spin_I + 1.0)
        mm1 = m * (m - 1.0)
        nu2 = -(nu_Q**2 / nu_L) * (
            -A * (mm1 - II1 / 6.0 + 3.0 / 8.0)
            + B * (0.5 * mm1 - II1 / 6.0 + 1.0 / 4.0)
        )
    else:
        nu2 = 0.0 * nu1
    return nu1, nu2


def transition_weight(m, spin_I):
    """Relative transition probability p(I, m) = I(I+1) - m(m-1) (eq 2.33)."""
    return spin_I * (spin_I + 1.0) - m * (m - 1.0)


def single_crystal_lines(nu_Q, eta, spin_I, nu_L, theta, phi):
    """Transition line positions for a single crystal orientation (theta, phi).

    Returns a list of ``(frequency_MHz, intensity, m)`` tuples, one per
    transition |m-1> -> |m>, using eqs 2.28+2.29+2.32 for the frequency and
    eq 2.33 for the intensity. ``theta``/``phi`` are the polar/azimuthal angles
    of the field in the EFG principal-axis frame (radians).
    """
    spin_I = float(spin_I)
    if spin_I < 1.0:
        raise ValueError('Quadrupolar spectrum requires I >= 1')
    lines = []
    for m in _transition_m_values(spin_I):
        nu1, nu2 = _quadrupolar_shift(m, nu_Q, eta, spin_I, nu_L, theta, phi)
        lines.append((float(nu_L + nu1 + nu2), float(transition_weight(m, spin_I)), float(m)))
    return lines


def lattice_direction_to_angles(direction, cell, axes):
    """Convert a field direction in lattice-vector units to EFG-frame (theta, phi).

    Args:
        direction: 3 coefficients ``(d1, d2, d3)`` so that the (un-normalised)
            field is ``d1*a1 + d2*a2 + d3*a3`` with ``a_i`` the lattice vectors.
        cell: 3x3 array whose *rows* are the Cartesian lattice vectors a1,a2,a3.
        axes: dict with the EFG eigenvectors ``{'Vxx','Vyy','Vzz': [x,y,z]}`` in
            the same Cartesian frame (as parsed from qe-efg output).

    Returns:
        ``(theta, phi)`` in radians: the polar angle from the Vzz axis and the
        azimuth in the (Vxx, Vyy) plane. The direction is normalised automatically.
    """
    d = np.asarray(direction, dtype=float)
    cell = np.asarray(cell, dtype=float)
    b = d @ cell  # Cartesian field vector
    norm = np.linalg.norm(b)
    if norm == 0.0:
        raise ValueError('Field direction is the zero vector')
    b = b / norm

    def _unit(v):
        v = np.asarray(v, dtype=float)
        n = np.linalg.norm(v)
        return v / n if n else v

    ex, ey, ez = _unit(axes['Vxx']), _unit(axes['Vyy']), _unit(axes['Vzz'])
    theta = float(np.arccos(np.clip(np.dot(b, ez), -1.0, 1.0)))
    phi = float(np.arctan2(np.dot(b, ey), np.dot(b, ex)))
    return theta, phi


def powder_spectrum(nu_Q, eta, spin_I, nu_L,
                    n_theta=200, n_phi=200, n_bins=1000,
                    freq_window=None, broadening=None):
    """Simulate a powder quadrupolar NMR spectrum.

    Args:
        nu_Q: quadrupolar frequency (MHz).
        eta: EFG asymmetry parameter (0..1).
        spin_I: nuclear spin I (>= 1).
        nu_L: Larmor frequency (MHz).
        n_theta, n_phi: orientation grid density.
        n_bins: number of frequency bins.
        freq_window: optional (lo, hi) frequency window in MHz; defaults to the
            observed min/max with a small pad.
        broadening: optional Gaussian FWHM (MHz) convolved with the histogram.

    Returns:
        ``(frequencies, intensities)`` numpy arrays.  ``frequencies`` are bin
        centres in MHz; ``intensities`` is the binned, transition-probability
        weighted line density (normalised to unit maximum).
    """
    spin_I = float(spin_I)
    if spin_I < 1.0:
        raise ValueError('Quadrupolar spectrum requires I >= 1')

    # Uniform-on-sphere orientation grid: cos(theta) uniform, phi uniform.
    cos_theta = np.linspace(-1.0, 1.0, n_theta)
    theta = np.arccos(np.clip(cos_theta, -1.0, 1.0))
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    theta_g, phi_g = np.meshgrid(theta, phi, indexing='ij')
    theta_f = theta_g.ravel()
    phi_f = phi_g.ravel()

    all_freqs = []
    all_weights = []
    for m in _transition_m_values(spin_I):
        nu1, nu2 = _quadrupolar_shift(m, nu_Q, eta, spin_I, nu_L, theta_f, phi_f)
        nu = nu_L + nu1 + nu2  # (2.32)
        weight = transition_weight(m, spin_I)  # (2.33)
        all_freqs.append(nu)
        all_weights.append(np.full_like(nu, weight))

    freqs = np.concatenate(all_freqs)
    weights = np.concatenate(all_weights)

    if freq_window is None:
        lo, hi = float(freqs.min()), float(freqs.max())
        pad = 0.05 * (hi - lo) if hi > lo else 1.0
        lo, hi = lo - pad, hi + pad
    else:
        lo, hi = freq_window

    intensity, edges = np.histogram(freqs, bins=n_bins, range=(lo, hi), weights=weights)
    centres = 0.5 * (edges[:-1] + edges[1:])

    if broadening:
        bin_width = (hi - lo) / n_bins
        sigma = broadening / (2.0 * np.sqrt(2.0 * np.log(2.0)))  # FWHM -> sigma
        sigma_bins = max(sigma / bin_width, 1e-6)
        half = int(np.ceil(4.0 * sigma_bins))
        x = np.arange(-half, half + 1)
        kernel = np.exp(-0.5 * (x / sigma_bins) ** 2)
        kernel /= kernel.sum()
        intensity = np.convolve(intensity.astype(float), kernel, mode='same')

    peak = intensity.max()
    if peak > 0:
        intensity = intensity / peak

    return centres, intensity


# AiiDA calcfunction wrapper, defined only when AiiDA is importable so that the
# pure-numpy core above can be imported and unit-tested without a profile.
try:  # pragma: no cover - exercised only in a full AiiDA environment
    from aiida import orm
    from aiida.engine import calcfunction

    @calcfunction
    def simulate_powder_spectrum(nu_Q, eta, spin_I, nu_L, options=None):
        """Provenance-tracked wrapper around :func:`powder_spectrum`.

        Inputs are AiiDA ``Float`` nodes; ``options`` is an optional ``Dict``
        with ``n_theta`` / ``n_phi`` / ``n_bins`` / ``broadening``.  Returns an
        ``ArrayData`` with arrays ``frequency_MHz`` and ``intensity``.
        """
        opts = options.get_dict() if options is not None else {}
        centres, intensity = powder_spectrum(
            float(nu_Q), float(eta), float(spin_I), float(nu_L),
            n_theta=opts.get('n_theta', 200),
            n_phi=opts.get('n_phi', 200),
            n_bins=opts.get('n_bins', 1000),
            broadening=opts.get('broadening'),
        )
        array = orm.ArrayData()
        array.set_array('frequency_MHz', centres)
        array.set_array('intensity', intensity)
        array.base.attributes.set('nu_Q', float(nu_Q))
        array.base.attributes.set('eta', float(eta))
        array.base.attributes.set('spin_I', float(spin_I))
        array.base.attributes.set('nu_L', float(nu_L))
        return array

except ImportError:  # pragma: no cover
    simulate_powder_spectrum = None
