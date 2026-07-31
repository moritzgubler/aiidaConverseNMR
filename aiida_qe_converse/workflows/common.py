"""
Shared helpers for the converse-based workchains (NMR and EFG).

This module factors out the pieces that are identical between
``NmrConverseWorkChain`` and ``EfgWorkChain``:

* pseudopotential lookup from a named AiiDA group (``gipaw_PBE`` / ``gipaw_PBEsol``)
* the protocol table (``fast`` / ``moderate`` / ``precise``)
* construction of the pw.x SCF parameter dictionary
* computational ``options`` (resources / wallclock / memory) assembly

Keeping these in one place avoids copy-paste drift between the two workflows.
The only physics difference between the NMR and EFG SCF is symmetry: NMR needs
``nosym=True, noinv=True`` (the converse perturbation breaks symmetry), whereas
EFG is a ground-state property and keeps symmetry on (``qe-efg.x`` symmetrises
the tensor itself via ``symtensor``), which is faster.
"""

from aiida_quantumespresso.common.types import ElectronicType


# Protocol table shared by the converse workchains. Values mirror the NMR
# protocols; EFG is k-point insensitive (a local charge-density property) so
# even the ``fast`` grid converges it, but we keep the same knobs for a uniform
# user experience and to allow a single SCF to be reused conceptually.
PROTOCOLS = {
    'fast': {
        'ecutwfc': 60.0,
        'kpoints_distance': 0.5,
        'conv_thr': 1.0e-8,
        'degauss': 1e-2,
        'mixing_beta': 0.3,
        'num_machines': 1,
        'num_mpiprocs_per_machine': 8,
        'max_wallclock_seconds': 3600 * 23,
        'max_memory_kb': 32000000,
    },
    'moderate': {
        'ecutwfc': 80.0,
        'kpoints_distance': 0.2,
        'conv_thr': 1.0e-9,
        'degauss': 1e-3,
        'mixing_beta': 0.3,
        'num_machines': 1,
        'num_mpiprocs_per_machine': 16,
        'max_wallclock_seconds': 3600 * 23,
        'max_memory_kb': 128000000,
    },
    'precise': {
        'ecutwfc': 100.0,
        'kpoints_distance': 0.1,
        'conv_thr': 1.0e-10,
        'degauss': 1e-3,
        'mixing_beta': 0.3,
        'num_machines': 1,
        'num_mpiprocs_per_machine': 32,
        'max_wallclock_seconds': 3600 * 23,
        'max_memory_kb': 480000000,
    },
}


# aiidalab-qe's global protocol selector uses the names fast/balanced/stringent.
# Accept those as aliases of our fast/moderate/precise table so the GUI works
# without a separate per-plugin protocol control.
PROTOCOL_ALIASES = {
    'balanced': 'moderate',
    'stringent': 'precise',
}


def get_protocol(name, overrides=None):
    """Return a copy of the protocol dictionary, applying ``overrides`` if given.

    Args:
        name: one of ``fast``, ``moderate``, ``precise`` (the aiidalab-qe names
            ``balanced``/``stringent`` are accepted as aliases).
        overrides: optional dict merged on top of the protocol values.

    Returns:
        A fresh dict (safe to mutate by the caller).
    """
    resolved = PROTOCOL_ALIASES.get(name, name)
    if resolved not in PROTOCOLS:
        raise ValueError(
            f"Unknown protocol '{name}'. Choose from: "
            f"{list(PROTOCOLS.keys())} (aliases: {list(PROTOCOL_ALIASES.keys())})"
        )
    proto = dict(PROTOCOLS[resolved])
    if overrides:
        proto.update(overrides)
    return proto


def lookup_pseudos(structure, pseudo_family):
    """Look up GIPAW pseudopotentials for every kind in ``structure``.

    Pseudos are stored as ``UpfData`` nodes inside a named AiiDA ``Group``
    (e.g. ``gipaw_PBE``). We match on the *element symbol* of each kind, so a
    structure that uses custom kind names (e.g. ``Fe1``/``Fe2`` for two
    inequivalent iron sites) still resolves to the right pseudo.

    Args:
        structure: ``StructureData`` node.
        pseudo_family: label of the AiiDA group holding the pseudos.

    Returns:
        Dict mapping kind name -> pseudo node PK.

    Raises:
        ValueError: if no pseudo is found for some element.
    """
    from aiida.orm import QueryBuilder, Group
    from aiida_pseudo.data.pseudo.upf import UpfData

    pseudos = {}
    for kind in structure.kinds:
        element = kind.symbol
        qb = QueryBuilder()
        qb.append(Group, filters={'label': pseudo_family}, tag='group')
        qb.append(UpfData, with_group='group', filters={'attributes.element': element})
        results = qb.all()
        if results:
            pseudos[kind.name] = results[0][0].pk
        else:
            raise ValueError(
                f"No pseudo found for element {element} (kind '{kind.name}') in family '{pseudo_family}'"
            )
    return pseudos


