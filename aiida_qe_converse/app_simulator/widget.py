"""ipywidgets GUI of the standalone quadrupolar NMR simulator.

Everything is user-entered (no AiiDA, no DFT run): isotope (or custom Q, I,
gamma), field, Vzz and eta, and -- for single-crystal work -- lattice
vectors, EFG eigenvectors and a field direction. The plot mirrors the EFG
results panel (``app_efg/results/view.py``) so the two can be cross-checked.

Frequencies are MHz in the backend; the axis and broadening are kHz here at
the GUI boundary only (``MHZ_TO_KHZ``).
"""

import numpy as np
import ipywidgets as ipw

from ..app_common.spectrum_plot import (
    MHZ_TO_KHZ,
    add_envelope_trace,
    add_powder_traces,
    add_stick_traces,
    direction_meta,
    js_download_text,
    spectrum_layout,
    stick_block,
)
from ..data.nuclear import ISOTOPES, isotope_entry, isotopes_for
from ..postprocessing.spectrum_export import spectrum_csv
from . import core

_HEADER = """
<h3>Quadrupolar NMR spectrum simulator</h3>
<p>Simulate first/second-order quadrupolar NMR spectra from hand-entered
parameters — no calculation needed.</p>
<p><b>Powder</b>: average over all field orientations (eqs 2.28–2.33),
independent of direction, on an equal-area orientation grid. Optionally
overlay the single-crystal peak positions for a chosen field direction.</p>
<p><b>Single crystal</b>: discrete transition lines for a fixed field
direction (in lattice-vector units), projected onto the EFG principal axes
to get (θ, φ). The field strength sets ν<sub>L</sub> = |γ|·B.</p>
<p><b>Pick an isotope</b> to seed I and γ from the built-in table, or edit
them freely (= <i>custom</i>). Enter the quadrupolar coupling as
<b>C<sub>q</sub> or ν<sub>Q</sub></b> — the two fields stay in sync via
ν<sub>Q</sub> = 3C<sub>q</sub>/(2I(2I−1)); when I changes, C<sub>q</sub>
is kept and ν<sub>Q</sub> follows.</p>
<p style='font-size:0.9em;color:#666;'>Equation numbers refer to
<a href='https://repozitorij.uni-lj.si/IzpisGradiva.php?id=159093&amp;lang=eng'
target='_blank'>T. Arh, <i>Stability of quantum spin liquids in two
dimensions</i>, doctoral dissertation, University of Ljubljana (2024)</a>.<br>
Isotope data (spins I and γ): R. K. Harris et al., <i>NMR nomenclature</i>
(IUPAC Recommendations 2001), Pure Appl. Chem. 73, 1795 (2001),
<a href='https://doi.org/10.1351/pac200173111795'
target='_blank'>doi:10.1351/pac200173111795</a>.</p>
"""


def _matrix_grid(defaults, row_labels, width="110px"):
    """A labelled 3x3 grid of FloatTexts; returns (cells, VBox)."""
    cells = []
    rows = []
    for i, label in enumerate(row_labels):
        row = [ipw.FloatText(value=float(defaults[i][j]),
                             layout=ipw.Layout(width=width))
               for j in range(3)]
        cells.append(row)
        rows.append(ipw.HBox(
            [ipw.HTML(f"<span style='display:inline-block;width:44px;'>"
                      f"{label}</span>")] + row))
    return cells, ipw.VBox(rows)


def _matrix_values(cells):
    return np.array([[float(w.value) for w in row] for row in cells])


