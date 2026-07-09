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

``ISOTOPES`` lists every ground-state quadrupolar isotope with a recommended
``Q``; the first entry per element is the default used by
:func:`default_q_i`.  Many elements have several NMR-active isotopes with
quite different ``Q`` (e.g. 121Sb/123Sb), so the GUI lets the user pick the
isotope or enter custom ``Q``/``I`` (see also :func:`build_efg_arrays`).

Data sources
------------
* ``Q``: the "year-2017" recommended set of P. Pyykkö,
  *Year-2017 nuclear quadrupole moments*, Mol. Phys. **116**, 1328-1338 (2018),
  https://doi.org/10.1080/00268976.2018.1426131 (Table 2).  Pyykkö tabulates Q
  in mb (1 mb = 1e-31 m^2); divide by 10 to get the 1e-30 m^2 units used here.
  Ground-state moments only — the table's 57Fe/77Se/119Sn entries are Mössbauer
  *excited* states; those ground states are spin-1/2, hence ``Q = 0`` here.
* ``I`` (ground-state nuclear spins) and gamma: R. K. Harris et al., *NMR
  nomenclature: nuclear spin properties and conventions for chemical shifts*
  (IUPAC Recommendations 2001), Pure Appl. Chem. **73**, 1795-1818 (2001),
  https://doi.org/10.1351/pac200173111795, Tables 1-2.  The tabulated
  ``|gamma/2pi|`` [MHz/T] is computed from that paper's magnetogyric-ratio
  column (gamma in 1e7 rad s^-1 T^-1) as gamma * 10 / (2 pi), rounded to
  ~5 significant figures.  This is the bare-nucleus constant; it differs from
  reference-compound frequency ratios (the paper's Xi column) by the chemical
  shielding of the reference, up to a few percent for heavy nuclei (Bi, Hg).

CRITICAL ordering note
----------------------
``qe-efg.x`` indexes ``q_efg``/``i_efg`` by *atom type* in the order the
``ATOMIC_SPECIES`` card is written by aiida-quantumespresso, which sorts the
kinds **alphabetically by kind name**.  :func:`build_efg_arrays` reproduces that
exact ordering so that ``Q``/``I`` attach to the correct species.
"""

# element -> tuple of (isotope_label, I, Q[1e-30 m^2], |gamma/2pi| [MHz/T] or None)
# The FIRST entry per element is the default isotope.  All ground-state
# quadrupolar isotopes with a recommended Q in Pyykkö's year-2017 table are
# listed; gamma is None only for the spin-1/2 defaults (no quadrupolar
# spectrum, so it is never used).
ISOTOPES = {
    'H':  (('1H',   0.5,   0.0,     None),
           ('2H',   1.0,   0.285783, 6.5359)),
    'Li': (('7Li',  1.5,  -4.01,    16.5485),
           ('6Li',  1.0,  -0.0808,   6.2662)),
    'Be': (('9Be',  1.5,   5.288,    5.9837),),
    'B':  (('11B',  1.5,   4.059,   13.663),
           ('10B',  3.0,   8.459,    4.5752)),
    'C':  (('13C',  0.5,   0.0,     None),),
    'N':  (('14N',  1.0,   2.044,    3.0777),),
    'O':  (('17O',  2.5,  -2.558,    5.7743),),
    'F':  (('19F',  0.5,   0.0,     None),),
    'Na': (('23Na', 1.5,  10.4,     11.2695),),
    'Mg': (('25Mg', 2.5,  19.94,     2.6083),),
    'Al': (('27Al', 2.5,  14.66,    11.1031),),
    'Si': (('29Si', 0.5,   0.0,     None),),
    'P':  (('31P',  0.5,   0.0,     None),),
    'S':  (('33S',  1.5,  -6.94,     3.2717),),
    'Cl': (('35Cl', 1.5,  -8.112,    4.1765),
           ('37Cl', 1.5,  -6.393,    3.4765)),
    'K':  (('39K',  1.5,   6.03,     1.9895),
           ('41K',  1.5,   7.34,     1.0919),
           ('40K',  4.0,  -7.50,    2.4737)),
    'Ca': (('43Ca', 3.5,  -4.08,     2.8697),),
    'Sc': (('45Sc', 3.5, -22.0,     10.3591),),
    'Ti': (('47Ti', 2.5,  30.2,      2.404),
           ('49Ti', 3.5,  24.7,      2.4048)),
    'V':  (('51V',  3.5,  -5.2,     11.2133),
           ('50V',  6.0,  21.0,     4.2505)),
    'Cr': (('53Cr', 1.5, -15.0,      2.4115),),
    'Mn': (('55Mn', 2.5,  33.0,     10.5763),),
    'Fe': (('57Fe', 0.5,   0.0,     None),),
    'Co': (('59Co', 3.5,  42.0,     10.0777),),
    'Ni': (('61Ni', 1.5,  16.2,      3.8114),),
    'Cu': (('63Cu', 1.5, -22.0,     11.3188),
           ('65Cu', 1.5, -20.4,     12.1027)),
    'Zn': (('67Zn', 2.5,  12.2,      2.6685),),
    'Ga': (('69Ga', 1.5,  17.1,     10.2478),
           ('71Ga', 1.5,  10.7,     13.0207)),
    'Ge': (('73Ge', 4.5, -19.6,      1.4897),),
    'As': (('75As', 1.5,  31.1,      7.315),),
    'Se': (('77Se', 0.5,   0.0,     None),),
    'Br': (('79Br', 1.5,  30.87,    10.7042),
           ('81Br', 1.5,  25.79,    11.5384)),
    'Rb': (('87Rb', 1.5,  13.35,    13.984),
           ('85Rb', 2.5,  27.6,      4.1264)),
    'Sr': (('87Sr', 4.5,  30.5,      1.8525),),
    'Y':  (('89Y',  0.5,   0.0,     None),),
    'Zr': (('91Zr', 2.5, -17.6,      3.9748),),
    'Nb': (('93Nb', 4.5, -32.0,     10.4523),),
    'Mo': (('95Mo', 2.5,  -2.2,      2.7868),
           ('97Mo', 2.5,  25.5,     2.8457)),
    'Cd': (('111Cd', 0.5,  0.0,     None),),
    'In': (('115In', 4.5, 77.2,      9.3857),
           ('113In', 4.5, 76.1,      9.3655)),
    'Sn': (('119Sn', 0.5,  0.0,     None),),
    'Sb': (('121Sb', 2.5, -54.3,    10.2551),
           ('123Sb', 3.5, -69.2,     5.5532)),
    'Te': (('125Te', 0.5,  0.0,     None),),
    'I':  (('127I',  2.5, -68.822,   8.5778),),
    'Cs': (('133Cs', 3.5,  -0.343,   5.6233),),
    'Ba': (('137Ba', 1.5,  23.6,     4.7634),
           ('135Ba', 1.5,  15.3,     4.2582)),
    'La': (('139La', 3.5,  20.6,     6.0611),
           ('138La', 5.0,  45.0,    5.6615)),
    'Ta': (('181Ta', 3.5, 317.0,     5.1627),),
    'W':  (('183W',  0.5,   0.0,    None),),
    'Pt': (('195Pt', 0.5,   0.0,    None),),
    'Au': (('197Au', 1.5,  54.7,     0.7529),),
    'Hg': (('201Hg', 1.5,  38.7,     2.8469),),
    'Tl': (('205Tl', 0.5,   0.0,    None),),
    'Pb': (('207Pb', 0.5,   0.0,    None),),
    'Bi': (('209Bi', 4.5, -51.6,     7.2326),),
}


# element -> (isotope_label, I, Q[1e-30 m^2]) for the default isotope.
DEFAULT_NUCLEAR_DATA = {
    element: (isotopes[0][0], isotopes[0][1], isotopes[0][2])
    for element, isotopes in ISOTOPES.items()
}


# Gyromagnetic ratio |gamma/2pi| in MHz/T for the default (quadrupolar) isotope
# of each element, used to convert an external field B [T] into the Larmor
# frequency nu_L = |gamma/2pi| * B [MHz] for the quadrupolar-spectrum simulation
# (sign dropped: only |nu_L| enters the 2nd-order term).  Only nuclei with
# I >= 1 (which have a quadrupolar spectrum) are included.
GYROMAGNETIC_RATIOS = {
    element: isotopes[0][3]
    for element, isotopes in ISOTOPES.items()
    if isotopes[0][1] >= 1.0 and isotopes[0][3] is not None
}


def isotopes_for(element):
    """All tabulated ``(label, I, Q, gamma)`` entries for ``element``.

    The first entry is the default isotope; ``gamma`` (|gamma/2pi| in MHz/T)
    may be None.  Unknown elements give an empty list.
    """
    return list(ISOTOPES.get(element, ()))


def isotope_entry(element, label):
    """The ``(label, I, Q, gamma)`` entry for one isotope, or None."""
    for entry in ISOTOPES.get(element, ()):
        if entry[0] == label:
            return entry
    return None


def matching_isotope(element, quadrupole_moment, spin):
    """Isotope label whose (Q, I) match the given values, or None."""
    for label, iso_spin, iso_q, _gamma in isotopes_for(element or ''):
        if (abs(quadrupole_moment - iso_q) < 1e-6
                and abs(spin - iso_spin) < 1e-6):
            return label
    return None


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
