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


def _quadrupolar_shift(m, nu_Q, eta, spin_I, nu_L, theta, phi, second_order=True):
    """First- and second-order quadrupolar shifts for transition |m-1> -> |m>.

    Implements eqs 2.28 (``nu1``) and 2.29 (``nu2``); ``theta``/``phi`` (the
    field direction in the EFG principal-axis frame) may be scalars or numpy
    arrays. ``second_order=False`` zeroes the 2.29 term. Returns ``(nu1, nu2)``
    in MHz.
    """
    sin2 = np.sin(theta) ** 2
    cos2 = np.cos(theta) ** 2
    cos2phi = np.cos(2.0 * phi)
    nu1 = 0.25 * nu_Q * (1.0 - 2.0 * m) * (3.0 * cos2 - 1.0 + eta * sin2 * cos2phi)
    if second_order and nu_L != 0.0:
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


def single_crystal_lines(nu_Q, eta, spin_I, nu_L, theta, phi, second_order=True):
    """Transition line positions for a single crystal orientation (theta, phi).

    Returns a list of ``(frequency_MHz, intensity, m)`` tuples, one per
    transition |m-1> -> |m>, using eqs 2.28+2.29+2.32 for the frequency and
    eq 2.33 for the intensity. ``theta``/``phi`` are the polar/azimuthal angles
    of the field in the EFG principal-axis frame (radians). Set
    ``second_order=False`` to keep only the first-order shift (eq 2.28).
    """
    spin_I = float(spin_I)
    if spin_I < 1.0:
        raise ValueError('Quadrupolar spectrum requires I >= 1')
    lines = []
    for m in _transition_m_values(spin_I):
        nu1, nu2 = _quadrupolar_shift(m, nu_Q, eta, spin_I, nu_L, theta, phi, second_order)
        lines.append((float(nu_L + nu1 + nu2), float(transition_weight(m, spin_I)), float(m)))
    return lines


def broaden_lines(lines, broadening, n_points=2000, window=None):
    """Convert discrete ``(freq, weight, m)`` lines into a Gaussian-broadened curve.

    Returns ``(frequencies, intensity)`` (intensity normalised to unit max), the
    sum of one Gaussian per line with FWHM ``broadening`` (MHz) and area ~ weight.
    """
    if not lines:
        return np.array([]), np.array([])
    freqs = np.array([ln[0] for ln in lines], dtype=float)
    weights = np.array([ln[1] for ln in lines], dtype=float)
    if window is None:
        lo, hi = float(freqs.min()), float(freqs.max())
        span = hi - lo
        pad = max(5.0 * (broadening or 0.0), 0.1 * span if span > 0 else 1.0)
        lo, hi = lo - pad, hi + pad
    else:
        lo, hi = window
    grid = np.linspace(lo, hi, n_points)
    fwhm = broadening or (hi - lo) / 200.0
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    intensity = np.zeros_like(grid)
    for freq, weight in zip(freqs, weights):
        intensity += weight * np.exp(-0.5 * ((grid - freq) / sigma) ** 2)
    peak = intensity.max()
    if peak > 0:
        intensity /= peak
    return grid, intensity


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


def orientation_sampling(method='grid', n_theta=200, n_phi=200, lebedev_order=53):
    """Return ``(theta, phi, weight)`` samples of field orientations on the sphere.

    Two schemes:

    * ``'grid'`` (default): a regular product grid uniform in ``cos(theta)`` and
      ``phi`` -- every point carries equal solid angle (weight 1).
    * ``'lebedev'``: Lebedev quadrature nodes (``scipy.integrate.lebedev_rule``)
      with their proper solid-angle weights; far fewer points for the same
      angular accuracy and no preferred axis.

    Angles are in the EFG principal-axis frame (the powder average is over all
    orientations of the field relative to that frame, so no cell is needed).
    """
    if method == 'lebedev':
        from scipy.integrate import lebedev_rule
        pts, weights = lebedev_rule(int(lebedev_order))
        x, y, z = pts
        theta = np.arccos(np.clip(z, -1.0, 1.0))
        phi = np.arctan2(y, x)
        return theta, phi, weights
    # equal-area regular grid
    cos_theta = np.linspace(-1.0, 1.0, n_theta)
    theta1 = np.arccos(np.clip(cos_theta, -1.0, 1.0))
    phi1 = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    theta_g, phi_g = np.meshgrid(theta1, phi1, indexing='ij')
    theta = theta_g.ravel()
    phi = phi_g.ravel()
    return theta, phi, np.ones(theta.size)


