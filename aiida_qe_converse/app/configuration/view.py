"""
Configuration panel for NMR Converse plugin.

The atom-selection rendering is inherited from the shared
``app_common.atom_selection.AtomSelectionConfigPanel``.
"""
from ...app_common.atom_selection import AtomSelectionConfigPanel
from .model import NMRConfigurationSettingsModel


class NMRConfigurationSettingPanel(AtomSelectionConfigPanel):
    """Panel for configuring NMR Converse calculations."""

    title = "NMR"
    identifier = "nmr_converse"

    def render(self):
        """Render the configuration panel."""
        if (hasattr(self._model, 'input_structure') and
                self._model.input_structure is not None and
                not self._model.atom_info):
            self._model._on_input_structure_change({"new": self._model.input_structure})

        self.children = [
            self._render_atom_selection(),
        ]
