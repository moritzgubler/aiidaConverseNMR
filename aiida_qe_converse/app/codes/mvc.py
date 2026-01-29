"""
Resource settings for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import PluginResourceSettingsModel, PluginResourceSettingsPanel
from aiidalab_qe.common.code.model import PwCodeModel, CodeModel


class NMRResourceSettingsModel(PluginResourceSettingsModel):
    """Resource settings for NMR Converse calculations."""

    title = "NMR Resources"
    identifier = "nmr_converse"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.add_models(
            {
                "pw_nmr": PwCodeModel(
                    description="pw.x for NMR SCF calculation",
                    default_calc_job_plugin="quantumespresso.pw",
                ),
                "qeconverse": CodeModel(
                    name="qe-converse.x",
                    description="qe-converse.x for chemical shift calculation",
                    default_calc_job_plugin="qeconverse",
                ),
            },
        )


class NMRResourcesSettingsPanel(PluginResourceSettingsPanel[NMRResourceSettingsModel]):
    """Panel for the resource settings for NMR Converse calculations."""

    title = "NMR"
