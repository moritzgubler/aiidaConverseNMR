"""
Configuration panel for the EFG plugin: GIPAW pseudo section (shared base)
plus a per-element Q / I override table seeded from the built-in nuclear-data
table. No per-atom selection — qe-efg.x computes all atoms in one cheap run.
"""
import ipywidgets as ipw

from ...app_common.atom_selection import AtomSelectionConfigPanel
from ...data.nuclear import default_q_i, DEFAULT_NUCLEAR_DATA
from .model import EFGConfigurationSettingsModel


class EFGConfigurationSettingPanel(AtomSelectionConfigPanel):
    """Panel for configuring EFG calculations."""

    title = "EFG"
    identifier = "qeefg"

    def __init__(self, model: EFGConfigurationSettingsModel, **kwargs):
        super().__init__(model, **kwargs)
        self._q_inputs = {}
        self._i_inputs = {}

    def render(self):
        """Render the configuration panel."""
        if (hasattr(self._model, 'input_structure') and
                self._model.input_structure is not None and
                not self._model.atom_info):
            self._model._on_input_structure_change({"new": self._model.input_structure})

        # No atom-selection UI: qe-efg.x computes the EFG tensor for all
        # atoms in a single run, so there is nothing to save by picking sites.
        pseudo_container = self._render_pseudo_section()
        nuclear_data_container = self._render_nuclear_data()

        # rebuild the Q/I table whenever the structure (atom_info) changes
        self._model.observe(lambda _: self._update_nuclear_table(), "atom_info")

        self.children = [
            pseudo_container,
            nuclear_data_container,
        ]

    def _structure_elements(self):
        """Distinct element symbols present in the current structure."""
        elements = []
        for _, element, _ in self._model.atom_info:
            if element not in elements:
                elements.append(element)
        return elements

    def _render_nuclear_data(self):
        """Render the editable per-element Q / I table."""
        header = ipw.HTML(
            "<h4>Nuclear quadrupole data</h4>"
            "<p>Q in units of 1e-30 m&sup2; (= 10 mbarn); I is the nuclear spin. "
            "Q = 0 skips C<sub>q</sub> for that element; &nu;<sub>Q</sub> needs I &ge; 1. "
            "Defaults are a representative isotope &mdash; override as needed.</p>"
        )
        self.nuclear_table_container = ipw.VBox()
        self._update_nuclear_table()
        return ipw.VBox([header, self.nuclear_table_container])

    def _update_nuclear_table(self):
        """(Re)build the Q/I widgets for the elements in the structure."""
        self._q_inputs.clear()
        self._i_inputs.clear()

        elements = self._structure_elements()
        if not elements:
            self.nuclear_table_container.children = [
                ipw.HTML("<p><i>Load a structure to edit nuclear data.</i></p>")
            ]
            return

        overrides = self._model.nuclear_data or {}
        rows = [ipw.HBox([
            ipw.HTML("<b>Element</b>", layout=ipw.Layout(width="100px")),
            ipw.HTML("<b>Isotope</b>", layout=ipw.Layout(width="90px")),
            ipw.HTML("<b>Q (1e-30 m&sup2;)</b>", layout=ipw.Layout(width="160px")),
            ipw.HTML("<b>I</b>", layout=ipw.Layout(width="120px")),
        ])]

        for element in elements:
            default_q, default_i = default_q_i(element)
            isotope = DEFAULT_NUCLEAR_DATA.get(element, ('-',))[0]
            ov = overrides.get(element, {})
            q_val = ov.get('Q', default_q)
            i_val = ov.get('I', default_i)

            q_input = ipw.FloatText(value=float(q_val), layout=ipw.Layout(width="150px"))
            i_input = ipw.FloatText(value=float(i_val), layout=ipw.Layout(width="110px"))
            q_input.observe(lambda _change, el=element: self._on_nuclear_change(el), "value")
            i_input.observe(lambda _change, el=element: self._on_nuclear_change(el), "value")
            self._q_inputs[element] = q_input
            self._i_inputs[element] = i_input

            rows.append(ipw.HBox([
                ipw.HTML(f"<div style='width:100px'>{element}</div>"),
                ipw.HTML(f"<div style='width:90px'>{isotope}</div>"),
                q_input,
                i_input,
            ]))

        self.nuclear_table_container.children = rows

    def _on_nuclear_change(self, element):
        """Write the current Q/I widgets back into the model override dict."""
        new_data = dict(self._model.nuclear_data)
        new_data[element] = {
            'Q': self._q_inputs[element].value,
            'I': self._i_inputs[element].value,
        }
        self._model.nuclear_data = new_data
