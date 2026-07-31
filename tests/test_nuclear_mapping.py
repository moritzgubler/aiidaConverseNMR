"""Tests for the nuclear-data table and species->array mapping (no AiiDA)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiida_qe_converse.data.nuclear import (
    DEFAULT_NUCLEAR_DATA,
    build_efg_arrays,
    default_q_i,
    isotope_entry,
    isotopes_for,
)


def test_default_lookup_known_and_unknown():
    q, i = default_q_i('O')
    assert abs(q - (-2.558)) < 1e-6 and i == 2.5
    q, i = default_q_i('Si')
    assert q == 0.0 and i == 0.5
    # Unknown element -> skipped
    assert default_q_i('Xx') == (0.0, 0.0)


def test_isotope_table():
    # first entry per element is the default and feeds DEFAULT_NUCLEAR_DATA
    label, spin, quad, _gamma = isotopes_for('Cl')[0]
    assert (label, spin, quad) == DEFAULT_NUCLEAR_DATA['Cl']
    # sibling isotope lookup (Pyykkö 2017: 37Cl Q = -63.93 mb)
    entry = isotope_entry('Cl', '37Cl')
    assert entry[1] == 1.5 and abs(entry[2] - (-6.393)) < 1e-9
    # unknown element / isotope
    assert isotopes_for('Xx') == []
    assert isotope_entry('Cl', '99Cl') is None


def test_alphabetical_species_ordering():
    # aiida-quantumespresso writes ATOMIC_SPECIES sorted alphabetically by kind.
    # Input order is Si then O; output must be O then Si.
    arrays = build_efg_arrays([('Si', 'Si'), ('O', 'O')])
    assert arrays['species_order'] == ['O', 'Si']
    assert arrays['elements'] == ['O', 'Si']
    # Q/I must follow that order: O first.
    assert abs(arrays['q_efg'][0] - (-2.558)) < 1e-6
    assert arrays['i_efg'][0] == 2.5
    assert arrays['q_efg'][1] == 0.0  # Si


def test_custom_kind_names_resolve_element():
    kinds = [('O2', 'O'), ('O1', 'O'), ('Si1', 'Si')]
    arrays = build_efg_arrays(kinds)
    assert arrays['species_order'] == ['O1', 'O2', 'Si1']
    assert arrays['elements'] == ['O', 'O', 'Si']
    assert arrays['q_efg'][0] == arrays['q_efg'][1]  # both oxygen defaults


def test_override_by_element_and_by_kind():
    kinds = [('O1', 'O'), ('O2', 'O')]
    # element override applies to all oxygens
    arrays = build_efg_arrays(kinds, overrides={'O': {'Q': -2.0, 'I': 2.5}})
    assert arrays['q_efg'] == [-2.0, -2.0]
    # kind override takes precedence over the element override
    arrays = build_efg_arrays(kinds, overrides={'O': {'Q': -2.0}, 'O1': {'Q': -9.9}})
    assert arrays['species_order'] == ['O1', 'O2']
    assert arrays['q_efg'][0] == -9.9
    assert arrays['q_efg'][1] == -2.0


def test_q_zero_skip_convention():
    arrays = build_efg_arrays([('C', 'C'), ('H', 'H')])
    # C and H are spin-1/2, Q=0 -> skipped (no Cq)
    assert all(q == 0.0 for q in arrays['q_efg'])
