# postprocessing/ — quadrupolar spectrum & EFG analysis

Pure numpy/scipy, **no AiiDA imports** at module level (the one calcfunction is
guarded by try/ImportError) — everything here is unit-testable without a
profile (`tests/test_quadrupolar_spectrum.py`, `tests/test_efg_analysis.py`).

## Units — the #1 source of confusion

- **Everything in this package is in MHz** (frequencies, broadening FWHM) and
  Ha/bohr² (EFG tensor / principal values). Q is in 1e-30 m² (= 10 mbarn).
- The GUIs plot the axis in **kHz** and take broadening in kHz: conversion
  happens only at the GUI boundary via `app_common/spectrum_plot.py::MHZ_TO_KHZ`
  (used by `app_efg/results/view.py` and `app_simulator/widget.py`). Never
  convert here.

## quadrupolar_spectrum.py — thesis eqs 2.28–2.33

"Thesis" everywhere (eqs 2.28–2.33, Fig 2.3) = T. Arh, *Stability of quantum
spin liquids in two dimensions*, doctoral dissertation, Univ. of Ljubljana
(2024), <https://repozitorij.uni-lj.si/IzpisGradiva.php?id=159093&lang=eng>.

Equation → function map:
- eq 2.28 (first-order shift ν⁽¹⁾, ∝ ν_Q(1−2m)[3cos²θ−1+η sin²θ cos2φ]) and
  eq 2.29 (second-order ν⁽²⁾, ∝ ν_Q²/ν_L with angular factors A (2.30), B (2.31))
  → `_quadrupolar_shift(m, …, second_order=)`; `_AB()` holds A and B.
- eq 2.32 (ν = ν_L + ν⁽¹⁾ + ν⁽²⁾) → assembled in the callers.
- eq 2.33 (intensity p(I,m) = I(I+1) − m(m−1)) → `transition_weight`.
  Intensities are **orientation-independent** (high-field, non-selective
  excitation, equal populations) — only frequencies are anisotropic.
- Transitions |m−1⟩→|m⟩ with m = −I+1 … I (2I of them) → `_transition_m_values`.
  Central transition (m=½, half-integer I) has no first-order shift.

Powder averaging (`orientation_sampling`): either an equal-area product grid
(uniform in cosθ and φ — every point equal solid angle, weight 1) or **Lebedev
quadrature** (`scipy.integrate.lebedev_rule`, weights sum to 4π). The powder
spectrum is a *histogram of line positions* weighted by solid angle × p(I,m),
then optionally Gaussian-convolved (`_gaussian_broaden`, FWHM in MHz).

`powder_spectrum_by_transition` is the core (per-transition curves on a
**common** frequency grid with **shared normalization**, so curves sum exactly
to the total — thesis Fig 2.3 decomposition); `powder_spectrum` returns just the
total. `single_crystal_lines` gives discrete (freq, weight, m) for one (θ, φ);
`broaden_lines` turns them into a Gaussian envelope.

`lattice_direction_to_angles(direction, cell, axes)`: field direction given in
lattice-vector coefficients (d·cell rows → Cartesian, normalized), projected
onto the EFG eigenvector frame → (θ, φ). Note: "a,b,c" means the rows of the
stored `structure.cell` — meaningful only if that cell matches the user's
crystallographic convention (no re-reduction upstream).

## spectrum_export.py — CSV serializer for the GUI's plotted-data download

`spectrum_csv(meta, blocks)`: `#`-commented metadata header + data blocks,
each starting with a plain (uncommented) column-names row so spreadsheets
align names over data (two blank lines between blocks, gnuplot `index`
style). Pure string building, no units logic — the GUI passes values
already converted for display (kHz axis etc.). Tested in
`tests/test_spectrum_csv.py`.

## efg_analysis.py — recompute anything from the stored tensor

The EFG tensor is Q/I-independent; Q and I only enter Cq/ν_Q. So:
- `principal_values(tensor)`: symmetrize (guards parse round-off), `eigh`,
  order by |eigenvalue| ascending → `[Vxx, Vyy, Vzz]` with |Vzz|≥|Vyy|≥|Vxx|
  (NMR convention); eigenvectors as columns.
- `cq_nuq_from_vzz(vzz, Q, I)`: the **single home** of the Cq/ν_Q arithmetic —
  Cq = `CQ_MHZ_PER_Q_VZZ` × Q × Vzz (≈ 2.3496 MHz per Q·Vzz — the **same
  constants and expression as QE-CONVERSE `src/efg.f90`**, so recomputed values
  match the Fortran printout); ν_Q = 3Cq/(2I(2I−1)). Cq is None when Q=0;
  ν_Q None unless also I ≥ 1 (spin-½ ⇒ no quadrupole interaction). All GUI
  paths (EFG panel incl. debug overrides, simulator) derive through it.
- `quadrupolar_parameters_from_tensor(tensor, Q, I)`: η = (Vxx−Vyy)/Vzz plus
  the above per-tensor (principal values, eigenvector dict, Cq, ν_Q).

This is what lets the GUI switch isotopes / edit Q,I at plot time without
re-running DFT. Nuclear constants (Q, I, γ per isotope) live in
`../data/nuclear.py` — experimental values, not computed ones.
