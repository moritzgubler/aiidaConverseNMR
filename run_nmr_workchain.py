"""
Example script for running the NMR converse WorkChain.

This script shows how to:
1. Set up the necessary codes in AiiDA
2. Prepare the structure
3. Configure parameters
4. Submit the workchain
5. Retrieve results

Before running this script, make sure:
- AiiDA is installed and configured
- You have set up your codes (pw.x and qe-converse.x) in AiiDA
- You have pseudopotentials loaded
"""

from aiida import orm, load_profile
from aiida.engine import submit
# from aiida_quantumespresso.data.pseudopotential import upload_pseudo_family
import numpy as np
from ase.io import read

# Load AiiDA profile
load_profile()


def get_pseudopotentials(structure: orm.StructureData, pp_label: str):
    """Get custom GIPAW pseudopotentials."""
    from aiida.orm import QueryBuilder, Group
    
    # Get pseudos for each element in the structure
    pseudos = {}
    for kind in structure.get_kind_names():
        # Find the pseudo for this element
        qb = QueryBuilder()
        qb.append(Group, filters={'label': pp_label}, tag='group')  # Changed here too
        qb.append(orm.UpfData, with_group='group', 
                  filters={'attributes.element': kind})
        results = qb.all()
        
        if results:
            pseudos[kind] = results[0][0].pk
        else:
            raise ValueError(f"No pseudo found for element {kind} in gipaw family")
    
    # return pseudos  # Return dict directly, NOT orm.Dict(dict=pseudos)
    return orm.Dict(dict=pseudos)


def prepare_scf_parameters():
    """
    Prepare parameters for the SCF calculation.
    IMPORTANT: Must disable -k symmetry (nosym = True, noinv = True)
    """
    parameters = {
        'CONTROL': {
            'calculation': 'scf',
            'restart_mode': 'from_scratch',
            'verbosity': 'high',
        },
        'SYSTEM': {
            'ecutwfc': 80.0,  # Adjust based on your pseudopotentials
                # 'occupations': 'smearing',
                # 'smearing': 'gaussian',
                # 'degauss': 0.01,
            'nosym': True,  # CRITICAL: Disable symmetry for NMR
            'noinv': True,  # CRITICAL: Disable inversion symmetry
            'nbnd' : 30
        },
        'ELECTRONS': {
            'conv_thr': 1.0e-10,
            'mixing_beta': 0.5,
        },
    }
    
    return orm.Dict(dict=parameters)

def prepare_converse_parameters(mixing_beta = 0.5):
    """
    Prepare base parameters for converse calculations.
    The workchain will add atom-specific and direction-specific parameters.
    """
    parameters = {
        "mixing_beta": mixing_beta
    }
    
    return orm.Dict(dict=parameters)

def prepare_options():
    """
    Prepare computational resources.
    Adjust based on your system.
    """
    options = {
        'resources': {
            'num_machines': 1,
            'num_mpiprocs_per_machine': 16,
        },
        'max_wallclock_seconds': 3600 * 4,  # 4 hours
        'queue_name': 'daily',  # If applicable
    }
    
    return orm.Dict(dict=options)


