"""
Configuration panel for the EFG plugin: GIPAW pseudo section (shared base)
plus a per-element Q / I override table seeded from the built-in nuclear-data
table. No per-atom selection — qe-efg.x computes all atoms in one cheap run.
"""
import ipywidgets as ipw

from ...app_common.atom_selection import AtomSelectionConfigPanel
from ...data.nuclear import default_q_i, isotopes_for, isotope_entry
from .model import EFGConfigurationSettingsModel


class EFGConfigurationSettingPanel(AtomSelectionConfigPanel):
    """Panel for configuring EFG calculations."""

    title = "EFG"
    identifier = "qeefg"

    def __init__(self, model: EFGConfigurationSettingsModel, **kwargs):
        super().__init__(model, **kwargs)
        self._q_inputs = {}
        self._i_inputs = {}
        self._iso_dropdowns = {}
        # guards the Q/I <-> isotope-dropdown observers against feedback loops
        self._nuc_syncing = False

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
            "Pick the isotope of interest, or choose <i>custom</i> and enter "
            "Q / I by hand.</p>"
            "<p style='font-size:0.9em;color:#666;'>Isotope data: "
            "Q from P. Pyykk&ouml;, <i>Year-2017 nuclear quadrupole moments</i>, "
            "Mol. Phys. 116, 1328 (2018), "
            "<a href='https://doi.org/10.1080/00268976.2018.1426131' "
            "target='_blank'>doi:10.1080/00268976.2018.1426131</a>; "
            "spins I from R. K. Harris et al., <i>NMR nomenclature</i> "
            "(IUPAC Recommendations 2001), Pure Appl. Chem. 73, 1795 (2001), "
            "<a href='https://doi.org/10.1351/pac200173111795' "
            "target='_blank'>doi:10.1351/pac200173111795</a>.</p>"
        )
        self.nuclear_table_container = ipw.VBox()
        self._update_nuclear_table()
        return ipw.VBox([header, self.nuclear_table_container])

    def _update_nuclear_table(self):
        """(Re)build the isotope/Q/I widgets for the elements in the structure."""
        self._q_inputs.clear()
        self._i_inputs.clear()
        self._iso_dropdowns.clear()

        elements = self._structure_elements()
        if not elements:
            self.nuclear_table_container.children = [
                ipw.HTML("<p><i>Load a structure to edit nuclear data.</i></p>")
            ]
            return

        overrides = self._model.nuclear_data or {}
        rows = [ipw.HBox([
            ipw.HTML("<b>Element</b>", layout=ipw.Layout(width="100px")),
            ipw.HTML("<b>Isotope</b>", layout=ipw.Layout(width="110px")),
            ipw.HTML("<b>Q (1e-30 m&sup2;)</b>", layout=ipw.Layout(width="160px")),
            ipw.HTML("<b>I</b>", layout=ipw.Layout(width="120px")),
        ])]

        for element in elements:
            default_q, default_i = default_q_i(element)
            ov = overrides.get(element, {})
            q_val = float(ov.get('Q', default_q))
            i_val = float(ov.get('I', default_i))

            options = [entry[0] for entry in isotopes_for(element)] + ["custom"]
            selected = ov.get('isotope')
            if selected not in options:
                selected = self._matching_isotope(element, q_val, i_val) or "custom"

            iso_dd = ipw.Dropdown(options=options, value=selected,
                                  layout=ipw.Layout(width="100px"))
            q_input = ipw.FloatText(value=q_val, layout=ipw.Layout(width="150px"))
            i_input = ipw.FloatText(value=i_val, layout=ipw.Layout(width="110px"))
            iso_dd.observe(lambda _change, el=element: self._on_isotope_change(el), "value")
            q_input.observe(lambda _change, el=element: self._on_nuclear_change(el), "value")
            i_input.observe(lambda _change, el=element: self._on_nuclear_change(el), "value")
            self._iso_dropdowns[element] = iso_dd
            self._q_inputs[element] = q_input
            self._i_inputs[element] = i_input

            rows.append(ipw.HBox([
                ipw.HTML(f"<div style='width:100px'>{element}</div>"),
                ipw.HBox([iso_dd], layout=ipw.Layout(width="110px")),
                q_input,
                i_input,
            ]))

        self.nuclear_table_container.children = rows

    @staticmethod
    def _matching_isotope(element, q_val, i_val):
        """Isotope label whose (Q, I) match the given values, or None."""
        for label, spin, quad, _gamma in isotopes_for(element):
            if abs(q_val - quad) < 1e-6 and abs(i_val - spin) < 1e-6:
                return label
        return None

    def _on_isotope_change(self, element):
        """User picked an isotope: seed Q/I from the table (custom = keep values)."""
        if self._nuc_syncing:
            return
        entry = isotope_entry(element, self._iso_dropdowns[element].value)
        if entry is not None:
            _label, spin, quad, _gamma = entry
            self._nuc_syncing = True
            try:
                self._q_inputs[element].value = float(quad)
                self._i_inputs[element].value = float(spin)
            finally:
                self._nuc_syncing = False
        self._store_nuclear(element)

    def _on_nuclear_change(self, element):
        """User edited Q or I by hand: flag 'custom' if it left the isotope values."""
        if self._nuc_syncing:
            return
        dd = self._iso_dropdowns.get(element)
        if dd is not None and dd.value != "custom":
            entry = isotope_entry(element, dd.value)
            if entry is None or (abs(self._q_inputs[element].value - entry[2]) > 1e-6
                                 or abs(self._i_inputs[element].value - entry[1]) > 1e-6):
                self._nuc_syncing = True
                try:
                    dd.value = "custom"
                finally:
                    self._nuc_syncing = False
        self._store_nuclear(element)

    def _store_nuclear(self, element):
        """Write the current isotope/Q/I widgets back into the model override dict."""
        new_data = dict(self._model.nuclear_data)
        new_data[element] = {
            'Q': self._q_inputs[element].value,
            'I': self._i_inputs[element].value,
            'isotope': self._iso_dropdowns[element].value,
        }
        self._model.nuclear_data = new_data
