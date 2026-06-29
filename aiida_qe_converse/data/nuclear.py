"""
Built-in table of default nuclear quadrupole moments ``Q`` and spins ``I`` for
common NMR/NQR-active isotopes, and helpers to turn a structure into the
per-species ``q_efg`` / ``i_efg`` arrays expected by ``qe-efg.x``.

Units and conventions
---------------------
* ``Q`` is the nuclear electric quadrupole moment in units of **1e-30 m^2**
  (= 10 mbarn).  1 barn = 100 of these units.  Example: 17O has
  Q = -0.02558 barn = -2.558 (1e-30 m^2).  These are exactly the units the
  ``&input_qeefg`` namelist's ``q_efg(n)`` expects.
* ``I`` is the nuclear spin (dimensionless).
* ``Q = 0`` is the "skip" convention: ``qe-efg.x`` prints ``Cq`` only for
  species with ``Q != 0`` (spin-1/2 nuclei such as 1H, 13C, 29Si carry no
  quadrupole and report only ``Vzz``/``eta``).  ``nu_Q`` is printed only for
  ``I >= 1``.

The defaults below pick a representative, commonly-measured isotope per element
(values from standard compilations, e.g. Pyykkö 2018).  They are intended as a
sensible starting point; for production work, override the isotope explicitly
(see :func:`build_efg_arrays`), because many elements have several NMR-active
isotopes with quite different ``Q``.

CRITICAL ordering note
----------------------
``qe-efg.x`` indexes ``q_efg``/``i_efg`` by *atom type* in the order the
``ATOMIC_SPECIES`` card is written by aiida-quantumespresso, which sorts the
kinds **alphabetically by kind name**.  :func:`build_efg_arrays` reproduces that
exact ordering so that ``Q``/``I`` attach to the correct species.
"""

# element -> (isotope_label, I, Q[1e-30 m^2])
DEFAULT_NUCLEAR_DATA = {
    'H':  ('1H',   0.5,  0.0),
    'Li': ('7Li',  1.5, -4.01),
    'Be': ('9Be',  1.5,  5.288),
    'B':  ('11B',  1.5,  4.059),
    'C':  ('13C',  0.5,  0.0),
    'N':  ('14N',  1.0,  2.044),
    'O':  ('17O',  2.5, -2.558),
    'F':  ('19F',  0.5,  0.0),
    'Na': ('23Na', 1.5,  10.4),
    'Mg': ('25Mg', 2.5,  19.94),
    'Al': ('27Al', 2.5,  14.66),
    'Si': ('29Si', 0.5,  0.0),
    'P':  ('31P',  0.5,  0.0),
    'S':  ('33S',  1.5, -6.78),
    'Cl': ('35Cl', 1.5, -8.165),
    'K':  ('39K',  1.5,  5.85),
    'Ca': ('43Ca', 3.5, -4.08),
    'Sc': ('45Sc', 3.5, -22.0),
    'Ti': ('47Ti', 2.5,  30.2),
    'V':  ('51V',  3.5, -5.2),
    'Cr': ('53Cr', 1.5, -15.0),
    'Mn': ('55Mn', 2.5,  33.0),
    'Fe': ('57Fe', 0.5,  0.0),
    'Co': ('59Co', 3.5,  42.0),
    'Ni': ('61Ni', 1.5,  16.2),
    'Cu': ('63Cu', 1.5, -22.0),
    'Zn': ('67Zn', 2.5,  15.0),
    'Ga': ('69Ga', 1.5,  17.1),
    'Ge': ('73Ge', 4.5, -19.6),
    'As': ('75As', 1.5,  31.4),
    'Se': ('77Se', 0.5,  0.0),
    'Br': ('79Br', 1.5,  31.3),
    'Rb': ('87Rb', 1.5,  13.35),
    'Sr': ('87Sr', 4.5,  30.5),
    'Y':  ('89Y',  0.5,  0.0),
    'Zr': ('91Zr', 2.5, -17.6),
    'Nb': ('93Nb', 4.5, -32.0),
    'Mo': ('95Mo', 2.5, -2.2),
    'Cd': ('111Cd', 0.5, 0.0),
    'In': ('115In', 4.5, 77.2),
    'Sn': ('119Sn', 0.5, 0.0),
    'Sb': ('121Sb', 2.5, -36.0),
    'Te': ('125Te', 0.5, 0.0),
    'I':  ('127I', 2.5, -69.6),
    'Cs': ('133Cs', 3.5, -0.343),
    'Ba': ('137Ba', 1.5,  24.5),
    'La': ('139La', 3.5,  20.0),
    'Ta': ('181Ta', 3.5,  317.0),
    'W':  ('183W',  0.5,  0.0),
    'Pt': ('195Pt', 0.5,  0.0),
    'Au': ('197Au', 1.5,  54.7),
    'Hg': ('201Hg', 1.5,  38.6),
    'Tl': ('205Tl', 0.5,  0.0),
    'Pb': ('207Pb', 0.5,  0.0),
    'Bi': ('209Bi', 4.5, -51.6),
}


