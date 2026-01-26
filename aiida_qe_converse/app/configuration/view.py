"""
Configuration panel for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ConfigurationSettingsPanel
from .model import NMRConfigurationSettingsModel


class NMRConfigurationSettingPanel(ConfigurationSettingsPanel[NMRConfigurationSettingsModel]):
    """Panel for configuring NMR Converse calculations."""

    title = "NMR"
    identifier = "nmr_converse"

    def __init__(self, model: NMRConfigurationSettingsModel, **kwargs):
        super().__init__(model, **kwargs)

    def render(self):
        """Render the configuration panel."""
        pass
