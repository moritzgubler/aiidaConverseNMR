"""Standalone AiiDAlab app: quadrupolar NMR spectrum simulator.

Unlike the aiidalab-qe plugins (``app/``, ``app_efg/``), this subpackage has
no AiiDA / aiidalab-qe dependency at all -- every input (isotope, Vzz, eta,
field, lattice, EFG eigenvectors) is user-entered. Needs only numpy, scipy,
ipywidgets and plotly. Launched from ``quadrupolar_simulator.ipynb`` at the
repo root (see ``start.md`` / ``setup.cfg [aiidalab]``).
"""

from .widget import QuadrupolarSimulatorWidget

__all__ = ["QuadrupolarSimulatorWidget"]
