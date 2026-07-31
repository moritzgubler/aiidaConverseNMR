"""
Shared atom-selection configuration model and panel for aiidalab-qe plugins.

The per-atom "compute these sites" picker is identical for the NMR and EFG
plugins, so it lives here and both plugins subclass it (the NMR and EFG models
add their own extra traits; the EFG panel adds the Q/I override widget on top).
"""
import ipywidgets as ipw
from aiidalab_qe.common.panel import ConfigurationSettingsModel, ConfigurationSettingsPanel
from aiidalab_qe.common.mixins import HasInputStructure
from traitlets import List, Dict, Unicode, observe


class AtomSelectionConfigModel(ConfigurationSettingsModel, HasInputStructure):
    """Configuration model holding a per-site selection over the structure."""

    # In current aiidalab-qe, ``HasInputStructure`` exposes the *trait*
    # ``structure_uuid`` (``input_structure`` is a derived property). The
    # dependency system dlinks traits, so we depend on / observe
    # ``structure_uuid`` and resolve the node via the ``input_structure``
    # property.
    dependencies = [
        "structure_uuid",
    ]

    # List of selected atom indices (0-based).
    target_atoms = List([])
    # Mapping atom index -> selection state, e.g. {0: True, 1: False, ...}.
    atom_selection = Dict({})
    # [(index, element, kind_name), ...]
    atom_info = List([])
    # GIPAW pseudopotential library/functional (group label). EFG/NMR require
    # GIPAW pseudos, so the standard aiidalab-qe pseudo selection is not used.
    pseudo_family = Unicode("gipaw_PBE")

    @observe("structure_uuid")
    def _on_input_structure_change(self, change=None):
        """Rebuild the atom list when the structure changes."""
        structure = self.input_structure

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
        # Only the plugin's own selection traits; structure_uuid/locked/blockers
        # are framework-managed and must not be part of the saved state.
        return {
            k: getattr(self, k)
            for k in ("target_atoms", "atom_selection", "atom_info", "pseudo_family")
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

    # ---------------- GIPAW pseudopotential selection ----------------

    def _render_pseudo_section(self):
        """Render the GIPAW pseudopotential note + library selector + preview."""
        from ..workflows.common import list_gipaw_pseudo_families

        note = ipw.HTML(
            "<h4>Pseudopotentials (GIPAW)</h4>"
            "<p>EFG / NMR calculations <b>require GIPAW</b> norm-conserving "
            "pseudopotentials (with reconstruction data). The pseudopotential "
            "family chosen in the <i>Advanced</i> step is <b>not used</b> here — "
            "the GIPAW library selected below is used instead.</p>"
        )

        families = list_gipaw_pseudo_families() or ["gipaw_PBE", "gipaw_PBEsol"]
        labels = {"gipaw_PBE": "GIPAW PBE (gipaw_PBE)",
                  "gipaw_PBEsol": "GIPAW PBEsol (gipaw_PBEsol)"}
        options = [(labels.get(f, f), f) for f in families]
        current = self._model.pseudo_family if self._model.pseudo_family in families else families[0]

        self._pseudo_family_dd = ipw.Dropdown(
            options=options, value=current, description="GIPAW library:",
            style={"description_width": "120px"})
        ipw.link((self._pseudo_family_dd, "value"), (self._model, "pseudo_family"))

        self._pseudo_preview = ipw.HTML()
        self._pseudo_family_dd.observe(lambda c: self._update_pseudo_preview(), "value")
        self._model.observe(lambda c: self._update_pseudo_preview(), "atom_info")
        self._update_pseudo_preview()

        return ipw.VBox([note, self._pseudo_family_dd, self._pseudo_preview])

    def _update_pseudo_preview(self):
        """Show which GIPAW pseudo each element resolves to (or flag missing)."""
        structure = getattr(self._model, "input_structure", None)
        if structure is None:
            self._pseudo_preview.value = "<p><i>Load a structure to preview pseudopotentials.</i></p>"
            return
        from ..workflows.common import pseudo_status
        try:
            status = pseudo_status(structure, self._pseudo_family_dd.value)
        except Exception as exc:  # pragma: no cover - depends on AiiDA profile
            self._pseudo_preview.value = (
                f"<p style='color:#dc3545;'>Could not query pseudopotentials: {exc}</p>")
            return

        rows = ""
        missing = []
        for element, filename in status.items():
            if filename:
                cell = f"<span style='color:#28a745;'>{filename}</span>"
            else:
                cell = "<span style='color:#dc3545;font-weight:bold;'>MISSING</span>"
                missing.append(element)
            rows += (f"<tr><td style='padding:4px 12px;border:1px solid #eee;'>{element}</td>"
                     f"<td style='padding:4px 12px;border:1px solid #eee;'>{cell}</td></tr>")
        html = ("<table style='border-collapse:collapse;margin-top:6px;'>"
                "<tr style='background:#f0f0f0;'>"
                "<th style='padding:4px 12px;border:1px solid #eee;'>Element</th>"
                "<th style='padding:4px 12px;border:1px solid #eee;'>GIPAW pseudo</th></tr>"
                + rows + "</table>")
        if missing:
            html += (f"<p style='color:#dc3545;margin-top:6px;'><b>No GIPAW pseudopotential "
                     f"for: {', '.join(missing)}</b> in '{self._pseudo_family_dd.value}'. "
                     f"The calculation will fail until these are provided.</p>")
        self._pseudo_preview.value = html
