"""
Results panel for NMR Converse plugin.
"""
from aiidalab_qe.common.panel import ResultsPanel
from .model import NMRResultsModel


class NMRResultsPanel(ResultsPanel[NMRResultsModel]):
    """Panel for displaying NMR Converse results."""

    identifier = "nmr_converse"
    title = "NMR Chemical Shifts"
    workchain_labels = ["nmr_converse"]

    def __init__(self, model: NMRResultsModel, **kwargs):
        super().__init__(model, **kwargs)

    def render(self):
        """Render the results panel."""
        pass

    def _render_isotropic_shielding_table(self):
        """Render table of isotropic shielding values."""
        pass

    def _render_tensor_components(self):
        """Render full chemical shift tensor components."""
        pass

    def _render_structure_view(self):
        """Render structure with NMR-active sites highlighted."""
        pass
