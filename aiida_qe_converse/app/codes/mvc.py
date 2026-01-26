"""
Resource settings for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import PluginResourceSettingsModel, PluginResourceSettingsPanel
from aiidalab_qe.common.code.model import PwCodeModel, CodeModel


class NMRResourceSettingsModel(PluginResourceSettingsModel):
    """Model for NMR Converse resource settings."""

    identifier = "nmr_converse"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Code for pw.x (SCF calculation)
        self.add_code_model(
            "pw_nmr",
            PwCodeModel(
                name="pw_nmr",
                description="pw.x for NMR SCF calculation",
                default_calc_job_plugin="quantumespresso.pw",
            ),
        )

        # Code for qe-converse.x (chemical shift calculation)
        self.add_code_model(
            "qeconverse",
            CodeModel(
                name="qeconverse",
                description="qe-converse.x for chemical shift calculation",
                default_calc_job_plugin="qeconverse.qeconverse",
            ),
        )

    def get_model_state(self):
        """Get the current state of the model."""
        return {}

    def set_model_state(self, state):
        """Set the model state from a dictionary."""
        pass


class NMRResourcesSettingsPanel(PluginResourceSettingsPanel[NMRResourceSettingsModel]):
    """Panel for NMR Converse resource settings."""

    title = "NMR"

    def __init__(self, model: NMRResourceSettingsModel, **kwargs):
        super().__init__(model, **kwargs)

    def render(self):
        """Render the resource settings panel."""
        pass
