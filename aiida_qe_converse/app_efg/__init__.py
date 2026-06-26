"""
EFG (electric field gradient) plugin for AiiDAlab-QE.

Mirrors the NMR Converse plugin but drives ``EfgWorkChain`` / ``qe-efg.x`` and
reports per-atom Vzz, eta, Cq and nu_Q instead of isotropic shielding.
"""
from aiidalab_qe.common.panel import PluginOutline
from .configuration.model import EFGConfigurationSettingsModel
from .configuration.view import EFGConfigurationSettingPanel
from .codes.mvc import (
    EFGResourceSettingsModel,
    EFGResourcesSettingsPanel,
)
from .results.view import EFGResultsPanel
from .results.model import EFGResultsModel
from .workchain import workchain_and_builder


class EFGPluginOutline(PluginOutline):
    """Outline for the EFG plugin."""

    title = "EFG"
    description = "Compute EFG tensors and NMR/NQR quadrupolar parameters (Cq, eta, nu_Q)"


property = {
    "outline": EFGPluginOutline,
    "configuration": {
        "panel": EFGConfigurationSettingPanel,
        "model": EFGConfigurationSettingsModel,
    },
    "resources": {
        "panel": EFGResourcesSettingsPanel,
        "model": EFGResourceSettingsModel,
    },
    "result": {
        "panel": EFGResultsPanel,
        "model": EFGResultsModel,
    },
    "workchain": workchain_and_builder,
}
