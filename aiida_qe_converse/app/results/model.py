"""
Results model for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ResultsModel
from traitlets import Bool, Unicode, List, Dict, observe


class NMRResultsModel(ResultsModel):
    """Model for NMR Converse results."""

    identifier = "nmr_converse"
    title = "NMR Chemical Shifts"
    workchain_labels = ["nmr_converse"]

    # Results data
    isotropic_shielding = Dict({})
    chemical_shift_tensors = Dict({})
    target_atoms = List([])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update(self, specific=""):
        """Update results from workchain outputs."""
        pass

    def _update_isotropic_shielding(self):
        """Extract isotropic shielding values from workchain."""
        pass

    def _update_chemical_shift_tensors(self):
        """Extract full chemical shift tensors from workchain."""
        pass

    def get_model_state(self):
        """Get the current state of the model."""
        return {}

    def set_model_state(self, state):
        """Set the model state from a dictionary."""
        pass
