"""Results panel for the EFG plugin."""
import numpy as np
import ipywidgets as ipw
from aiidalab_qe.common.panel import ResultsPanel
from aiidalab_widgets_base.viewers import StructureDataViewer
from .model import EFGResultsModel
from ...data.nuclear import default_gamma, larmor_frequency
from ...postprocessing.quadrupolar_spectrum import (
    powder_spectrum,
    single_crystal_lines,
    lattice_direction_to_angles,
)


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
            <p>Per-atom quadrupolar parameters from the symmetrized EFG tensor.</p>
            <ul>
              <li><b>V<sub>zz</sub></b>: largest-|eigenvalue| EFG principal value (Ha/bohr&sup2;)</li>
              <li><b>&eta;</b> = (V<sub>xx</sub> &minus; V<sub>yy</sub>) / V<sub>zz</sub></li>
              <li><b>C<sub>q</sub></b> = e Q V<sub>zz</sub> / h (MHz; only for Q &ne; 0)</li>
              <li><b>&nu;<sub>Q</sub></b> = 3 C<sub>q</sub> / (2I(2I&minus;1)) (MHz; only for I &ge; 1)</li>
            </ul>
            """
        )

        widgets = [title, self._render_summary_table()]

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

    def _render_summary_table(self):
        if not self._model.table_data:
            return ipw.HTML("<p>No quadrupolar data available.</p>")

        html = "<h4>Quadrupolar Parameter Summary</h4>"
        html += "<table style='border-collapse: collapse; width: 100%; margin: 10px 0;'>"
        html += "<tr style='background-color: #f0f0f0;'>"
        for header in ["Atom", "V<sub>zz</sub>", "&eta;", "C<sub>q</sub> (MHz)", "&nu;<sub>Q</sub> (MHz)"]:
            html += f"<th style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{header}</th>"
        html += "</tr>"
        for row in self._model.table_data:
            html += "<tr>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{row['Atom']}</td>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{row['Vzz']}</td>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{row['eta']}</td>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{row['Cq']}</td>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{row['nu_Q']}</td>"
            html += "</tr>"
        html += "</table>"
        return ipw.HTML(html)

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
        params = self._model.quadrupolar_parameters.get(atom_label, {})

        html = f"<h5>EFG Tensor for {atom_label} (Ha/bohr&sup2;)</h5>"
        detail = []
        for key, label in [("Vxx", "V<sub>xx</sub>"), ("Vyy", "V<sub>yy</sub>"),
                           ("Vzz", "V<sub>zz</sub>"), ("eta", "&eta;"),
                           ("Cq", "C<sub>q</sub> (MHz)"), ("nu_Q", "&nu;<sub>Q</sub> (MHz)")]:
            if key in params and params[key] is not None:
                detail.append(f"{label} = {params[key]}")
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
        """Labels of atoms with a defined quadrupolar spectrum (I>=1 and nu_Q)."""
        out = []
        for label in self._model.atom_labels:
            p = self._model.quadrupolar_parameters.get(label, {})
            spin = p.get("I")
            if p.get("nu_Q") is not None and spin is not None and spin >= 1.0:
                out.append(label)
        return out

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
                "<p><i>No quadrupolar-active sites in this structure "
                "(a spectrum needs I&ge;1 and Q&ne;0).</i></p>"
            )])

        self._spec_atom = ipw.Dropdown(options=atoms, description="Atom:",
                                       style={"description_width": "120px"})
        self._spec_B = ipw.FloatText(value=9.4, description="B field (T):",
                                     style={"description_width": "120px"})
        self._spec_gamma = ipw.FloatText(value=0.0, description="|γ| (MHz/T):",
                                         style={"description_width": "120px"})
        self._spec_da = ipw.FloatText(value=0.0, description="a:",
                                      layout=ipw.Layout(width="120px"),
                                      style={"description_width": "20px"})
        self._spec_db = ipw.FloatText(value=0.0, description="b:",
                                      layout=ipw.Layout(width="120px"),
                                      style={"description_width": "20px"})
        self._spec_dc = ipw.FloatText(value=1.0, description="c:",
                                      layout=ipw.Layout(width="120px"),
                                      style={"description_width": "20px"})
        self._spec_broad = ipw.FloatText(value=0.0, description="broadening (MHz):",
                                         style={"description_width": "140px"})
        self._spec_info = ipw.HTML()
        # Container that holds a plotly FigureWidget (the pattern aiidalab-qe uses
        # for its own plots; display(fig) into an Output does not render here).
        self._spec_plot = ipw.VBox()

        self._spec_on_atom_change()  # seed gamma/broadening from first atom
        self._spec_atom.observe(lambda c: self._spec_on_atom_change(), names="value")
        for w in (self._spec_B, self._spec_gamma, self._spec_da, self._spec_db,
                  self._spec_dc, self._spec_broad):
            w.observe(lambda c: self._recompute_spectrum(), names="value")
        self._recompute_spectrum()

        controls = ipw.VBox([
            self._spec_atom,
            ipw.HBox([self._spec_B, self._spec_gamma]),
            ipw.HTML("<b>Field direction</b> (lattice-vector units, normalised automatically):"),
            ipw.HBox([self._spec_da, self._spec_db, self._spec_dc]),
            self._spec_broad,
            self._spec_info,
        ])
        return ipw.VBox([
            ipw.HTML(
                "<h4>Quadrupolar NMR spectrum</h4>"
                "<p>Powder lineshape (orientation average, eqs 2.28–2.33) with the "
                "single-crystal transition lines for the entered field direction "
                "overlaid (red). The field strength sets "
                "ν<sub>L</sub> = |γ|·B; the direction is projected onto the EFG "
                "principal axes to get (θ, φ).</p>"),
            controls,
            self._spec_plot,
        ])

    def _spec_on_atom_change(self):
        label = self._spec_atom.value
        element = self._atom_element(label)
        gamma = default_gamma(element) if element else None
        if gamma is not None:
            self._spec_gamma.value = float(gamma)
        p = self._model.quadrupolar_parameters.get(label, {})
        nu_Q = abs(p.get("nu_Q") or 0.0)
        if self._spec_broad.value == 0.0:
            self._spec_broad.value = round(max(0.02 * nu_Q, 0.01), 4)
        self._recompute_spectrum()

    def _recompute_spectrum(self):
        import plotly.graph_objects as go

        label = self._spec_atom.value
        p = self._model.quadrupolar_parameters.get(label, {})
        eta = float(p.get("eta") or 0.0)
        nu_Q = float(p.get("nu_Q") or 0.0)
        spin_I = float(p.get("I") or 0.0)
        axes = p.get("eigenvectors") or {}
        nu_L = abs(float(self._spec_gamma.value)) * float(self._spec_B.value)
        direction = [self._spec_da.value, self._spec_db.value, self._spec_dc.value]
        broad = float(self._spec_broad.value) or None

        theta = phi = None
        try:
            if self._model.structure and all(k in axes for k in ("Vxx", "Vyy", "Vzz")):
                theta, phi = lattice_direction_to_angles(
                    direction, self._model.structure.cell, axes)
        except Exception:
            theta = phi = None

        info = (f"ν<sub>L</sub> = |γ|·B = {nu_L:.3f} MHz &nbsp;|&nbsp; "
                f"ν<sub>Q</sub> = {nu_Q:.4f} MHz &nbsp;|&nbsp; η = {eta:.4f} "
                f"&nbsp;|&nbsp; I = {spin_I:g}")
        if theta is not None:
            info += f" &nbsp;|&nbsp; θ = {np.degrees(theta):.1f}°, φ = {np.degrees(phi):.1f}°"
        self._spec_info.value = info

        try:
            freqs, inten = powder_spectrum(nu_Q, eta, spin_I, nu_L, broadening=broad)
        except Exception as exc:
            self._spec_plot.children = [ipw.HTML(f"<i>Could not compute spectrum: {exc}</i>")]
            return

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=freqs - nu_L, y=inten, mode="lines",
                                 name="powder", line=dict(color="#1f77b4")))
        if theta is not None:
            lines = single_crystal_lines(nu_Q, eta, spin_I, nu_L, theta, phi)
            wmax = max((w for _, w, _ in lines), default=1.0) or 1.0
            for freq, weight, m in lines:
                fig.add_trace(go.Scatter(
                    x=[freq - nu_L, freq - nu_L], y=[0.0, weight / wmax],
                    mode="lines", line=dict(color="#d62728", width=2),
                    showlegend=False, hovertext=f"m: {m-1:g}→{m:g}"))
        fig.update_layout(
            xaxis_title="ν − ν_L (MHz)", yaxis_title="intensity (norm.)",
            height=420, margin=dict(l=50, r=20, t=20, b=50),
            template="plotly_white", showlegend=False)
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

        results_data = {
            "calculation_date": datetime.now().isoformat(),
            "workchain_label": self.identifier,
            "quadrupolar_parameters": self._model.quadrupolar_parameters,
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
