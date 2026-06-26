"""
Configuration model for the EFG plugin.

Reuses the shared per-atom selection model and adds a ``nuclear_data`` override
trait (per-element Q in 1e-30 m^2 and spin I).
"""
from traitlets import Dict

from ...app_common.atom_selection import AtomSelectionConfigModel


class EFGConfigurationSettingsModel(AtomSelectionConfigModel):
    """Model for EFG configuration settings."""

    title = "EFG"
    identifier = "qeefg"

    # Per-element override of the nuclear quadrupole moment Q (1e-30 m^2) and
    # spin I, e.g. {"O": {"Q": -2.558, "I": 2.5}}. Empty -> use built-in table.
    nuclear_data = Dict({})
