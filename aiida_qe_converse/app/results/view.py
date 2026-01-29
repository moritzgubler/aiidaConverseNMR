"""
Results panel for NMR Converse plugin.
"""
import ipywidgets as ipw
from aiidalab_qe.common.panel import ResultsPanel
from aiidalab_widgets_base.viewers import StructureDataViewer
from .model import NMRResultsModel


class NMRResultsPanel(ResultsPanel[NMRResultsModel]):
    """Panel for displaying NMR Converse results."""

    identifier = "qeconverse"
    title = "NMR Chemical Shifts"

    def __init__(self, model: NMRResultsModel, **kwargs):
        super().__init__(model, **kwargs)

    def _render(self):
        """Render the results panel."""
        # Fetch results from workchain
        self._model.fetch_results()

        # Check if we have results to display
        if not self._model.isotropic_shielding:
            self.results_container.children = [
                ipw.HTML(
                    "<p style='color: orange;'>No NMR results found. "
                    "The workchain may not have completed successfully.</p>"
                )
            ]
            return

        # Create the results widgets
        title = ipw.HTML(
            """
            <h3>NMR Chemical Shielding Results</h3>
            <p>The table below shows the computed NMR chemical shielding for the selected atoms.
            Values are reported in ppm (parts per million).</p>
            <p><b>Isotropic shielding:</b> σ<sub>iso</sub> = Tr(σ) / 3</p>
            """
        )

        # Create the main table
        table_widget = self._render_isotropic_shielding_table()

        # Create tensor details section
        tensor_details_widget = self._render_tensor_components()

        # Create structure viewer if available
        structure_widget = self._render_structure_view()

        # Assemble the panel
        widgets = [title, table_widget]

        if tensor_details_widget:
            widgets.append(tensor_details_widget)

        if structure_widget:
            widgets.append(structure_widget)

        # Download button
        download_button = ipw.Button(
            description="Download Results",
            icon="download",
            button_style="primary",
            tooltip="Download NMR results as JSON",
        )
        download_button.on_click(self._download_results)
        widgets.append(download_button)

        self.results_container.children = widgets

    def _render_isotropic_shielding_table(self):
        """Render table of isotropic shielding values for all atoms."""
        if not self._model.table_data:
            return ipw.HTML("<p>No shielding data available.</p>")

        # Build HTML table
        html = "<h4>Chemical Shielding Tensor Summary</h4>"
        html += "<table style='border-collapse: collapse; width: 100%; margin: 10px 0;'>"

        # Header row
        html += "<tr style='background-color: #f0f0f0;'>"
        headers = ["Atom", "σ<sub>iso</sub> (ppm)"]
        for header in headers:
            html += f"<th style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{header}</th>"
        html += "</tr>"

        # Data rows
        for row in self._model.table_data:
            html += "<tr>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: center;'>{row.get('Atom', '')}</td>"
            html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{row.get('Isotropic (ppm)', '')}</td>"
            html += "</tr>"

        html += "</table>"

        return ipw.HTML(html)

    def _render_tensor_components(self):
        """Render full chemical shift tensor components."""
        if not self._model.chemical_shift_tensors:
            return None

        # Create a dropdown to select which atom to display
        self.atom_selector = ipw.Dropdown(
            options=self._model.atom_labels,
            description="Select Atom:",
            style={"description_width": "100px"},
        )

        # Create an HTML widget to display the tensor
        self.tensor_display = ipw.HTML()

        self.atom_selector.observe(self._update_tensor_display, names="value")

        # Initialize with first atom
        if self._model.atom_labels:
            self.atom_selector.value = self._model.atom_labels[0]
            # Manually trigger the update since setting initial value doesn't fire observe
            self._update_tensor_display({"new": self._model.atom_labels[0]})

        return ipw.VBox([
            ipw.HTML("<h4>Full Shielding Tensor Details</h4>"),
            self.atom_selector,
            self.tensor_display,
        ])

    def _update_tensor_display(self, change):
        """Update tensor display for selected atom."""
        import re

        atom_label = change["new"]
        if atom_label not in self._model.chemical_shift_tensors:
            self.tensor_display.value = "<p>No tensor data available for this atom.</p>"
            return

        tensor = self._model.chemical_shift_tensors[atom_label]

        # Get isotropic value from model
        iso_value = self._model.isotropic_shielding.get(atom_label, {}).get("isotropic_shielding_ppm", 0.0)

        # Format the tensor as HTML
        html = f"<h5>Chemical Shielding Tensor for {atom_label} (ppm)</h5>"
        html += f"<p><b>Isotropic shielding:</b> σ<sub>iso</sub> = {iso_value:.3f} ppm</p>"
        html += "<table style='border-collapse: collapse; margin: 10px 0;'>"
        html += "<tr style='background-color: #f0f0f0;'>"
        html += "<th style='padding: 8px; border: 1px solid #ddd;'></th>"
        html += "<th style='padding: 8px; border: 1px solid #ddd;'>x</th>"
        html += "<th style='padding: 8px; border: 1px solid #ddd;'>y</th>"
        html += "<th style='padding: 8px; border: 1px solid #ddd;'>z</th>"
        html += "</tr>"

        for i, row_label in enumerate(["x", "y", "z"]):
            html += "<tr>"
            html += f"<th style='padding: 8px; border: 1px solid #ddd; background-color: #f0f0f0;'>{row_label}</th>"
            for j in range(3):
                value = tensor[i][j]
                html += f"<td style='padding: 8px; border: 1px solid #ddd; text-align: right;'>{value:.3f}</td>"
            html += "</tr>"

        html += "</table>"

        self.tensor_display.value = html

        # Update structure viewer highlighting
        if hasattr(self, 'structure_viewer'):
            match = re.match(r"([A-Za-z]+)(\d+)", atom_label)
            if match:
                index = int(match.group(2)) - 1  # Convert to 0-based
                self.structure_viewer.displayed_selection = [index]

    def _render_structure_view(self):
        """Render structure with selected atom highlighted."""
        import re

        if not self._model.structure:
            return None

        self.structure_viewer = StructureDataViewer(self._model.structure)

        # Highlight the currently selected atom (if atom_selector exists)
        if hasattr(self, 'atom_selector') and self.atom_selector.value:
            match = re.match(r"([A-Za-z]+)(\d+)", self.atom_selector.value)
            if match:
                index = int(match.group(2)) - 1  # Convert to 0-based
                self.structure_viewer.displayed_selection = [index]

        return ipw.VBox([
            ipw.HTML("<h4>Structure with NMR-Active Sites</h4>"),
            ipw.HTML("<p>The highlighted atom corresponds to the selection above.</p>"),
            self.structure_viewer,
        ])

    def _download_results(self, _=None):
        """Download NMR results as JSON file."""
        import json
        from datetime import datetime

        # Prepare data for download
        results_data = {
            "calculation_date": datetime.now().isoformat(),
            "workchain_label": self.identifier,
            "isotropic_shielding": self._model.isotropic_shielding,
            "chemical_shift_tensors": self._model.chemical_shift_tensors,
            "atom_labels": self._model.atom_labels,
        }

        # Create download link
        json_str = json.dumps(results_data, indent=2)
        filename = f"nmr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Create a download widget
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
