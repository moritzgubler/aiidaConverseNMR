"""
Shared atom-selection configuration model and panel for aiidalab-qe plugins.

The per-atom "compute these sites" picker is identical for the NMR and EFG
plugins, so it lives here and both plugins subclass it (the NMR and EFG models
add their own extra traits; the EFG panel adds the Q/I override widget on top).
"""
import ipywidgets as ipw
from aiidalab_qe.common.panel import ConfigurationSettingsModel, ConfigurationSettingsPanel
from aiidalab_qe.common.mixins import HasInputStructure
from traitlets import List, Dict, observe


class AtomSelectionConfigModel(ConfigurationSettingsModel, HasInputStructure):
    """Configuration model holding a per-site selection over the structure."""

    dependencies = [
        "input_structure",
    ]

    # List of selected atom indices (0-based).
    target_atoms = List([])
    # Mapping atom index -> selection state, e.g. {0: True, 1: False, ...}.
    atom_selection = Dict({})
    # [(index, element, kind_name), ...]
    atom_info = List([])

    @observe("input_structure")
    def _on_input_structure_change(self, change):
        """Rebuild the atom list when the structure changes."""
        structure = change.get("new") if isinstance(change, dict) else change["new"]

        if structure is None:
            self.atom_info = []
            self.atom_selection = {}
            self.target_atoms = []
            return

        atom_list = []
        for idx, site in enumerate(structure.sites):
            atom_list.append((idx, site.kind_name, site.kind_name))
        self.atom_info = atom_list

        self.atom_selection = {idx: True for idx in range(len(structure.sites))}
        self._update_target_atoms()

    @observe("atom_selection")
    def _on_atom_selection_change(self, _):
        self._update_target_atoms()

    def _update_target_atoms(self):
        self.target_atoms = [idx for idx, selected in self.atom_selection.items() if selected]

    def get_model_state(self):
        return {
            k: getattr(self, k) for k, v in self.traits().items()
            if k != "input_structure"
        }

    def set_model_state(self, parameters):
        for key, value in parameters.items():
            if key in self.traits():
                self.set_trait(key, value)

    def reset(self):
        if self.input_structure is not None:
            self.atom_selection = {idx: True for idx in range(len(self.input_structure.sites))}
        else:
            self.atom_selection = {}
            self.target_atoms = []


class AtomSelectionConfigPanel(ConfigurationSettingsPanel):
    """Panel rendering the scrollable per-atom selection table + select-all buttons."""

    def __init__(self, model, **kwargs):
        super().__init__(model, **kwargs)
        self._atom_checkboxes = {}

    def _render_atom_selection(self):
        """Render the atom-selection interface (returns a VBox)."""
        header = ipw.HTML("<h4>Atom Selection</h4>")

        self.atom_list_container = ipw.VBox()
        self._model.observe(self._update_atom_list, "atom_info")
        self._update_atom_list(None)

        select_all_btn = ipw.Button(description="Select All", button_style="info",
                                    layout=ipw.Layout(width="120px"))
        deselect_all_btn = ipw.Button(description="Deselect All", button_style="warning",
                                      layout=ipw.Layout(width="120px"))
        select_all_btn.on_click(lambda _: self._select_all_atoms(True))
        deselect_all_btn.on_click(lambda _: self._select_all_atoms(False))
        button_row = ipw.HBox([select_all_btn, deselect_all_btn],
                              layout=ipw.Layout(margin="10px 0"))

        self.selection_summary = ipw.HTML()
        self._model.observe(self._update_selection_summary, "target_atoms")
        self._update_selection_summary(None)

        return ipw.VBox([header, button_row, self.atom_list_container, self.selection_summary])

    def _update_atom_list(self, _):
        """Rebuild the checkbox rows from the model's atom_info."""
        self._atom_checkboxes.clear()

        if not self._model.atom_info:
            self.atom_list_container.children = [ipw.HTML("<p><i>Loading structure...</i></p>")]
            return

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

        checkbox_rows = []
        for idx, element, kind_name in self._model.atom_info:
            checkbox = ipw.Checkbox(
                value=self._model.atom_selection.get(idx, True),
                indent=False,
                layout=ipw.Layout(width="auto", margin="0"),
            )
            checkbox.observe(
                lambda change, atom_idx=idx: self._on_checkbox_change(atom_idx, change),
                "value",
            )
            self._atom_checkboxes[idx] = checkbox

            bg_color = "#f5f5f5" if idx % 2 == 0 else "white"
            row_html = ipw.HTML(
                f"""<div style='display: flex; align-items: center; background: {bg_color}; border-bottom: 1px solid #eee;'>
                    <div style='width: 80px; text-align: center; padding: 8px;'>{idx+1}</div>
                    <div style='flex: 1; padding: 8px;'>{element}</div>
                </div>""",
                layout=ipw.Layout(flex="1 1 auto")
            )
            checkbox_cell = ipw.HBox([checkbox],
                                     layout=ipw.Layout(width="100px", justify_content="center",
                                                       padding="4px 0"))
            row = ipw.HBox([row_html, checkbox_cell],
                           layout=ipw.Layout(align_items="stretch", width="100%"))
            row.add_class("atom-row-even" if idx % 2 == 0 else "atom-row-odd")
            checkbox_rows.append(row)

        css_style = ipw.HTML("""
            <style>
                .atom-row-even > .widget-hbox { background: #f5f5f5; }
                .atom-row-odd > .widget-hbox { background: white; }
            </style>
        """)

        scrollable_output = ipw.Output(
            layout=ipw.Layout(height="250px", overflow_y="scroll", border="1px solid #ddd")
        )
        rows_vbox = ipw.VBox(checkbox_rows)
        with scrollable_output:
            from IPython.display import display
            display(rows_vbox)

        self.atom_list_container.children = [css_style, header_widget, scrollable_output]

    def _on_checkbox_change(self, atom_idx, change):
        new_selection = self._model.atom_selection.copy()
        new_selection[atom_idx] = change["new"]
        self._model.atom_selection = new_selection

    def _select_all_atoms(self, select: bool):
        new_selection = {idx: select for idx in range(len(self._model.atom_info))}
        self._model.atom_selection = new_selection
        for idx, checkbox in self._atom_checkboxes.items():
            checkbox.value = select

    def _update_selection_summary(self, _):
        num_selected = len(self._model.target_atoms)
        num_total = len(self._model.atom_info)
        if num_selected == num_total:
            msg = f"<p style='color: #28a745; margin-top: 10px;'><strong>All {num_total} atoms selected</strong></p>"
        elif num_selected == 0:
            msg = "<p style='color: #dc3545; margin-top: 10px;'><strong>No atoms selected</strong></p>"
        else:
            msg = f"<p style='color: #007bff; margin-top: 10px;'><strong>{num_selected} of {num_total} atoms selected</strong></p>"
        self.selection_summary.value = msg