def _gaussian_broaden(intensity, lo, hi, n_bins, broadening):
    """Convolve a binned histogram with a Gaussian of FWHM ``broadening`` (MHz)."""
    if not broadening:
        return intensity.astype(float)
    bin_width = (hi - lo) / n_bins
    sigma = broadening / (2.0 * np.sqrt(2.0 * np.log(2.0)))  # FWHM -> sigma
    sigma_bins = max(sigma / bin_width, 1e-6)
    half = int(np.ceil(4.0 * sigma_bins))
    x = np.arange(-half, half + 1)
    kernel = np.exp(-0.5 * (x / sigma_bins) ** 2)
    kernel /= kernel.sum()
    return np.convolve(intensity.astype(float), kernel, mode='same')


def powder_spectrum_by_transition(nu_Q, eta, spin_I, nu_L,
                                  n_theta=200, n_phi=200, n_bins=1000,
                                  freq_window=None, broadening=None,
                                  method='grid', lebedev_order=53, second_order=True):
    """Powder spectrum decomposed per transition (as in the thesis Fig. 2.3).

    Same physics/averaging as :func:`powder_spectrum`, but each transition
    |m-1> -> |m> is histogrammed separately on a *common* frequency grid so the
    curves overlay. All curves share one normalisation (the total's maximum), so
    the per-transition lineshapes add up to the total.

    Returns ``(frequencies, per_transition, total)`` where ``per_transition`` is
    a list of ``(m, intensity)`` ordered by ``m`` and ``total`` is their sum.
    """
    spin_I = float(spin_I)
    if spin_I < 1.0:
        raise ValueError('Quadrupolar spectrum requires I >= 1')

    theta_f, phi_f, ori_w = orientation_sampling(method, n_theta, n_phi, lebedev_order)

    per_freqs = []  # (m, nu_array, weight_array)
    for m in _transition_m_values(spin_I):
        nu1, nu2 = _quadrupolar_shift(m, nu_Q, eta, spin_I, nu_L, theta_f, phi_f, second_order)
        nu = nu_L + nu1 + nu2  # (2.32)
        weight = ori_w * transition_weight(m, spin_I)  # solid angle x (2.33)
        per_freqs.append((m, nu, weight))

    all_nu = np.concatenate([nu for _, nu, _ in per_freqs])
    if freq_window is None:
        lo, hi = float(all_nu.min()), float(all_nu.max())
        pad = 0.05 * (hi - lo) if hi > lo else 1.0
        lo, hi = lo - pad, hi + pad
    else:
        lo, hi = freq_window

    edges = np.linspace(lo, hi, n_bins + 1)
    centres = 0.5 * (edges[:-1] + edges[1:])

    per_transition = []
    total = np.zeros(n_bins)
    for m, nu, weight in per_freqs:
        hist, _ = np.histogram(nu, bins=edges, weights=weight)
        hist = _gaussian_broaden(hist, lo, hi, n_bins, broadening)
        per_transition.append((m, hist))
        total = total + hist

    peak = total.max()
    if peak > 0:
        total = total / peak
        per_transition = [(m, h / peak) for m, h in per_transition]

    return centres, per_transition, total


def powder_spectrum(nu_Q, eta, spin_I, nu_L,
                    n_theta=200, n_phi=200, n_bins=1000,
                    freq_window=None, broadening=None,
                    method='grid', lebedev_order=53, second_order=True):
    """Simulate a (total) powder quadrupolar NMR spectrum.

    Thin wrapper over :func:`powder_spectrum_by_transition` returning only the
    total. See that function for the argument meanings.

    Returns:
        ``(frequencies, intensities)`` numpy arrays; ``intensities`` is the
        total binned, solid-angle and transition-probability weighted line
        density (normalised to unit maximum).
    """
    centres, _per, total = powder_spectrum_by_transition(
        nu_Q, eta, spin_I, nu_L, n_theta=n_theta, n_phi=n_phi, n_bins=n_bins,
        freq_window=freq_window, broadening=broadening, method=method,
        lebedev_order=lebedev_order, second_order=second_order)
    return centres, total


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
