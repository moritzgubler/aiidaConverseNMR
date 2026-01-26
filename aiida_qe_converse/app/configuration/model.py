"""
Configuration model for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ConfigurationSettingsModel
from aiidalab_qe.common.mixins import HasInputStructure
from traitlets import Bool, Float, Int, List, Unicode, Dict, observe


class NMRConfigurationSettingsModel(ConfigurationSettingsModel, HasInputStructure):
    """Model for NMR Converse configuration settings."""

    title = "NMR"
    identifier = "nmr_converse"

    # Dependencies - tells framework to link these from the app
    dependencies = [
        "input_structure",
    ]

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
    # List of atom indices (0-based) for which to compute chemical shifts
    target_atoms = List([])

    # Dictionary mapping atom index to selection state
    # Format: {0: True, 1: False, 2: True, ...}
    atom_selection = Dict({})

    # Information about atoms in the structure
    # Format: [(index, element, kind_name), ...]
    atom_info = List([])

    # Symmetry settings (must be disabled for NMR)
    nosym = Bool(True)
    noinv = Bool(True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @observe("input_structure")
    def _on_input_structure_change(self, change):
        """Handle changes to input structure."""
        structure = change.get("new") if isinstance(change, dict) else change["new"]

        if structure is None:
            self.atom_info = []
            self.atom_selection = {}
            self.target_atoms = []
            return

        # Build atom information list
        atom_list = []
        for idx, site in enumerate(structure.sites):
            element = site.kind_name
            atom_list.append((idx, element, site.kind_name))

        self.atom_info = atom_list

        # Initialize all atoms as selected by default
        self.atom_selection = {idx: True for idx in range(len(structure.sites))}

        # Update target atoms list
        self._update_target_atoms()

    @observe("atom_selection")
    def _on_atom_selection_change(self, _):
        """Update target_atoms when selection changes."""
        self._update_target_atoms()

    def _update_target_atoms(self):
        """Update the target_atoms list based on atom_selection."""
        self.target_atoms = [
            idx for idx, selected in self.atom_selection.items() if selected
        ]

    def get_model_state(self):
        """Get the current state of the model."""
        return {
            "protocol": self.protocol,
            "compute_nmr": self.compute_nmr,
            "kpoints_distance": self.kpoints_distance,
            "ecutwfc": self.ecutwfc,
            "conv_thr": self.conv_thr,
            "mixing_beta": self.mixing_beta,
            "q_gipaw": self.q_gipaw,
            "dudk_method": self.dudk_method,
            "atom_selection": self.atom_selection,
            "target_atoms": self.target_atoms,
        }

    def set_model_state(self, state):
        """Set the model state from a dictionary."""
        self.protocol = state.get("protocol", "moderate")
        self.compute_nmr = state.get("compute_nmr", True)
        self.kpoints_distance = state.get("kpoints_distance", 0.25)
        self.ecutwfc = state.get("ecutwfc", 90.0)
        self.conv_thr = state.get("conv_thr", 1.0e-10)
        self.mixing_beta = state.get("mixing_beta", 0.4)
        self.q_gipaw = state.get("q_gipaw", 0.01)
        self.dudk_method = state.get("dudk_method", "covariant")
        self.atom_selection = state.get("atom_selection", {})
        self.target_atoms = state.get("target_atoms", [])

    def reset(self):
        """Reset model to default values."""
        self.protocol = "moderate"
        self.compute_nmr = True
        self.kpoints_distance = 0.25
        self.ecutwfc = 90.0
        self.conv_thr = 1.0e-10
        self.mixing_beta = 0.4
        self.q_gipaw = 0.01
        self.dudk_method = "covariant"
        # Reselect all atoms
        if self.input_structure is not None:
            self.atom_selection = {idx: True for idx in range(len(self.input_structure.sites))}
        else:
            self.atom_selection = {}
            self.target_atoms = []
