"""
Configuration model for the EFG plugin.

Subclasses the shared atom-selection model for its structure tracking
(``atom_info``) and ``pseudo_family`` traits, and adds a ``nuclear_data``
override trait (per-element Q in 1e-30 m^2 and spin I). The per-atom
selection itself is not exposed: qe-efg.x computes all atoms in one run.
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

    def get_model_state(self):
        # No atom selection for EFG: qe-efg.x always computes all atoms, so
        # target_atoms/atom_selection are deliberately not serialized (the
        # workchain treats a missing target_atoms as "all atoms").
        return {
            "pseudo_family": self.pseudo_family,
            "nuclear_data": self.nuclear_data,
        }

    def set_model_state(self, parameters):
        super().set_model_state(parameters)
        if "nuclear_data" in parameters:
            self.nuclear_data = parameters["nuclear_data"]