def main():
    """
    Main function to submit the NMR converse workchain.
    """
    print("Setting up NMR converse calculation...")
    
    # 1. define codes
    pw_code = orm.load_code('qe-7.2@merlin')  # pw code
    converse_code = orm.load_code('qe-converse@merlin')  # converse code
    print(f"Using pw.x code: {pw_code.label}")
    print(f"Using qe-converse code: {converse_code.label}")
    
    # 2. Create structure
    ase_structure = read("quartz.extxyz")
    structure = orm.StructureData(ase=ase_structure)
    print(f"Structure has {len(structure.sites)} atoms")
    
    # 3. Get pseudopotentials
    pseudos = get_pseudopotentials(structure, 'gipaw')
    print("Pseudopotentials loaded")
    
    # 4. Prepare parameters
    scf_params = prepare_scf_parameters()
    converse_params = prepare_converse_parameters(mixing_beta=0.5)
    options = prepare_options()
    
    # 5. Define target atoms (0-indexed)
    target_atoms = orm.List(list=[0, 1, 2, 3, 4, 5])
    print(f"Will compute chemical shifts for atoms: {target_atoms.get_list()}")
    
    # 6. Prepare inputs for the workchain
    # from nmr_converse_workchain import NmrConverseWorkChain
    from aiida_qe_converse.workflows.nmr_converse_workchain import NmrConverseWorkChain
    
    inputs = {
        'structure': structure,
        'pw_code': pw_code,
        'converse_code': converse_code,
        'scf_parameters': scf_params,
        'converse_parameters': converse_params,
        'pseudos': pseudos,
        'target_atoms': target_atoms,
        'options': options,
        'kpoints_distance': orm.Float(0.5),
        'q_gipaw': orm.Float(0.01),
        'mixing_beta': orm.Float(0.5),
        'dudk_method': orm.Str('covariant'),
    }
    
    # 7. Submit the workchain
    print("\nSubmitting workchain...")
    workchain = submit(NmrConverseWorkChain, **inputs)
    print(f"Submitted NmrConverseWorkChain with PK: {workchain.pk}")
    print(f"\nTo monitor the workchain, use:")
    print(f"  verdi process show {workchain.pk}")
    print(f"  verdi process status {workchain.pk}")
    print(f"\nTo see the report:")
    print(f"  verdi process report {workchain.pk}")
    
    return workchain


def retrieve_results(workchain_pk):
    """
    Retrieve and display results from a completed workchain.
    
    Args:
        workchain_pk: PK of the completed workchain
    """
    workchain = orm.load_node(workchain_pk)
    
    if not workchain.is_finished_ok:
        print(f"Workchain did not complete successfully")
        print(f"Status: {workchain.process_state}")
        if workchain.exit_status:
            print(f"Exit status: {workchain.exit_status}")
            print(f"Exit message: {workchain.exit_message}")
        return
    
    print("Workchain completed successfully!")
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    # Get results
    tensors = workchain.outputs.absolute_shift_tensor_ppm.get_dict()
    isotropic_data = workchain.outputs.isotropic_shielding_ppm.get_dict()
    
    print("\nChemical Shift Tensors and Isotropic Shielding:")
    print("-"*60)
    for atom_label in tensors.keys():
        tensor = tensors[atom_label]
        isotropic = isotropic_data[atom_label]['isotropic_shielding_ppm']
        
        print(f"\n{atom_label}:")
        print(f"  Isotropic shielding: {isotropic:8.3f} ppm")
        print(f"  Tensor (ppm):")
        print(f"    [{tensor[0][0]:8.3f}, {tensor[0][1]:8.3f}, {tensor[0][2]:8.3f}]")
        print(f"    [{tensor[1][0]:8.3f}, {tensor[1][1]:8.3f}, {tensor[1][2]:8.3f}]")
        print(f"    [{tensor[2][0]:8.3f}, {tensor[2][1]:8.3f}, {tensor[2][2]:8.3f}]")
    
    print("\n" + "="*60)
    
    # Export data to file
    import json
    combined_results = {
        atom: {
            'tensor_ppm': tensors[atom],
            'isotropic_shielding_ppm': isotropic_data[atom]['isotropic_shielding_ppm']
        }
        for atom in tensors.keys()
    }
    output_file = f'nmr_results_{workchain_pk}.json'
    with open(output_file, 'w') as f:
        json.dump(combined_results, f, indent=2)
    print(f"\nResults exported to: {output_file}")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Run or retrieve results from NMR converse workflow'
    )
    parser.add_argument(
        '--retrieve', '-r',
        type=int,
        metavar='PK',
        help='Retrieve results from a completed workchain (provide PK (int))'
    )
    
    args = parser.parse_args()
    
    if args.retrieve:
        retrieve_results(args.retrieve)
    else:
        workchain = main()
