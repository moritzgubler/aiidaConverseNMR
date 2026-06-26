"""Workchain integration for the EFG plugin."""
from aiida.plugins import WorkflowFactory

EfgWorkChain = WorkflowFactory("qeconverse.efg")


def get_builder(codes, structure, parameters, **kwargs):
    """Build an :class:`EfgWorkChain` builder from the GUI parameters.

    The key of the per-plugin ``parameters`` dict is the entry point name
    (``qeefg``); ``codes`` carries ``pw_efg`` and ``qeefg``.
    """
    protocol = parameters["workchain"].get("protocol", "moderate")

    efg_params = parameters.get("qeefg", {})
    target_atoms = efg_params.get("target_atoms", None)
    nuclear_data = efg_params.get("nuclear_data", None) or None

    pw_code = codes.get("pw_efg", {}).get("code", None)
    efg_code = codes.get("qeefg", {}).get("code", None)

    builder = EfgWorkChain.get_builder_from_protocol(
        pw_code=pw_code,
        efg_code=efg_code,
        structure=structure,
        protocol=protocol,
        target_atoms=target_atoms,
        nuclear_data=nuclear_data,
        **kwargs
    )
    return builder


workchain_and_builder = {
    "workchain": EfgWorkChain,
    "exclude": ("clean_workdir",),
    "get_builder": get_builder,
}
