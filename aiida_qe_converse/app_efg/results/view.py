"""Results panel for the EFG plugin."""
import ipywidgets as ipw
from aiidalab_qe.common.panel import ResultsPanel
from aiidalab_widgets_base.viewers import StructureDataViewer
from .model import EFGResultsModel


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
