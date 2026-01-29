"""
Results model for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ResultsModel
from traitlets import List, Dict, Instance, observe
from aiida import orm
import numpy as np


class NMRResultsModel(ResultsModel):
    """Model for NMR Converse results."""

    identifier = "qeconverse"
    title = "NMR Chemical Shifts"

    _this_process_label = "NmrConverseWorkChain"

    # Results data
    isotropic_shielding = Dict(default_value={})
    chemical_shift_tensors = Dict(default_value={})
    atom_labels = List(default_value=[])
    structure = Instance(orm.StructureData, allow_none=True)

    # Table data for display
    table_data = List(default_value=[])

    def fetch_results(self):
        """Fetch results from workchain outputs."""
        print(f"[NMR DEBUG] fetch_results called")
        print(f"[NMR DEBUG] process_uuid: {self.process_uuid}")
        print(f"[NMR DEBUG] process: {self.process}")

        # Use the base class method to get outputs
        outputs = self._get_child_outputs()
        print(f"[NMR DEBUG] outputs from _get_child_outputs: {outputs}")

        if not outputs:
            print("[NMR DEBUG] No outputs, returning")
            return

        # Extract the workchain outputs
        self._update_isotropic_shielding(outputs)
        self._update_chemical_shift_tensors(outputs)
        self._update_structure()
        self._generate_table_data()

    def _update_isotropic_shielding(self, node):
        """Extract isotropic shielding values from workchain."""
        if "isotropic_shielding_ppm" not in node:
            self.isotropic_shielding = {}
            return

        iso_data = node.isotropic_shielding_ppm.get_dict()
        self.isotropic_shielding = iso_data
        self.atom_labels = list(iso_data.keys())

    def _update_chemical_shift_tensors(self, node):
        """Extract full chemical shift tensors from workchain."""
        if "absolute_shift_tensor_ppm" not in node:
            self.chemical_shift_tensors = {}
            return

        tensor_data = node.absolute_shift_tensor_ppm.get_dict()
        self.chemical_shift_tensors = tensor_data

    def _update_structure(self):
        """Extract structure from workchain inputs."""
        try:
            # Get the child process node
            child_node = self.fetch_child_process_node()
            if child_node and hasattr(child_node, 'inputs') and 'structure' in child_node.inputs:
                self.structure = child_node.inputs.structure
            else:
                self.structure = None
        except Exception:
            self.structure = None

    def _generate_table_data(self):
        """Generate table data for display."""
        if not self.isotropic_shielding or not self.chemical_shift_tensors:
            self.table_data = []
            return

        table_rows = []
        for atom_label in self.atom_labels:
            if atom_label not in self.isotropic_shielding:
                continue

            iso_value = self.isotropic_shielding[atom_label].get("isotropic_shielding_ppm", 0.0)

            # Compute tensor properties if available
            if atom_label in self.chemical_shift_tensors:
                tensor = np.array(self.chemical_shift_tensors[atom_label])

                # Compute anisotropy and asymmetry
                eigenvalues = np.linalg.eigvalsh(tensor)
                eigenvalues = np.sort(eigenvalues)[::-1]  # Sort descending

                # Anisotropy: δ = σ_zz - (σ_xx + σ_yy)/2
                # Using principal components: δ = σ_33 - (σ_11 + σ_22)/2
                anisotropy = eigenvalues[2] - (eigenvalues[0] + eigenvalues[1]) / 2

                # Asymmetry: η = (σ_yy - σ_xx) / (σ_zz - σ_iso)
                if abs(eigenvalues[2] - iso_value) > 1e-6:
                    asymmetry = (eigenvalues[1] - eigenvalues[0]) / (eigenvalues[2] - iso_value)
                else:
                    asymmetry = 0.0

                row = {
                    "Atom": atom_label,
                    "Isotropic (ppm)": f"{iso_value:.2f}",
                    "Anisotropy (ppm)": f"{anisotropy:.2f}",
                    "Asymmetry": f"{asymmetry:.3f}",
                    "σ₁₁ (ppm)": f"{eigenvalues[0]:.2f}",
                    "σ₂₂ (ppm)": f"{eigenvalues[1]:.2f}",
                    "σ₃₃ (ppm)": f"{eigenvalues[2]:.2f}",
                }
            else:
                row = {
                    "Atom": atom_label,
                    "Isotropic (ppm)": f"{iso_value:.2f}",
                }

            table_rows.append(row)

        self.table_data = table_rows

    def get_model_state(self):
        """Get the current state of the model."""
        return {
            "isotropic_shielding": self.isotropic_shielding,
            "chemical_shift_tensors": self.chemical_shift_tensors,
            "atom_labels": self.atom_labels,
        }

    def set_model_state(self, state):
        """Set the model state from a dictionary."""
        if "isotropic_shielding" in state:
            self.isotropic_shielding = state["isotropic_shielding"]
        if "chemical_shift_tensors" in state:
            self.chemical_shift_tensors = state["chemical_shift_tensors"]
        if "atom_labels" in state:
            self.atom_labels = state["atom_labels"]
