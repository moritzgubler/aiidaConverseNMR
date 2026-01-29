"""
Configuration panel for NMR Converse plugin.
"""
import ipywidgets as ipw
from aiidalab_qe.common.panel import ConfigurationSettingsPanel
from .model import NMRConfigurationSettingsModel


class NMRConfigurationSettingPanel(ConfigurationSettingsPanel[NMRConfigurationSettingsModel]):
    """Panel for configuring NMR Converse calculations."""

    title = "NMR"
    identifier = "nmr_converse"

    def __init__(self, model: NMRConfigurationSettingsModel, **kwargs):
        super().__init__(model, **kwargs)
        self._atom_checkboxes = {}

    def render(self):
        """Render the configuration panel."""
        # If structure exists but atom_info is empty, manually trigger processing
        if (hasattr(self._model, 'input_structure') and
            self._model.input_structure is not None and
            not self._model.atom_info):
            self._model._on_input_structure_change({"new": self._model.input_structure})

        # Atom selection section
        atom_selection_container = self._render_atom_selection()

        # Assemble the panel
        self.children = [
            atom_selection_container,
        ]

    def _render_atom_selection(self):
        """Render the atom selection interface."""
        header = ipw.HTML("<h4>Atom Selection</h4>")

        # Create container for atom checkboxes
        self.atom_list_container = ipw.VBox()

        # Update atom list when model changes
        self._model.observe(self._update_atom_list, "atom_info")

        # Initial render
        self._update_atom_list(None)

        # Select all / Deselect all buttons
        select_all_btn = ipw.Button(
            description="Select All",
            button_style="info",
            layout=ipw.Layout(width="120px"),
        )
        deselect_all_btn = ipw.Button(
            description="Deselect All",
            button_style="warning",
            layout=ipw.Layout(width="120px"),
        )

        select_all_btn.on_click(lambda _: self._select_all_atoms(True))
        deselect_all_btn.on_click(lambda _: self._select_all_atoms(False))

        button_row = ipw.HBox(
            [select_all_btn, deselect_all_btn],
            layout=ipw.Layout(margin="10px 0"),
        )

        # Selection summary
        self.selection_summary = ipw.HTML()
        self._model.observe(self._update_selection_summary, "target_atoms")
        self._update_selection_summary(None)

        return ipw.VBox([header, button_row, self.atom_list_container, self.selection_summary])

    def _update_atom_list(self, _):
        """Update the list of atom checkboxes based on the model."""
        self._atom_checkboxes.clear()

        # Check if atom_info is populated
        if not self._model.atom_info:
            self.atom_list_container.children = [
                ipw.HTML("<p><i>Loading structure...</i></p>")
            ]
            return

        # Create table header
        header_html = """
        <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
            <thead>
                <tr style="background-color: #f0f0f0; border-bottom: 2px solid #ddd;">
                    <th style="padding: 8px; text-align: center; width: 80px;">Index</th>
                    <th style="padding: 8px; text-align: left;">Element</th>
                    <th style="padding: 8px; text-align: center; width: 100px;">Compute</th>
                </tr>
            </thead>
        </table>
        """
        header_widget = ipw.HTML(header_html)

        # Create checkbox rows using GridBox for cleaner layout
        checkbox_rows = []
        for idx, element, kind_name in self._model.atom_info:
            # Create checkbox
            checkbox = ipw.Checkbox(
                value=self._model.atom_selection.get(idx, True),
                indent=False,
                layout=ipw.Layout(width="auto", margin="0"),
            )

            # Link checkbox to model
            checkbox.observe(
                lambda change, atom_idx=idx: self._on_checkbox_change(atom_idx, change),
                "value",
            )

            self._atom_checkboxes[idx] = checkbox

            # Create row using HBox with overflow hidden
            index_widget = ipw.HTML(
                f"<div style='width: 80px; text-align: center; padding: 8px;'>{idx+1}</div>",
                layout=ipw.Layout(width="80px", flex="0 0 auto")
            )

            element_widget = ipw.HTML(
                f"<div style='padding: 8px;'>{element}</div>",
                layout=ipw.Layout(flex="1 1 auto")
            )

            checkbox_widget = ipw.Box(
                [checkbox],
                layout=ipw.Layout(
                    width="100px",
                    flex="0 0 auto",
                    display="flex",
                    justify_content="center",
                    align_items="center",
                ),
            )

            row = ipw.HBox(
                [index_widget, element_widget, checkbox_widget],
                layout=ipw.Layout(
                    border_bottom="1px solid #eee",
                    align_items="center",
                    width="100%",
                    overflow="hidden",
                ),
            )
            checkbox_rows.append(row)

        # Combine header and rows
        self.atom_list_container.children = [
            header_widget,
            ipw.VBox(
                checkbox_rows,
                layout=ipw.Layout(
                    max_height="300px",
                    overflow_y="auto",
                    overflow_x="hidden",
                    border="1px solid #ddd",
                    padding="5px",
                ),
            ),
        ]

    def _on_checkbox_change(self, atom_idx, change):
        """Handle checkbox state change."""
        new_selection = self._model.atom_selection.copy()
        new_selection[atom_idx] = change["new"]
        self._model.atom_selection = new_selection

    def _select_all_atoms(self, select: bool):
        """Select or deselect all atoms."""
        new_selection = {idx: select for idx in range(len(self._model.atom_info))}
        self._model.atom_selection = new_selection

        # Update checkbox widgets
        for idx, checkbox in self._atom_checkboxes.items():
            checkbox.value = select

    def _update_selection_summary(self, _):
        """Update the selection summary display."""
        num_selected = len(self._model.target_atoms)
        num_total = len(self._model.atom_info)

        if num_selected == num_total:
            msg = f"<p style='color: #28a745; margin-top: 10px;'><strong>All {num_total} atoms selected</strong></p>"
        elif num_selected == 0:
            msg = "<p style='color: #dc3545; margin-top: 10px;'><strong>No atoms selected</strong></p>"
        else:
            msg = f"<p style='color: #007bff; margin-top: 10px;'><strong>{num_selected} of {num_total} atoms selected</strong></p>"

        self.selection_summary.value = msg