# Gyromagnetic ratio gamma/2pi in MHz/T for the default (quadrupolar) isotope of
# each element, used to convert an external field B [T] into the Larmor
# frequency nu_L = |gamma/2pi| * B [MHz] for the quadrupolar-spectrum simulation.
# Values are |gamma/2pi| (sign dropped: only |nu_L| enters the 2nd-order term).
# Only nuclei with I >= 1 (which have a quadrupolar spectrum) are tabulated.
GYROMAGNETIC_RATIOS = {
    'Li': 16.546,   # 7Li
    'Be': 5.984,    # 9Be
    'B':  13.663,   # 11B
    'N':  3.0777,   # 14N
    'O':  5.7742,   # 17O
    'Na': 11.2625,  # 23Na
    'Mg': 2.6083,   # 25Mg
    'Al': 11.1031,  # 27Al
    'S':  3.2717,   # 33S
    'Cl': 4.1765,   # 35Cl
    'K':  1.9893,   # 39K
    'Ca': 2.8697,   # 43Ca
    'Sc': 10.3589,  # 45Sc
    'Ti': 2.4040,   # 47Ti
    'V':  11.2133,  # 51V
    'Cr': 2.4115,   # 53Cr
    'Mn': 10.5763,  # 55Mn
    'Co': 10.0532,  # 59Co
    'Ni': 2.394,    # 61Ni
    'Cu': 11.3188,  # 63Cu
    'Zn': 2.6694,   # 67Zn
    'Ga': 10.2478,  # 69Ga
    'Ge': 1.4897,   # 73Ge
    'As': 7.3150,   # 75As
    'Br': 10.7042,  # 79Br
    'Rb': 13.9844,  # 87Rb
    'Sr': 1.8525,   # 87Sr
    'Zr': 3.9748,   # 91Zr
    'Nb': 10.4523,  # 93Nb
    'Mo': 2.7874,   # 95Mo
    'In': 9.3856,   # 115In
    'Sb': 10.2551,  # 121Sb
    'I':  8.5778,   # 127I
    'Cs': 5.6234,   # 133Cs
    'Ba': 4.7634,   # 137Ba
    'La': 6.0612,   # 139La
    'Ta': 5.1627,   # 181Ta
    'Au': 0.7406,   # 197Au
    'Hg': 1.7776,   # 201Hg
    'Bi': 6.9628,   # 209Bi
}


def default_q_i(element):
    """Return ``(Q, I)`` for ``element`` from the built-in table.

    Unknown elements default to ``(0.0, 0.0)`` (i.e. skipped: no ``Cq``/``nu_Q``).
    """
    isotope = DEFAULT_NUCLEAR_DATA.get(element)
    if isotope is None:
        return 0.0, 0.0
    _, spin, quad = isotope
    return quad, spin


def default_gamma(element):
    """Return |gamma/2pi| in MHz/T for the element's default isotope (or None)."""
    return GYROMAGNETIC_RATIOS.get(element)


def larmor_frequency(element, field_tesla, gamma=None):
    """Larmor frequency nu_L = |gamma/2pi| * B in MHz.

    ``gamma`` (MHz/T) overrides the built-in value; returns None if neither a
    provided nor a tabulated gamma is available.
    """
    if gamma is None:
        gamma = default_gamma(element)
    if gamma is None:
        return None
    return abs(float(gamma)) * float(field_tesla)


def build_efg_arrays(kinds, overrides=None):
    """Build the per-type ``q_efg`` / ``i_efg`` arrays in ATOMIC_SPECIES order.

    Args:
        kinds: iterable of ``(kind_name, element_symbol)`` pairs, one per kind.
        overrides: optional dict mapping a kind name *or* element symbol to a
            dict ``{'Q': <1e-30 m^2>, 'I': <spin>}`` (either key optional).
            A kind-name override takes precedence over an element override.

    Returns:
        Dict with:
            ``species_order``: kind names in the (alphabetical) species order;
            ``q_efg``: list of Q values aligned with ``species_order``;
            ``i_efg``: list of I values aligned with ``species_order``;
            ``elements``: list of element symbols aligned with ``species_order``.

    The alphabetical sort by kind name reproduces exactly how
    aiida-quantumespresso orders the ``ATOMIC_SPECIES`` card, so element ``n``
    of the returned arrays is type ``n`` (Fortran 1-based) inside ``qe-efg.x``.
    """
    overrides = overrides or {}
    # Sort by kind name to match aiida-quantumespresso's ATOMIC_SPECIES ordering.
    sorted_kinds = sorted(kinds, key=lambda ke: ke[0])

    species_order, q_efg, i_efg, elements = [], [], [], []
    for kind_name, element in sorted_kinds:
        quad, spin = default_q_i(element)
        override = overrides.get(kind_name)
        if override is None:
            override = overrides.get(element)
        if override:
            if 'Q' in override and override['Q'] is not None:
                quad = float(override['Q'])
            if 'I' in override and override['I'] is not None:
                spin = float(override['I'])
        species_order.append(kind_name)
        elements.append(element)
        q_efg.append(float(quad))
        i_efg.append(float(spin))

    return {
        'species_order': species_order,
        'elements': elements,
        'q_efg': q_efg,
        'i_efg': i_efg,
    }


def efg_arrays_from_structure(structure, overrides=None):
    """Convenience wrapper: build the EFG arrays directly from a ``StructureData``."""
    kinds = [(kind.name, kind.symbol) for kind in structure.kinds]
    return build_efg_arrays(kinds, overrides=overrides)
