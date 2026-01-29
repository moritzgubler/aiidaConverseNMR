"""
Results panel for NMR Converse plugin.
"""
import ipywidgets as ipw
import numpy as np
from aiidalab_qe.common.panel import ResultsPanel
from aiidalab_qe.common.widgets import TableWidget
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
            <p>The table below shows the computed NMR chemical shielding tensors for the selected atoms.
            Values are reported in ppm (parts per million).</p>
            <p><b>Isotropic shielding:</b> σ<sub>iso</sub> = (σ<sub>11</sub> + σ<sub>22</sub> + σ<sub>33</sub>) / 3</p>
            <p><b>Anisotropy:</b> δ = σ<sub>33</sub> - (σ<sub>11</sub> + σ<sub>22</sub>) / 2</p>
            <p><b>Asymmetry:</b> η = (σ<sub>22</sub> - σ<sub>11</sub>) / (σ<sub>33</sub> - σ<sub>iso</sub>)</p>
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
        """Render table of isotropic shielding values."""
        table = TableWidget(layout=ipw.Layout(width="auto", height="auto"))

        # Link model data to table
        ipw.dlink(
            (self._model, "table_data"),
            (table, "data"),
        )

        return ipw.VBox([
            ipw.HTML("<h4>Chemical Shielding Tensor Summary</h4>"),
            table,
        ])

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

        tensor = np.array(self._model.chemical_shift_tensors[atom_label])

        # Compute derived values
        eigenvalues = np.linalg.eigvalsh(tensor)
        eigenvalues = np.sort(eigenvalues)[::-1]

        # Get isotropic value from model
        iso_value = self._model.isotropic_shielding.get(atom_label, {}).get("isotropic_shielding_ppm", 0.0)

        # Compute anisotropy and asymmetry
        anisotropy = eigenvalues[2] - (eigenvalues[0] + eigenvalues[1]) / 2
        if abs(eigenvalues[2] - iso_value) > 1e-6:
            asymmetry = (eigenvalues[1] - eigenvalues[0]) / (eigenvalues[2] - iso_value)
        else:
            asymmetry = 0.0

        # Format the tensor as HTML
        html = f"<h5>Chemical Shielding Tensor for {atom_label} (ppm)</h5>"
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

        # Add derived values
        html += "<h5>Derived Properties</h5>"
        html += "<ul>"
        html += f"<li><b>Isotropic shielding:</b> σ<sub>iso</sub> = {iso_value:.3f} ppm</li>"
        html += f"<li><b>Anisotropy:</b> δ = {anisotropy:.3f} ppm</li>"
        html += f"<li><b>Asymmetry:</b> η = {asymmetry:.3f}</li>"
        html += "</ul>"

        # Add principal components
        html += "<h5>Principal Components (Eigenvalues)</h5>"
        html += "<ul>"
        html += f"<li>σ<sub>11</sub> = {eigenvalues[0]:.3f} ppm</li>"
        html += f"<li>σ<sub>22</sub> = {eigenvalues[1]:.3f} ppm</li>"
        html += f"<li>σ<sub>33</sub> = {eigenvalues[2]:.3f} ppm</li>"
        html += "</ul>"

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