def list_gipaw_pseudo_families():
    """Return the labels of available GIPAW pseudo groups (``gipaw*``), sorted."""
    from aiida.orm import QueryBuilder, Group
    qb = QueryBuilder()
    qb.append(Group, filters={'label': {'like': 'gipaw%'}}, project='label')
    return sorted({row[0] for row in qb.all()})


def pseudo_status(structure, pseudo_family):
    """Non-raising per-element lookup for the GUI preview.

    Returns a dict ``{element_symbol: filename_or_None}`` for the distinct
    elements in ``structure``; ``None`` means no GIPAW pseudo is present for that
    element in ``pseudo_family``.
    """
    from aiida.orm import QueryBuilder, Group
    from aiida_pseudo.data.pseudo.upf import UpfData

    elements = []
    for kind in structure.kinds:
        if kind.symbol not in elements:
            elements.append(kind.symbol)

    status = {}
    for element in elements:
        qb = QueryBuilder()
        qb.append(Group, filters={'label': pseudo_family}, tag='group')
        qb.append(UpfData, with_group='group', filters={'attributes.element': element})
        match = qb.first()
        status[element] = match[0].filename if match else None
    return status


def resolve_electronic_type(electronic_type):
    """Normalise ``electronic_type`` (str/enum/None) to an ``ElectronicType``."""
    if electronic_type is None:
        return ElectronicType.METAL
    if isinstance(electronic_type, str):
        return ElectronicType(electronic_type.lower())
    return electronic_type


def degauss_for(proto, electronic_type):
    """Return the smearing width: tiny for insulators, protocol value otherwise."""
    electronic_type = resolve_electronic_type(electronic_type)
    if electronic_type == ElectronicType.INSULATOR:
        return 1e-8
    return proto['degauss']


def build_scf_parameters(proto, electronic_type=None, nosym=False, noinv=False,
                          smearing_type=None, smearing_degauss=None):
    """Build the pw.x SCF parameter dictionary.

    Args:
        proto: a protocol dict (see :func:`get_protocol`).
        electronic_type: ``ElectronicType``, str, or None (defaults to METAL).
        nosym: set ``SYSTEM.nosym = True`` (required for the NMR converse SCF).
        noinv: set ``SYSTEM.noinv = True`` (required for the NMR converse SCF).
        smearing_type: smearing function to use (default ``fermi-dirac``).
        smearing_degauss: smearing width in Ry, overriding the protocol/insulator default.

    Returns:
        A nested dict ready to wrap in ``orm.Dict`` for ``PwBaseWorkChain``.
    """
    degauss = smearing_degauss if smearing_degauss is not None else degauss_for(proto, electronic_type)
    system = {
        'ecutwfc': proto['ecutwfc'],
        'occupations': 'smearing',
        'smearing': smearing_type if smearing_type is not None else 'fermi-dirac',
        'degauss': degauss,
    }
    if nosym:
        system['nosym'] = True
    if noinv:
        system['noinv'] = True

    return {
        'CONTROL': {
            'calculation': 'scf',
            'restart_mode': 'from_scratch',
            'verbosity': 'high',
        },
        'SYSTEM': system,
        'ELECTRONS': {
            'conv_thr': proto['conv_thr'],
            'mixing_beta': proto['mixing_beta'],
        },
    }


def build_options(proto, queue_name=None):
    """Assemble the ``metadata.options`` dict (resources / wallclock / memory)."""
    options = {
        'resources': {
            'num_machines': proto['num_machines'],
            'num_mpiprocs_per_machine': proto['num_mpiprocs_per_machine'],
        },
        'max_wallclock_seconds': proto['max_wallclock_seconds'],
        'max_memory_kb': proto['max_memory_kb'],
    }
    if queue_name:
        options['queue_name'] = queue_name
    return options
