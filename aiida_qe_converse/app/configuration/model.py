"""
Configuration model for NMR Converse plugin.

The per-atom selection logic lives in the shared
``app_common.atom_selection.AtomSelectionConfigModel`` (reused by the EFG
plugin); this subclass only sets the plugin identity.
"""
from ...app_common.atom_selection import AtomSelectionConfigModel


class NMRConfigurationSettingsModel(AtomSelectionConfigModel):
    """Model for NMR Converse configuration settings."""

    title = "NMR"
    identifier = "nmr_converse"
