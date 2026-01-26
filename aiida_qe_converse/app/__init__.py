"""
NMR Converse plugin for AiiDAlab-QE.
"""
from aiidalab_qe.common.panel import PluginOutline
from .configuration.model import NMRConfigurationSettingsModel
from .configuration.view import NMRConfigurationSettingPanel
from .codes.mvc import (
    NMRResourceSettingsModel,
    NMRResourcesSettingsPanel,
)
from .results.view import NMRResultsPanel
from .results.model import NMRResultsModel
from .workchain import workchain_and_builder
from pathlib import Path


class NMRPluginOutline(PluginOutline):
    """Outline for NMR Converse plugin."""

    title = "NMR"
    description = "Compute NMR chemical shifts using the converse approach"


property = {
    "outline": NMRPluginOutline,
    "configuration": {
        "panel": NMRConfigurationSettingPanel,
        "model": NMRConfigurationSettingsModel,
    },
    # "resources": {
    #     "panel": NMRResourcesSettingsPanel,
    #     "model": NMRResourceSettingsModel,
    # },
    "result": {
        "panel": NMRResultsPanel,
        "model": NMRResultsModel,
    },
    "workchain": workchain_and_builder,
}