class QuadrupolarSimulatorWidget(ipw.VBox):
    """Self-contained simulator: all spectrum inputs are user-entered."""

    def __init__(self, **kwargs):
        self._updating = False
        self._export = None

        self._build_nucleus_section()
        self._build_efg_section()
        self._build_mode_section()
        self._build_plot_section()

        self._info = ipw.HTML()
        self._plot = ipw.VBox()

        self._wire_observers()
        self._seed_from_isotope()
        self._update_visibility()  # also triggers the first recompute

        controls = ipw.VBox([
            self._mode,
            ipw.HBox([self._element, self._isotope]),
            ipw.HBox([self._B, self._gamma]),
            ipw.HBox([self._I]),
            ipw.HBox([self._cq, self._nuq]),
            ipw.HBox([self._eta]),
            self._powder_box,
            self._crystal_box,
            ipw.HBox([self._broad, self._second]),
            self._info,
        ])
        super().__init__(children=[
            ipw.HTML(_HEADER),
            controls,
            self._plot,
            self._download,
        ], **kwargs)

    # ---------------------------------------------------------------- build
    def _build_nucleus_section(self):
        style = {"description_width": "120px"}
        self._element = ipw.Dropdown(options=sorted(ISOTOPES), value="Na",
                                     description="Element:", style=style,
                                     layout=ipw.Layout(width="240px"))
        self._isotope = ipw.Dropdown(options=["custom"], value="custom",
                                     description="Isotope:", style=style,
                                     layout=ipw.Layout(width="240px"))
        self._B = ipw.FloatText(value=9.4, description="B field (T):", style=style)
        self._gamma = ipw.FloatText(value=0.0, description="|γ| (MHz/T):", style=style)
        self._I = ipw.FloatText(value=0.0, description="I:", style=style)

    def _build_efg_section(self):
        style = {"description_width": "120px"}
        # linked pair: C_q is the stored quantity, nu_Q a live view through I
        self._cq = ipw.FloatText(value=3.0, step=0.1,
                                 description="C_q (MHz):", style=style)
        self._nuq = ipw.FloatText(value=0.0, step=0.1,
                                  description="ν_Q (MHz):", style=style)
        self._eta = ipw.BoundedFloatText(value=0.0, min=0.0, max=1.0, step=0.05,
                                         description="η (0…1):", style=style)

    def _build_mode_section(self):
        self._mode = ipw.ToggleButtons(
            options=[("Powder (orientation average)", "powder"),
                     ("Single crystal (fixed direction)", "single")],
            value="powder",
        )
        # powder-only controls: equal-area orientation grid
        self._npts = ipw.IntText(value=1000, description="grid n (θ,φ):",
                                 style={"description_width": "120px"},
                                 layout=ipw.Layout(width="220px"))
        self._decompose = ipw.Checkbox(value=False, indent=False,
                                       description="decompose by transition")
        self._overlay = ipw.Checkbox(
            value=False, indent=False,
            description="mark single-crystal peaks for a field direction")
        self._powder_box = ipw.VBox([
            self._npts,
            ipw.HBox([self._decompose, self._overlay]),
        ])

        # crystal frame: lattice vectors, EFG eigenvectors, field direction
        eye = np.eye(3)
        self._cell_cells, cell_grid = _matrix_grid(eye, ("a₁", "a₂", "a₃"))
        self._eig_cells, eig_grid = _matrix_grid(eye, ("Vxx", "Vyy", "Vzz"))
        self._eig_warning = ipw.HTML()
        self._eig_fix = ipw.Button(description="Orthonormalize", icon="wrench",
                                   tooltip="Replace the eigenvector matrix by the "
                                           "nearest orthonormal one (SVD)",
                                   layout=ipw.Layout(width="160px", display="none"))
        self._da = ipw.FloatText(value=0.0, description="a:",
                                 layout=ipw.Layout(width="120px"),
                                 style={"description_width": "20px"})
        self._db = ipw.FloatText(value=0.0, description="b:",
                                 layout=ipw.Layout(width="120px"),
                                 style={"description_width": "20px"})
        self._dc = ipw.FloatText(value=1.0, description="c:",
                                 layout=ipw.Layout(width="120px"),
                                 style={"description_width": "20px"})
        self._crystal_box = ipw.VBox([
            ipw.HTML("<b>Lattice vectors</b> (rows, Cartesian; default = cubic):"),
            cell_grid,
            ipw.HTML("<b>EFG eigenvectors</b> (rows = V<sub>xx</sub>, V<sub>yy</sub>, "
                     "V<sub>zz</sub> principal axes in the same Cartesian frame; "
                     "rows are normalised automatically):"),
            eig_grid,
            ipw.HBox([self._eig_fix, self._eig_warning]),
            ipw.HTML("<b>Field direction</b> (lattice-vector units, "
                     "normalised automatically):"),
            ipw.HBox([self._da, self._db, self._dc]),
        ])

    def _build_plot_section(self):
        self._broad = ipw.BoundedFloatText(
            value=5.0, min=0.0, max=1e6, description="broadening (kHz):",
            style={"description_width": "140px"})
        self._second = ipw.Checkbox(value=True, indent=False,
                                    description="include 2nd-order term (eq 2.29)")
        self._download = ipw.Button(
            description="Download plotted data (CSV)", icon="download",
            tooltip="Download the curves currently shown in the plot as CSV "
                    "(with a #-commented parameter header)",
            layout=ipw.Layout(width="260px"), disabled=True)
        self._download.on_click(self._download_csv)

    def _wire_observers(self):
        self._element.observe(lambda c: self._on_element_change(), names="value")
        self._isotope.observe(lambda c: self._on_isotope_change(), names="value")
        for w in (self._I, self._gamma):
            w.observe(lambda c: self._on_ig_change(), names="value")
        self._cq.observe(lambda c: self._on_cq_change(), names="value")
        self._nuq.observe(lambda c: self._on_nuq_change(), names="value")
        self._mode.observe(lambda c: self._update_visibility(), names="value")
        self._overlay.observe(lambda c: self._update_visibility(), names="value")
        for row in self._eig_cells:
            for w in row:
                w.observe(lambda c: self._on_eig_change(), names="value")
        self._eig_fix.on_click(self._on_orthonormalize)
        recompute_widgets = [self._B, self._eta,
                             self._npts, self._decompose, self._second,
                             self._broad, self._da, self._db, self._dc]
        recompute_widgets += [w for row in self._cell_cells for w in row]
        for w in recompute_widgets:
            w.observe(lambda c: self._recompute(), names="value")

    # ------------------------------------------------------------- nucleus
    def _seed_from_isotope(self):
        """Populate the isotope options for the element and seed I and gamma."""
        element = self._element.value
        options = [e[0] for e in isotopes_for(element)] + ["custom"]
        self._updating = True
        try:
            self._isotope.options = options
            self._isotope.value = options[0]
            entry = isotope_entry(element, options[0])
            if entry is not None:
                _label, spin, _q, gamma = entry
                self._I.value = float(spin)
                self._gamma.value = float(gamma) if gamma is not None else 0.0
            self._sync_nuq_from_cq()
        finally:
            self._updating = False

    def _on_element_change(self):
        if self._updating:
            return
        self._seed_from_isotope()
        self._recompute()

    def _on_isotope_change(self):
        """User picked an isotope: seed I and gamma from the built-in table."""
        if self._updating:
            return
        entry = isotope_entry(self._element.value, self._isotope.value)
        if entry is None:  # "custom": keep whatever is in the I/gamma fields
            return
        _label, spin, _q, gamma = entry
        self._updating = True
        try:
            self._I.value = float(spin)
            # gamma is None only for spin-1/2 defaults: zero it rather than
            # keeping the previous isotope's value under the new label
            self._gamma.value = float(gamma) if gamma is not None else 0.0
            self._sync_nuq_from_cq()  # C_q kept as typed, nu_Q follows I
        finally:
            self._updating = False
        self._recompute()

    @staticmethod
    def _matching_isotope(element, spin, gamma):
        """Isotope label whose (I, gamma) match the given values, or None."""
        for label, iso_spin, _q, iso_gamma in isotopes_for(element or ""):
            iso_gamma = iso_gamma if iso_gamma is not None else 0.0
            if abs(spin - iso_spin) < 1e-6 and abs(gamma - iso_gamma) < 1e-4:
                return label
        return None

    def _on_ig_change(self):
        """Manual I/gamma edit: flip the isotope dropdown; nu_Q follows I."""
        if self._updating:
            return
        match = self._matching_isotope(
            self._element.value, float(self._I.value), float(self._gamma.value))
        self._updating = True
        try:
            if self._isotope.value != (match or "custom"):
                self._isotope.value = match or "custom"
            self._sync_nuq_from_cq()
        finally:
            self._updating = False
        self._recompute()

    # ----------------------------------------------------- C_q <-> nu_Q pair
    def _sync_nuq_from_cq(self):
        """Refresh the nu_Q field from C_q and I (caller holds ``_updating``).

        For I < 1 the conversion is singular (and there is no quadrupolar
        spectrum): the field is disabled and keeps its last value; C_q is
        never touched, so nothing is lost when I becomes valid again.
        """
        nuq = core.nu_q_from_cq(self._cq.value, self._I.value)
        self._nuq.disabled = nuq is None
        if nuq is not None:
            self._nuq.value = nuq

    def _on_cq_change(self):
        if self._updating:
            return
        self._updating = True
        try:
            self._sync_nuq_from_cq()
        finally:
            self._updating = False
        self._recompute()

    def _on_nuq_change(self):
        if self._updating:
            return
        cq = core.cq_from_nu_q(self._nuq.value, self._I.value)
        if cq is not None:
            self._updating = True
            try:
                self._cq.value = cq
            finally:
                self._updating = False
        self._recompute()

    # ------------------------------------------------------- crystal frame
    def _on_eig_change(self):
        if self._updating:
            return
        self._refresh_eig_warning()
        self._recompute()

    def _refresh_eig_warning(self):
        ok, dev = core.validate_eigenvectors(_matrix_values(self._eig_cells))
        if ok:
            self._eig_warning.value = ""
            self._eig_fix.layout.display = "none"
        else:
            self._eig_warning.value = (
                "<span style='color:#d62728;'>eigenvector rows are not "
                f"orthonormal (max deviation {dev:.3g}) — the spectrum uses "
                "them as given (normalised)</span>")
            self._eig_fix.layout.display = ""

    def _on_orthonormalize(self, _=None):
        fixed = core.orthonormalize(_matrix_values(self._eig_cells))
        self._updating = True
        try:
            for i, row in enumerate(self._eig_cells):
                for j, w in enumerate(row):
                    w.value = round(float(fixed[i, j]), 10)
        finally:
            self._updating = False
        self._refresh_eig_warning()
        self._recompute()

    # -------------------------------------------------------------- update
    def _update_visibility(self):
        powder = self._mode.value == "powder"
        self._powder_box.layout.display = "" if powder else "none"
        # the crystal-frame inputs also apply to the powder peak overlay
        show_crystal = (not powder) or self._overlay.value
        self._crystal_box.layout.display = "" if show_crystal else "none"
        self._recompute()

    def _set_export(self, payload):
        """Cache the CSV payload for the download button; None disables it."""
        self._export = payload
        self._download.disabled = payload is None

    def _show_hint(self, text, info=""):
        self._plot.children = [ipw.HTML(f"<i>{text}</i>")]
        self._info.value = info
        self._set_export(None)

    def _recompute(self):
        import plotly.graph_objects as go
        from datetime import datetime

        if self._updating:
            return
        cq = float(self._cq.value)
        eta = float(self._eta.value)
        spin_I = float(self._I.value)
        gamma = abs(float(self._gamma.value))
        field = float(self._B.value)
        derived = core.derived_parameters(cq, spin_I, gamma, field)
        nu_Q, nu_L = derived["nu_Q"], derived["nu_L"]

        # everything else on this line is already visible in an input field
        base_info = f"ν<sub>L</sub> = |γ|·B = {nu_L:.3f} MHz"

        mode = self._mode.value
        broad_khz = float(self._broad.value)
        need_direction = mode == "single" or (mode == "powder" and self._overlay.value)
        try:
            result = core.simulate(
                nu_Q or 0.0, eta, spin_I, nu_L, mode=mode,
                n_grid=int(self._npts.value),
                broadening=(broad_khz / MHZ_TO_KHZ) if broad_khz else None,
                second_order=bool(self._second.value),
                decompose=bool(self._decompose.value),
                overlay_peaks=(mode == "powder" and self._overlay.value),
                cell=_matrix_values(self._cell_cells) if need_direction else None,
                eigenvectors=_matrix_values(self._eig_cells) if need_direction else None,
                direction=[self._da.value, self._db.value, self._dc.value]
                          if need_direction else None,
            )
        except ValueError as exc:
            self._show_hint(str(exc), base_info)
            return
        except Exception as exc:
            self._show_hint(f"Could not compute spectrum: {exc}", base_info)
            return

        fig = go.Figure()
        show_legend = False
        export_blocks = []  # (title, column_names, columns) — mirrors the traces
        export_extra = []   # mode-specific metadata lines
        info = base_info

        if mode == "powder":
            block, show_legend = add_powder_traces(
                fig, result["freqs"], result["total"],
                result["per_transition"], nu_L)
            export_blocks.append(block)
            n = max(int(self._npts.value), 8)
            export_extra.append(("orientation_grid", f"{n} x {n}"))
            info += " &nbsp;|&nbsp; %dx%d grid" % (n, n)
            if result["lines"] is not None:
                add_stick_traces(fig, result["lines"], nu_L)
                export_blocks.append(stick_block(
                    "single-crystal peak positions", result["lines"], nu_L))
                export_extra += self._direction_meta(result["theta"], result["phi"])
                info += (f" &nbsp;|&nbsp; peaks at θ = {np.degrees(result['theta']):.1f}°, "
                         f"φ = {np.degrees(result['phi']):.1f}°")
        else:
            if result["envelope"] is not None:
                gx, gy = result["envelope"]
                export_blocks.append(add_envelope_trace(fig, gx, gy, nu_L))
            add_stick_traces(fig, result["lines"], nu_L)
            export_blocks.append(stick_block(
                "single-crystal peak positions", result["lines"], nu_L))
            export_extra += self._direction_meta(result["theta"], result["phi"])
            info += (f" &nbsp;|&nbsp; θ = {np.degrees(result['theta']):.1f}°, "
                     f"φ = {np.degrees(result['phi']):.1f}°")

        # eq 2.29 scales with 1/nu_L, so the backend drops it at nu_L = 0 --
        # say so instead of silently ignoring the checked box
        second = bool(self._second.value)
        second_active = second and nu_L != 0.0
        if second and not second_active:
            info += (" &nbsp;|&nbsp; <span style='color:#d62728;'>2nd-order "
                     "term inactive (ν_L = 0)</span>")

        self._info.value = info
        spectrum_layout(fig, show_legend)
        self._plot.children = [go.FigureWidget(fig)]

        # cache the plotted data for the CSV download (WYSIWYG)
        meta = [
            ("generated", datetime.now().isoformat(timespec="seconds")),
            ("element", self._element.value),
            ("isotope", self._isotope.value),
            ("mode", mode),
            ("B_T", field),
            ("gamma_MHz_per_T", gamma),
            ("nu_L_MHz", nu_L),
            ("I", spin_I),
            ("Cq_MHz", cq),
            ("nu_Q_MHz", nu_Q),
            ("eta", eta),
        ]
        meta += [
            ("broadening_FWHM_kHz", broad_khz),
            # what was actually applied (the term is dropped when nu_L = 0)
            ("second_order", second_active),
        ] + export_extra
        self._set_export({"meta": meta, "blocks": export_blocks})

    def _direction_meta(self, theta, phi):
        """Field-direction metadata lines for the CSV header."""
        return direction_meta(
            (self._da.value, self._db.value, self._dc.value), theta, phi)

    def _download_csv(self, _=None):
        """Download the currently plotted spectrum (cached by _recompute)."""
        from datetime import datetime

        if not self._export:
            return
        csv_text = spectrum_csv(self._export["meta"], self._export["blocks"])
        filename = "quadrupolar_spectrum_{}_{}_{}.csv".format(
            self._isotope.value, self._mode.value,
            datetime.now().strftime("%Y%m%d_%H%M%S"))
        js_download_text(filename, csv_text, "text/csv")
