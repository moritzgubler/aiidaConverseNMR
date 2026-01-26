"""
Configuration model for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ConfigurationSettingsModel
from aiidalab_qe.common.mixins import HasInputStructure
from traitlets import Bool, Float, Int, List, Unicode, observe


class NMRConfigurationSettingsModel(ConfigurationSettingsModel, HasInputStructure):
    """Model for NMR Converse configuration settings."""

    title = "NMR"
    identifier = "nmr_converse"

    # Protocol settings
    protocol = Unicode("moderate")

    # Calculation flags
    compute_nmr = Bool(True)

    # NMR-specific parameters
    kpoints_distance = Float(0.25)
    ecutwfc = Float(90.0)
    conv_thr = Float(1.0e-10)
    mixing_beta = Float(0.4)
    q_gipaw = Float(0.01)
    dudk_method = Unicode("covariant")

    # Target atoms for NMR calculation
    target_atoms = List([])

    # Symmetry settings (must be disabled for NMR)
    nosym = Bool(True)
    noinv = Bool(True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @observe("input_structure")
    def _on_input_structure_change(self, _):
        """Handle changes to input structure."""
        pass

    def get_model_state(self):
        """Get the current state of the model."""
        return {}

    def set_model_state(self, state):
        """Set the model state from a dictionary."""
        pass

    def reset(self):
        """Reset model to default values."""
        pass
