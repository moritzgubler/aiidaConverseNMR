# app_simulator/ — standalone AiiDAlab app (quadrupolar spectrum simulator)

A plain AiiDAlab app (NOT an aiidalab-qe plugin): every input is user-entered
(isotope/Q/I/γ, B, Vzz, η; lattice vectors + EFG eigenvectors + field
direction for single-crystal work). Launched via the repo-root app files
(`setup.cfg [aiidalab]` + `start.md` → `quadrupolar_simulator.ipynb`;
`post_install` pip-installs the package — the notebook assumes it succeeded).

## Hard constraint

**No `aiida`, `aiidalab_qe` or `aiidalab_widgets_base` imports anywhere in
this subpackage** (nor in `app_common/spectrum_plot.py`, which it shares with
the EFG panel). Dependencies: numpy, scipy, ipywidgets, plotly, anywidget —
all declared in `setup.py`; missing ones crash loudly with the plain
ModuleNotFoundError (deliberate: no availability fallbacks). Note plotly is
imported inside the plot helpers (view.py style), so the crash surfaces at
first plot, not at package import.

## Layout

- `core.py` — pure functions, no widgets: `derived_parameters` (Cq/ν_Q via
  `efg_analysis.cq_nuq_from_vzz` — the single home of that arithmetic;
  ν_L = |γ·B|), `validate_eigenvectors` /`orthonormalize`
  (rows = Vxx/Vyy/Vzz axes; SVD nearest-orthonormal), `axes_dict`, and
  `simulate` — the single dispatch into
  `postprocessing/quadrupolar_spectrum.py` (powder / single / overlay).
  Raises `ValueError` with user-displayable messages (I < 1, ν_Q = 0,
  zero direction).
- `widget.py` — `QuadrupolarSimulatorWidget(ipw.VBox)`. Renders through the
  SAME shared helpers as the EFG panel (`app_common/spectrum_plot.py`:
  `add_powder_traces`, `add_envelope_trace`, `add_stick_traces`,
  `stick_block`, `direction_meta`, `spectrum_layout`) so the two plots and
  their CSV schemas cannot drift; isotope matching via
  `data/nuclear.py::matching_isotope`. Same CSV export
  (`spectrum_export.spectrum_csv`, WYSIWYG payload cached per recompute,
  None disables the button; `second_order` in the header records what was
  actually applied — the backend drops the term when ν_L = 0, and the info
  line says so), same conventions — kHz only at the GUI boundary
  (`MHZ_TO_KHZ`), `go.FigureWidget` set into `_plot.children`
  (never `display()`), `self._updating` guard around programmatic widget
  writes. Crystal-frame inputs (cell / eigenvectors / direction) are shown
  in single-crystal mode or when the powder peak-overlay is on.

## Testing

- `tests/test_simulator_core.py` (skips without ipywidgets+plotly — importing
  the package pulls the widget) and `tests/test_simulator_widget.py` (skips
  without ipywidgets+plotly+anywidget). All present in the AiiDAlab/docker
  images, not necessarily in a bare dev env.
- If the panel and the simulator ever disagree for the same parameters,
  one of them drifted from the shared backend — compare against
  `app_efg/results/view.py::_recompute_spectrum` with debug overrides.
