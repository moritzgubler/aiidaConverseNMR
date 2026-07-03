# app_efg/ — EFG aiidalab-qe GUI plugin

Registered as `aiidalab_qe.properties: qeefg` via `__init__.py::property`
(outline / configuration / resources / result / workchain dict). The NMR plugin
(`../app/`) mirrors this layout and shares the same pitfalls; the common
atom-selection model+panel base is `../app_common/atom_selection.py`
(both config panels subclass it). Root CLAUDE.md lists the general aiidalab-qe
API pitfalls (traits vs properties, FigureWidget, protocol aliases).

## configuration/

- Model extends the shared `AtomSelectionConfigModel` (for structure tracking /
  `atom_info` and `pseudo_family`): adds `nuclear_data` (per-element
  `{"Q": .., "I": ..}` overrides). **No atom selection is exposed or
  serialized** — qe-efg.x computes all atoms in one run, and the workchain
  treats a missing `target_atoms` as "all atoms". `get_model_state`/
  `set_model_state` must include every trait the builder needs — the framework
  serializes only that.
- View = GIPAW pseudo section (info note that the Advanced-step pseudo family
  is IGNORED, per-element preview, MISSING warning) + editable per-element Q/I
  table seeded from `data/nuclear.py` defaults. The shared atom-selection
  table is deliberately not rendered.

## workchain.py

`get_builder(codes, structure, parameters)` maps GUI state to
`EfgWorkChain.get_builder_from_protocol`. Parameters arrive under the entry
point name: `parameters["qeefg"]` (nuclear_data, pseudo_family; a legacy
target_atoms is still honored, absence means all atoms);
protocol under `parameters["workchain"]["protocol"]` in **GUI names**
(`balanced`/`stringent` — aliased in `workflows/common.py`). Codes arrive as
`codes["pw_efg"]["code"]` / `codes["qeefg"]["code"]` (keys = the names given in
`codes/mvc.py::add_models`).

## results/ — the interactive panel

Everything shown is **recomputed live from the stored EFG tensor** (which is
Q/I-independent) via `postprocessing/efg_analysis.py`; the parser's Cq/ν_Q are
only a fallback for legacy runs without stored tensors. Data flow:

- `_qi_by_atom` : label → (Q, I). Seeded in `_init_qi_by_atom()` from the
  submission-time values in `quadrupolar_parameters`, else element defaults
  (`data/nuclear.py::default_q_i`). The single source of truth for Q/I.
- `_current_qp(label)`: tensor + `_qi_by_atom` → Vxx/Vyy/Vzz, η, Cq, ν_Q,
  eigenvectors (Cartesian) and `eigenvectors_lattice` (v·cell⁻¹, scaled so the
  largest |component| is 1 — directly usable in the direction inputs).
- Editing the spectrum section's Q/I widgets (`_on_qi_change`) updates
  `_qi_by_atom`, then refreshes: summary table (`_refresh_summary_table`, a
  persistent `ipw.HTML` whose `.value` is rewritten), the tensor-details block,
  and the spectrum. The `_spec_updating` flag guards against observer feedback
  loops while `_spec_on_atom_change` seeds widget values — keep it around any
  programmatic `.value =` writes.
- JSON download contains both `quadrupolar_parameters_as_computed` (parser) and
  `…_recomputed` (current Q/I).

Spectrum section specifics:
- Two modes (ToggleButtons): powder (grid/Lebedev averaging, optional
  per-transition decomposition à la thesis Fig 2.3) and single crystal
  (direction in lattice units → θ,φ; labeled sticks per transition,
  `_half_int_str` renders m as "−1/2↔1/2").
- **Axis and broadening are in kHz in the GUI only**; the physics backend is
  MHz — convert with `_MHZ_TO_KHZ` at the boundary, nowhere else.
- ν_L = |γ|·B: γ (MHz/T) auto-seeded per element from
  `data/nuclear.py::GYROMAGNETIC_RATIOS`, editable. B in Tesla.
- Atoms with I < 1 get a hint instead of a plot (no quadrupole interaction);
  every atom with a stored tensor is selectable (isotope play allowed).
- Plot embedding: build `go.Figure`, then `self._spec_plot.children =
  [go.FigureWidget(fig)]`. `display()` into an Output renders nothing here.

`results/model.py`: `_this_process_label = "EfgWorkChain"`; outputs fetched via
`_get_child_outputs()`; `_fmt` is the shared number formatter (None → "-").
