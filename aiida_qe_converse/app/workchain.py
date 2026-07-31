"""
Workchain integration for NMR Converse plugin.
"""
from aiida.plugins import WorkflowFactory

# Load the NMR Converse workchain
NmrConverseWorkChain = WorkflowFactory("qeconverse.nmr_converse")


def get_builder(codes, structure, parameters, **kwargs):
    """
    Get builder for NMR Converse workchain.


    the key of the parameters dict is the entry point name: qeconverse.

    Args:
        codes: Dictionary of code nodes (pw_nmr, qeconverse)
        structure: StructureData node
        parameters: Configuration parameters dictionary
        **kwargs: Additional arguments

    Returns:
        ProcessBuilder for NmrConverseWorkChain
    """
    # Extract protocol and settings
    protocol = parameters["workchain"].get("protocol", "moderate")

    # Extract NMR-specific parameters
    # kpoints_distance = parameters.get("kpoints_distance", 0.25)
    # ecutwfc = parameters.get("ecutwfc", 90.0)
    # conv_thr = parameters.get("conv_thr", 1.0e-10)
    # mixing_beta = parameters.get("mixing_beta", 0.4)
    # q_gipaw = parameters.get("q_gipaw", 0.01)
    # dudk_method = parameters.get("dudk_method", "covariant")

    target_atoms = parameters["qeconverse"].get("target_atoms", None)
    pseudo_family = parameters["qeconverse"].get("pseudo_family", "gipaw_PBE")

    # Get codes
    pw_code = codes.get("pw_nmr",{}).get("code",None)
    converse_code = codes.get("qeconverse",{}).get("code",None)

    # Use the workchain's get_builder_from_protocol method
    builder = NmrConverseWorkChain.get_builder_from_protocol(
        pw_code=pw_code,
        converse_code=converse_code,
        structure=structure,
        protocol=protocol,
        pseudo_family=pseudo_family,
        target_atoms=target_atoms,
        # overrides={
        #     "kpoints_distance": kpoints_distance,
        #     "ecutwfc": ecutwfc,
        #     "conv_thr": conv_thr,
        #     "mixing_beta": mixing_beta,
        #     "q_gipaw": q_gipaw,
        # },
        # dudk_method=dudk_method,
        **kwargs
    )

    return builder


# Export workchain and builder function
workchain_and_builder = {
    "workchain": NmrConverseWorkChain,
    "exclude": ("clean_workdir",),
    "get_builder": get_builder,
}
