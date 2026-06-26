"""Resource settings for the EFG plugin (pw.x + qe-efg.x)."""
from aiidalab_qe.common.panel import PluginResourceSettingsModel, PluginResourceSettingsPanel
from aiidalab_qe.common.code.model import PwCodeModel, CodeModel


class EFGResourceSettingsModel(PluginResourceSettingsModel):
    """Resource settings for EFG calculations."""

    title = "EFG Resources"
    identifier = "qeefg"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add_models(
            {
                "pw_efg": PwCodeModel(
                    description="pw.x for the EFG SCF calculation",
                    default_calc_job_plugin="quantumespresso.pw",
                ),
                "qeefg": CodeModel(
                    name="qe-efg.x",
                    description="qe-efg.x for the EFG tensor calculation",
                    default_calc_job_plugin="qeefg",
                ),
            },
        )


class EFGResourcesSettingsPanel(PluginResourceSettingsPanel[EFGResourceSettingsModel]):
    """Panel for the EFG resource settings."""

    title = "EFG"
