"""
Results model for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ResultsModel
from traitlets import Bool, Unicode, List, Dict, Instance, observe
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
    target_atoms = List(default_value=[])
    atom_labels = List(default_value=[])
    structure = Instance(orm.StructureData, allow_none=True)

    # Table data for display
    table_data = List(default_value=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @observe("process_node")
    def _observe_process_node(self, _):
        """Update when process_node changes."""
        self.update()

    def update(self, specific=""):
        """Update results from workchain outputs."""
        if not hasattr(self, 'process_node') or self.process_node is None:
            return

        node = self._get_child_outputs()

        if not node:
            return

        # Extract the workchain outputs
        self._update_isotropic_shielding(node)
        self._update_chemical_shift_tensors(node)
        self._update_structure(node)
        self._generate_table_data()

    def _get_child_outputs(self):
        """Get the child workchain outputs."""
        if not hasattr(self, 'process_node') or self.process_node is None:
            return None

        try:
            # Check if process_node itself is the NmrConverseWorkChain
            if hasattr(self.process_node, 'process_label') and \
               self.process_node.process_label == self._this_process_label:
                return self.process_node.outputs

            # Check if it's a QeAppWorkChain with nested qeconverse outputs
            if hasattr(self.process_node, 'outputs') and 'qeconverse' in self.process_node.outputs:
                return self.process_node.outputs.qeconverse

            # Try to find the NmrConverseWorkChain as a called process
            qb = orm.QueryBuilder()
            qb.append(
                orm.WorkChainNode,
                filters={"id": self.process_node.pk},
                tag="base",
            )
            qb.append(
                orm.WorkChainNode,
                with_incoming="base",
                edge_filters={"type": "CALL"},
                filters={"attributes.process_label": self._this_process_label},
                project=["*"],
            )
            results = qb.all()

            if results:
                return results[0][0].outputs

        except Exception as e:
            import traceback
            print(f"Error getting child outputs: {e}")
            traceback.print_exc()

        return None

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

    def _update_structure(self, node):
        """Extract structure from workchain."""
        # Try to get the structure from the workchain inputs
        try:
            qb = orm.QueryBuilder()
            qb.append(
                orm.WorkChainNode,
                filters={"attributes.process_label": self._this_process_label},
                project=["*"],
                tag="wc",
            )
            qb.append(
                orm.StructureData,
                with_outgoing="wc",
                edge_filters={"label": "structure"},
                project=["*"],
            )
            results = qb.all()

            if results:
                self.structure = results[0][0]
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
