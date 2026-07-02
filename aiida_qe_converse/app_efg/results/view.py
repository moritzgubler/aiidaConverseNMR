"""Results panel for the EFG plugin."""
import numpy as np
import ipywidgets as ipw
from aiidalab_qe.common.panel import ResultsPanel
from aiidalab_widgets_base.viewers import StructureDataViewer
from .model import EFGResultsModel
from ...data.nuclear import default_gamma, default_q_i, larmor_frequency
from ...postprocessing.efg_analysis import quadrupolar_parameters_from_tensor
from ...postprocessing.quadrupolar_spectrum import (
    powder_spectrum,
    powder_spectrum_by_transition,
    single_crystal_lines,
    broaden_lines,
    lattice_direction_to_angles,
)

# qualitative palette for the per-transition powder curves
_TRANSITION_COLORS = ["#17becf", "#9467bd", "#2ca02c", "#ff7f0e",
                      "#e377c2", "#8c564b", "#bcbd22", "#1f77b4", "#d62728"]

# the spectrum frequency axis (nu - nu_L) is plotted in kHz
_MHZ_TO_KHZ = 1000.0


def _half_int_str(x):
    """Format a multiple of 1/2 as a tidy string: 0.5->'1/2', -1.5->'−3/2', 1->'1'."""
    n = int(round(2 * x))
    s = str(n // 2) if n % 2 == 0 else f"{n}/2"
    return s.replace("-", "−")


class EFGResultsPanel(ResultsPanel[EFGResultsModel]):
    """Panel for displaying EFG / quadrupolar results."""

    identifier = "qeefg"
    title = "EFG / Quadrupolar Parameters"

    def __init__(self, model: EFGResultsModel, **kwargs):
        super().__init__(model, **kwargs)

    def _render(self):
        """Render the results panel."""
        self._model.fetch_results()

        if not self._model.quadrupolar_parameters:
            self.results_container.children = [
                ipw.HTML(
                    "<p style='color: orange;'>No EFG results found. "
                    "The workchain may not have completed successfully.</p>"
                )
            ]
            return

        title = ipw.HTML(
            """
            <h3>Electric Field Gradient Results</h3>
            <p>Per-atom quadrupolar parameters, <b>recomputed live from the stored
            symmetrized EFG tensor</b> — the tensor does not depend on Q or I, so you
            can adjust the nuclear quadrupole moment Q and spin I (e.g. to switch
            isotope) in the spectrum section below without re-running the calculation.</p>
            <ul>
              <li><b>V<sub>zz</sub></b>: largest-|eigenvalue| EFG principal value (Ha/bohr&sup2;)</li>
              <li><b>&eta;</b> = (V<sub>xx</sub> &minus; V<sub>yy</sub>) / V<sub>zz</sub></li>
              <li><b>C<sub>q</sub></b> = e Q V<sub>zz</sub> / h (MHz; only for Q &ne; 0)</li>
              <li><b>&nu;<sub>Q</sub></b> = 3 C<sub>q</sub> / (2I(2I&minus;1)) (MHz; only for Q &ne; 0 and I &ge; 1)</li>
            </ul>
            """
        )

        self._init_qi_by_atom()
        self._summary_table = ipw.HTML()
        self._refresh_summary_table()

        widgets = [title, self._summary_table]

        tensor_widget = self._render_tensor_components()
        if tensor_widget:
            widgets.append(tensor_widget)

        spectrum_widget = self._render_spectrum_section()
        if spectrum_widget:
            widgets.append(spectrum_widget)

        structure_widget = self._render_structure_view()
        if structure_widget:
            widgets.append(structure_widget)

        download_button = ipw.Button(
            description="Download Results", icon="download",
            button_style="primary", tooltip="Download EFG results as JSON",
        )
        download_button.on_click(self._download_results)
        widgets.append(download_button)

        self.results_container.children = widgets

    # ---- live recomputation from the stored EFG tensor with per-atom Q/I ----

    def _init_qi_by_atom(self):
        """Seed per-atom (Q, I): from the values used at submission, else defaults."""
        self._qi_by_atom = {}
        for label in self._model.atom_labels:
            stored = self._model.quadrupolar_parameters.get(label, {})
            q, spin = stored.get("Q"), stored.get("I")
            if q is None or spin is None:
                element = self._atom_element(label)
                dq, di = default_q_i(element) if element else (0.0, 0.0)
                q = dq if q is None else q
                spin = di if spin is None else spin
            self._qi_by_atom[label] = (float(q), float(spin))

    def _current_qp(self, label):
        """Quadrupolar parameters for ``label``, recomputed from its tensor."""
        tensor = self._model.efg_tensors.get(label)
        if tensor is None:
            return None
        q, spin = self._qi_by_atom.get(label, (0.0, 0.0))
        qp = quadrupolar_parameters_from_tensor(tensor, q, spin)
        qp["Q"], qp["I"] = q, spin
        return qp

    def _refresh_summary_table(self):
        rows_html = ""
        for label in self._model.atom_labels:
            qp = self._current_qp(label)
            if qp is None:  # no tensor stored (legacy run): fall back to parsed values
                qp = dict(self._model.quadrupolar_parameters.get(label, {}))
            cells = [
                label,
                self._model._fmt(qp.get("Q")),
                self._model._fmt(qp.get("I"), 1),
                self._model._fmt(qp.get("Vzz")),
                self._model._fmt(qp.get("eta"), 5),
                self._model._fmt(qp.get("Cq")),
                self._model._fmt(qp.get("nu_Q")),
            ]
            rows_html += "<tr>" + "".join(
                f"<td style='padding: 8px; border: 1px solid #ddd; text-align: "
                f"{'center' if i == 0 else 'right'};'>{c}</td>"
                for i, c in enumerate(cells)
            ) + "</tr>"

        if not rows_html:
            self._summary_table.value = "<p>No quadrupolar data available.</p>"
            return

        html = "<h4>Quadrupolar Parameter Summary</h4>"
        html += "<table style='border-collapse: collapse; width: 100%; margin: 10px 0;'>"
        html += "<tr style='background-color: #f0f0f0;'>"
        for header in ["Atom", "Q (10&#8315;&sup3;&#8304; m&sup2;)", "I",
                       "V<sub>zz</sub> (Ha/bohr&sup2;)", "&eta;",
                       "C<sub>q</sub> (MHz)", "&nu;<sub>Q</sub> (MHz)"]:
            html += f"<th style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{header}</th>"
        html += "</tr>" + rows_html + "</table>"
        self._summary_table.value = html

    def _render_tensor_components(self):
        if not self._model.efg_tensors:
            return None

        self.atom_selector = ipw.Dropdown(
            options=self._model.atom_labels,
            description="Select Atom:",
            style={"description_width": "100px"},
        )
        self.tensor_display = ipw.HTML()
        self.atom_selector.observe(self._update_tensor_display, names="value")

        if self._model.atom_labels:
            self.atom_selector.value = self._model.atom_labels[0]
            self._update_tensor_display({"new": self._model.atom_labels[0]})

        return ipw.VBox([
            ipw.HTML("<h4>EFG Tensor Details</h4>"),
            self.atom_selector,
            self.tensor_display,
        ])

    def _update_tensor_display(self, change):
        import re

        atom_label = change["new"]
        if atom_label not in self._model.efg_tensors:
            self.tensor_display.value = "<p>No tensor data available for this atom.</p>"
            return

        tensor = self._model.efg_tensors[atom_label]
        params = self._current_qp(atom_label) or self._model.quadrupolar_parameters.get(atom_label, {})

        html = f"<h5>EFG Tensor for {atom_label} (Ha/bohr&sup2;)</h5>"
        detail = []
        for key, label in [("Vxx", "V<sub>xx</sub>"), ("Vyy", "V<sub>yy</sub>"),
                           ("Vzz", "V<sub>zz</sub>"), ("eta", "&eta;"),
                           ("Cq", "C<sub>q</sub> (MHz)"), ("nu_Q", "&nu;<sub>Q</sub> (MHz)")]:
            if key in params and params[key] is not None:
                detail.append(f"{label} = {self._model._fmt(params[key])}")
        if detail:
            html += "<p>" + " &nbsp;|&nbsp; ".join(detail) + "</p>"

        html += "<table style='border-collapse: collapse; margin: 10px 0;'>"
        html += "<tr style='background-color: #f0f0f0;'>"
        html += "<th style='padding: 8px; border: 1px solid #ddd;'></th>"
        for col in ["x", "y", "z"]:
            html += f"<th style='padding: 8px; border: 1px solid #ddd;'>{col}</th>"
        html += "</tr>"
        for i, row_label in enumerate(["x", "y", "z"]):
            html += "<tr>"
            html += f"<th style='padding: 8px; border: 1px solid #ddd; background-color: #f0f0f0;'>{row_label}</th>"
            for j in range(3):
                value = tensor[i][j]
                html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{value:.6f}</td>"
            html += "</tr>"
        html += "</table>"
        self.tensor_display.value = html

        if hasattr(self, 'structure_viewer'):
            match = re.match(r"([A-Za-z][A-Za-z0-9]*?)(\d+)$", atom_label)
            if match:
                index = int(match.group(2)) - 1
                self.structure_viewer.displayed_selection = [index]

    # ---------------- quadrupolar spectrum (eqs 2.28-2.33, Fig 2.3) ----------------

    def _quadrupolar_atoms(self):
        """Labels of atoms with a stored EFG tensor (Q and I are adjustable live)."""
        return [label for label in self._model.atom_labels
                if label in self._model.efg_tensors]

    def _atom_element(self, label):
        import re
        m = re.match(r"([A-Za-z][A-Za-z0-9]*?)(\d+)$", label)
        if not m or not self._model.structure:
            return None
        idx = int(m.group(2)) - 1
        try:
            site = self._model.structure.sites[idx]
            return self._model.structure.get_kind(site.kind_name).symbols[0]
        except Exception:
            return None

    def _render_spectrum_section(self):
        atoms = self._quadrupolar_atoms()
        if not atoms:
            return ipw.VBox([ipw.HTML(
                "<h4>Quadrupolar NMR spectrum</h4>"
                "<p><i>No EFG tensors stored for this calculation.</i></p>"
            )])

        self._spec_mode = ipw.ToggleButtons(
            options=[("Powder (orientation average)", "powder"),
                     ("Single crystal (fixed direction)", "single")],
            value="powder",
        )
        self._spec_atom = ipw.Dropdown(options=atoms, description="Atom:",
                                       style={"description_width": "120px"})
        self._spec_B = ipw.FloatText(value=9.4, description="B field (T):",
                                     style={"description_width": "120px"})
        self._spec_gamma = ipw.FloatText(value=0.0, description="|γ| (MHz/T):",
                                         style={"description_width": "120px"})
        self._spec_Q = ipw.FloatText(value=0.0, description="Q (10⁻³⁰ m²):",
                                     style={"description_width": "120px"})
        self._spec_I = ipw.FloatText(value=0.0, description="I:",
                                     style={"description_width": "120px"})
        self._spec_broad = ipw.FloatText(value=0.0, description="broadening (kHz):",
                                         style={"description_width": "140px"})
        self._spec_second = ipw.Checkbox(value=True, indent=False,
                                         description="include 2nd-order term (eq 2.29)")

        # powder-only controls: averaging scheme
        self._spec_method = ipw.Dropdown(
            options=[("Equal-area grid", "grid"), ("Lebedev quadrature", "lebedev")],
            value="grid", description="Averaging:", style={"description_width": "120px"})
        self._spec_npts = ipw.IntText(value=200, description="grid n (θ,φ):",
                                      style={"description_width": "120px"},
                                      layout=ipw.Layout(width="220px"))
        self._spec_leb = ipw.Dropdown(
            options=[17, 29, 53, 89, 131], value=53, description="Lebedev order:",
            style={"description_width": "120px"}, layout=ipw.Layout(width="220px"))
        self._spec_decompose = ipw.Checkbox(value=False, indent=False,
                                            description="decompose by transition")
        self._spec_powder_box = ipw.VBox([
            ipw.HBox([self._spec_method, self._spec_npts, self._spec_leb]),
            self._spec_decompose,
        ])

        # single-crystal-only controls: field direction in lattice units
        self._spec_da = ipw.FloatText(value=0.0, description="a:",
                                      layout=ipw.Layout(width="120px"),
                                      style={"description_width": "20px"})
        self._spec_db = ipw.FloatText(value=0.0, description="b:",
                                      layout=ipw.Layout(width="120px"),
                                      style={"description_width": "20px"})
        self._spec_dc = ipw.FloatText(value=1.0, description="c:",
                                      layout=ipw.Layout(width="120px"),
                                      style={"description_width": "20px"})
        self._spec_single_box = ipw.VBox([
            ipw.HTML("<b>Field direction</b> (lattice-vector units, normalised automatically):"),
            ipw.HBox([self._spec_da, self._spec_db, self._spec_dc]),
        ])

        self._spec_info = ipw.HTML()
        # Container holding a plotly FigureWidget (display(fig) does not render here).
        self._spec_plot = ipw.VBox()

        self._spec_updating = False
        self._spec_on_atom_change()         # seed gamma/Q/I/broadening
        self._update_spectrum_visibility()  # show the right controls for the mode

        self._spec_atom.observe(lambda c: self._spec_on_atom_change(), names="value")
        self._spec_mode.observe(lambda c: self._update_spectrum_visibility(), names="value")
        self._spec_method.observe(lambda c: self._update_spectrum_visibility(), names="value")
        for w in (self._spec_Q, self._spec_I):
            w.observe(lambda c: self._on_qi_change(), names="value")
        for w in (self._spec_B, self._spec_gamma, self._spec_broad, self._spec_npts,
                  self._spec_leb, self._spec_da, self._spec_db, self._spec_dc,
                  self._spec_second, self._spec_decompose):
            w.observe(lambda c: self._recompute_spectrum(), names="value")
        self._recompute_spectrum()

        controls = ipw.VBox([
            self._spec_mode,
            self._spec_atom,
            ipw.HBox([self._spec_B, self._spec_gamma]),
            ipw.HBox([self._spec_Q, self._spec_I]),
            self._spec_powder_box,
            self._spec_single_box,
            ipw.HBox([self._spec_broad, self._spec_second]),
            self._spec_info,
        ])
        return ipw.VBox([
            ipw.HTML(
                "<h4>Quadrupolar NMR spectrum</h4>"
                "<p><b>Powder</b>: average over all field orientations (eqs 2.28–2.33), "
                "independent of direction — pick an equal-area grid or Lebedev "
                "quadrature. <b>Single crystal</b>: discrete transition lines for a "
                "fixed field direction, projected onto the EFG principal axes to get "
                "(θ, φ). The field strength sets ν<sub>L</sub> = |γ|·B. "
                "<b>Q and I are adjustable</b> (e.g. to switch isotope): η, C<sub>q</sub> "
                "and ν<sub>Q</sub> are recomputed live from the stored EFG tensor — "
                "the tensor itself does not depend on them.</p>"),
            controls,
            self._spec_plot,
        ])

    def _update_spectrum_visibility(self):
        powder = self._spec_mode.value == "powder"
        self._spec_powder_box.layout.display = "" if powder else "none"
        self._spec_single_box.layout.display = "none" if powder else ""
        lebedev = self._spec_method.value == "lebedev"
        self._spec_npts.layout.display = "none" if lebedev else "inline-flex"
        self._spec_leb.layout.display = "inline-flex" if lebedev else "none"
        self._recompute_spectrum()

    def _spec_on_atom_change(self):
        label = self._spec_atom.value
        self._spec_updating = True
        try:
            element = self._atom_element(label)
            gamma = default_gamma(element) if element else None
            if gamma is not None:
                self._spec_gamma.value = float(gamma)
            q, spin = self._qi_by_atom.get(label, (0.0, 0.0))
            self._spec_Q.value = q
            self._spec_I.value = spin
            qp = self._current_qp(label) or {}
            nu_Q = abs(qp.get("nu_Q") or 0.0)  # MHz
            if self._spec_broad.value == 0.0:
                # default FWHM ~2% of nu_Q, in kHz (min 5 kHz)
                self._spec_broad.value = round(max(0.02 * nu_Q * _MHZ_TO_KHZ, 5.0), 1)
        finally:
            self._spec_updating = False
        self._recompute_spectrum()

    def _on_qi_change(self):
        """User edited Q or I: store per atom, refresh table/details/spectrum."""
        if self._spec_updating:
            return
        label = self._spec_atom.value
        self._qi_by_atom[label] = (float(self._spec_Q.value), float(self._spec_I.value))
        self._refresh_summary_table()
        if hasattr(self, "atom_selector") and self.atom_selector.value:
            self._update_tensor_display({"new": self.atom_selector.value})
        self._recompute_spectrum()

    def _recompute_spectrum(self):
        import plotly.graph_objects as go

        if self._spec_updating:
            return
        label = self._spec_atom.value
        qp = self._current_qp(label)
        if qp is None:
            self._spec_plot.children = [ipw.HTML("<i>No EFG tensor stored for this atom.</i>")]
            self._spec_info.value = ""
            return
        eta = float(qp["eta"])
        cq = qp.get("Cq")
        nu_Q = float(qp.get("nu_Q") or 0.0)
        spin_I = float(self._spec_I.value)
        axes = qp["eigenvectors"]
        nu_L = abs(float(self._spec_gamma.value)) * float(self._spec_B.value)
        broad_khz = float(self._spec_broad.value)
        broad = (broad_khz / _MHZ_TO_KHZ) if broad_khz else None  # backend works in MHz
        second = bool(self._spec_second.value)

        base_info = (f"ν<sub>L</sub> = |γ|·B = {nu_L:.3f} MHz &nbsp;|&nbsp; "
                     f"V<sub>zz</sub> = {qp['Vzz']:.4f} Ha/bohr² &nbsp;|&nbsp; "
                     f"η = {eta:.4f} &nbsp;|&nbsp; "
                     + (f"C<sub>q</sub> = {cq:.4f} MHz &nbsp;|&nbsp; " if cq is not None else "")
                     + f"ν<sub>Q</sub> = {nu_Q:.4f} MHz &nbsp;|&nbsp; I = {spin_I:g}")

        if spin_I < 1.0:
            self._spec_plot.children = [ipw.HTML(
                "<i>A quadrupolar spectrum needs I ≥ 1 — adjust I above "
                "(spin-1/2 isotopes have no quadrupole interaction).</i>")]
            self._spec_info.value = base_info
            return

        fig = go.Figure()
        show_legend = False

        try:
            if self._spec_mode.value == "powder":
                method = self._spec_method.value
                n = max(int(self._spec_npts.value), 8)
                kwargs = dict(n_theta=n, n_phi=n, broadening=broad, method=method,
                              lebedev_order=int(self._spec_leb.value), second_order=second)
                if self._spec_decompose.value:
                    # one curve per transition (thesis Fig. 2.3) + total
                    freqs, per, total = powder_spectrum_by_transition(
                        nu_Q, eta, spin_I, nu_L, **kwargs)
                    fig.add_trace(go.Scatter(x=(freqs - nu_L) * _MHZ_TO_KHZ, y=total,
                                             mode="lines", name="total",
                                             line=dict(color="#000000", width=2)))
                    for i, (m, inten) in enumerate(per):
                        lbl = f"{_half_int_str(m - 1)}↔{_half_int_str(m)}"
                        fig.add_trace(go.Scatter(
                            x=(freqs - nu_L) * _MHZ_TO_KHZ, y=inten, mode="lines", name=lbl,
                            line=dict(color=_TRANSITION_COLORS[i % len(_TRANSITION_COLORS)],
                                      dash="dash")))
                    show_legend = True
                else:
                    freqs, inten = powder_spectrum(nu_Q, eta, spin_I, nu_L, **kwargs)
                    fig.add_trace(go.Scatter(x=(freqs - nu_L) * _MHZ_TO_KHZ, y=inten,
                                             mode="lines", line=dict(color="#1f77b4")))
                scheme = ("Lebedev order %d" % int(self._spec_leb.value)
                          if method == "lebedev" else "%dx%d grid" % (n, n))
                self._spec_info.value = base_info + f" &nbsp;|&nbsp; {scheme}"
            else:
                theta = phi = None
                if self._model.structure and all(k in axes for k in ("Vxx", "Vyy", "Vzz")):
                    direction = [self._spec_da.value, self._spec_db.value, self._spec_dc.value]
                    theta, phi = lattice_direction_to_angles(
                        direction, self._model.structure.cell, axes)
                if theta is None:
                    self._spec_plot.children = [ipw.HTML(
                        "<i>Single-crystal mode needs the structure and EFG "
                        "eigenvectors (missing here).</i>")]
                    self._spec_info.value = base_info
                    return
                lines = single_crystal_lines(nu_Q, eta, spin_I, nu_L, theta, phi,
                                             second_order=second)
                if broad:
                    gx, gy = broaden_lines(lines, broad)
                    fig.add_trace(go.Scatter(x=(gx - nu_L) * _MHZ_TO_KHZ, y=gy, mode="lines",
                                             line=dict(color="#1f77b4")))
                wmax = max((w for _, w, _ in lines), default=1.0) or 1.0
                for freq, weight, m in lines:
                    x0 = (freq - nu_L) * _MHZ_TO_KHZ
                    height = weight / wmax
                    label = f"{_half_int_str(m - 1)}↔{_half_int_str(m)}"
                    fig.add_trace(go.Scatter(
                        x=[x0, x0], y=[0.0, height], mode="lines",
                        line=dict(color="#d62728", width=2), showlegend=False,
                        hoverinfo="text", hovertext=f"{label}  (Δν = {x0:.2f} kHz)"))
                    fig.add_trace(go.Scatter(
                        x=[x0], y=[height], mode="markers+text",
                        marker=dict(color="#d62728", size=4),
                        text=[label], textposition="top center",
                        textfont=dict(size=10, color="#d62728"),
                        showlegend=False, hoverinfo="skip"))
                fig.update_yaxes(range=[0.0, 1.2])  # headroom for the labels
                self._spec_info.value = (base_info +
                    f" &nbsp;|&nbsp; θ = {np.degrees(theta):.1f}°, φ = {np.degrees(phi):.1f}°")
        except Exception as exc:
            self._spec_plot.children = [ipw.HTML(f"<i>Could not compute spectrum: {exc}</i>")]
            return

        fig.update_layout(
            xaxis_title="ν − ν_L (kHz)", yaxis_title="intensity (norm.)",
            height=420, margin=dict(l=50, r=20, t=20, b=50),
            template="plotly_white", showlegend=show_legend)
        self._spec_plot.children = [go.FigureWidget(fig)]

    def _render_structure_view(self):
        import re

        if not self._model.structure:
            return None

        self.structure_viewer = StructureDataViewer(self._model.structure)
        if hasattr(self, 'atom_selector') and self.atom_selector.value:
            match = re.match(r"([A-Za-z][A-Za-z0-9]*?)(\d+)$", self.atom_selector.value)
            if match:
                index = int(match.group(2)) - 1
                self.structure_viewer.displayed_selection = [index]

        return ipw.VBox([
            ipw.HTML("<h4>Structure with EFG Sites</h4>"),
            ipw.HTML("<p>The highlighted atom corresponds to the selection above.</p>"),
            self.structure_viewer,
        ])

    def _download_results(self, _=None):
        import json
        from datetime import datetime

        recomputed = {
            label: self._current_qp(label)
            for label in self._model.atom_labels
            if self._current_qp(label) is not None
        }
        results_data = {
            "calculation_date": datetime.now().isoformat(),
            "workchain_label": self.identifier,
            "quadrupolar_parameters_as_computed": self._model.quadrupolar_parameters,
            "quadrupolar_parameters_recomputed": recomputed,
            "efg_tensors": self._model.efg_tensors,
            "atom_labels": self._model.atom_labels,
        }
        json_str = json.dumps(results_data, indent=2)
        filename = f"efg_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        from IPython.display import display, Javascript
        js_download = f"""
        var data = {json_str};
        var blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = '{filename}';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        """
        display(Javascript(js_download))
