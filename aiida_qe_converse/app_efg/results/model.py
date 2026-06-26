"""Results model for the EFG plugin."""
from aiidalab_qe.common.panel import ResultsModel
from traitlets import List, Dict, Instance
from aiida import orm


class EFGResultsModel(ResultsModel):
    """Model for EFG results."""

    identifier = "qeefg"
    title = "EFG / Quadrupolar Parameters"

    _this_process_label = "EfgWorkChain"

    efg_tensors = Dict(default_value={})
    quadrupolar_parameters = Dict(default_value={})
    atom_labels = List(default_value=[])
    structure = Instance(orm.StructureData, allow_none=True)
    table_data = List(default_value=[])

    def fetch_results(self):
        """Fetch results from the workchain outputs."""
        outputs = self._get_child_outputs()
        if not outputs:
            return

        self._update_quadrupolar(outputs)
        self._update_tensors(outputs)
        self._update_structure()
        self._generate_table_data()

    def _update_quadrupolar(self, node):
        if "quadrupolar_parameters" not in node:
            self.quadrupolar_parameters = {}
            return
        data = node.quadrupolar_parameters.get_dict()
        self.quadrupolar_parameters = data
        self.atom_labels = list(data.keys())

    def _update_tensors(self, node):
        if "efg_tensors" not in node:
            self.efg_tensors = {}
            return
        self.efg_tensors = node.efg_tensors.get_dict()

    def _update_structure(self):
        try:
            child_node = self.fetch_child_process_node()
            if child_node and hasattr(child_node, 'inputs') and 'structure' in child_node.inputs:
                self.structure = child_node.inputs.structure
            else:
                self.structure = None
        except Exception:
            self.structure = None

    def _generate_table_data(self):
        if not self.quadrupolar_parameters:
            self.table_data = []
            return
        rows = []
        for label in self.atom_labels:
            params = self.quadrupolar_parameters.get(label, {})
            rows.append({
                "Atom": label,
                "Vzz": self._fmt(params.get("Vzz")),
                "eta": self._fmt(params.get("eta"), 5),
                "Cq": self._fmt(params.get("Cq")),
                "nu_Q": self._fmt(params.get("nu_Q")),
            })
        self.table_data = rows

    @staticmethod
    def _fmt(value, ndigits=4):
        if value is None:
            return "-"
        try:
            return f"{float(value):.{ndigits}f}"
        except (TypeError, ValueError):
            return str(value)

    def get_model_state(self):
        return {
            "efg_tensors": self.efg_tensors,
            "quadrupolar_parameters": self.quadrupolar_parameters,
            "atom_labels": self.atom_labels,
        }

    def set_model_state(self, state):
        if "efg_tensors" in state:
            self.efg_tensors = state["efg_tensors"]
        if "quadrupolar_parameters" in state:
            self.quadrupolar_parameters = state["quadrupolar_parameters"]
        if "atom_labels" in state:
            self.atom_labels = state["atom_labels"]
