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
from aiida_quantumespresso.data.pseudopotential import upload_pseudo_family
import numpy as np

# Load AiiDA profile
load_profile()


def setup_codes():
    """
    Setup or retrieve AiiDA codes.
    Modify these to match your setup.
    """
    # Get pw.x code
    # Option 1: If already set up
    pw_code = orm.load_code('pw@localhost')
    
    # Option 2: Set up new code (example)
    # pw_code = orm.Code()
    # pw_code.label = 'pw'
    # pw_code.description = 'Quantum ESPRESSO pw.x'
    # pw_code.set_remote_computer_exec((computer, '/path/to/pw.x'))
    # pw_code.set_input_plugin_name('quantumespresso.pw')
    # pw_code.store()
    
    # Get qe-converse code
    # You need to set this up similarly
    converse_code = orm.load_code('qe-converse@localhost')
    
    return pw_code, converse_code


def create_structure():
    """
    Create the crystal structure for Na3Ir3O8.
    Modify this to load your actual structure.
    """
    # Example: Load from a CIF or other file
    # structure = orm.StructureData(pymatgen=pymatgen_structure)
    
    # Or create manually
    from aiida.plugins import DataFactory
    StructureData = DataFactory('core.structure')
    
    # This is a placeholder - replace with your actual structure
    structure = StructureData()
    structure.set_cell([
        [10.0, 0.0, 0.0],
        [0.0, 10.0, 0.0],
        [0.0, 0.0, 10.0]
    ])
    
    # Add atoms (example)
    # structure.append_atom(position=(0, 0, 0), symbols='Ir', name='Ir1')
    # ... add all your atoms
    
    # Or load from file
    # from ase.io import read
    # ase_structure = read('your_structure.cif')
    # structure = StructureData(ase=ase_structure)
    
    return structure


def get_pseudopotentials():
    """
    Get pseudopotentials for the calculation.
    You need to have these uploaded to AiiDA.
    """
    # Option 1: Use a pseudo family
    from aiida_quantumespresso.data.pseudopotential import get_pseudos_from_structure
    
    pseudo_family_name = 'SSSP_1.3_PBE_efficiency'  # or your family name
    structure = create_structure()
    pseudos = get_pseudos_from_structure(structure, pseudo_family_name)
    
    return orm.Dict(dict=pseudos)
    
    # Option 2: Specify manually
    # pseudos = {
    #     'Ir': orm.load_node(pseudo_pk_for_Ir),
    #     'Na': orm.load_node(pseudo_pk_for_Na),
    #     'O': orm.load_node(pseudo_pk_for_O),
    # }
    # return orm.Dict(dict=pseudos)


def prepare_scf_parameters():
    """
    Prepare parameters for the SCF calculation.
    IMPORTANT: Must disable -k symmetry (nosym = True, noinv = True)
    """
    parameters = {
        'CONTROL': {
            'calculation': 'scf',
            'restart_mode': 'from_scratch',
            'prefix': 'nmr',
            'pseudo_dir': './pseudo/',
            'outdir': './scratch/',
            'verbosity': 'high',
        },
        'SYSTEM': {
            'ecutwfc': 50.0,  # Adjust based on your pseudopotentials
            'ecutrho': 400.0,
            'occupations': 'smearing',
            'smearing': 'gaussian',
            'degauss': 0.01,
            'nosym': True,  # CRITICAL: Disable symmetry for NMR
            'noinv': True,  # CRITICAL: Disable inversion symmetry
        },
        'ELECTRONS': {
            'conv_thr': 1.0e-8,
            'mixing_beta': 0.7,
        },
    }
    
    return orm.Dict(dict=parameters)


def prepare_converse_parameters():
    """
    Prepare base parameters for converse calculations.
    The workchain will add atom-specific and direction-specific parameters.
    """
    parameters = {
        'verbosity': 'high',
        'diagonalization': 'david',
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
            'num_mpiprocs_per_machine': 64,
        },
        'max_wallclock_seconds': 3600 * 2,  # 2 hours
        'queue_name': 'your_queue_name',  # If applicable
    }
    
    return orm.Dict(dict=options)


def main():
    """
    Main function to submit the NMR converse workchain.
    """
    print("Setting up NMR converse calculation...")
    
    # 1. Get codes
    pw_code, converse_code = setup_codes()
    print(f"Using pw.x code: {pw_code.label}")
    print(f"Using qe-converse code: {converse_code.label}")
    
    # 2. Create structure
    structure = create_structure()
    print(f"Structure has {len(structure.sites)} atoms")
    
    # 3. Get pseudopotentials
    pseudos = get_pseudopotentials()
    print("Pseudopotentials loaded")
    
    # 4. Prepare parameters
    scf_params = prepare_scf_parameters()
    converse_params = prepare_converse_parameters()
    options = prepare_options()
    
    # 5. Define target atoms (0-indexed)
    # Based on your bash script: atoms 1, 3, 4, 5 (1-indexed) -> 0, 2, 3, 4 (0-indexed)
    target_atoms = orm.List(list=[0, 2, 3, 4])
    print(f"Will compute chemical shifts for atoms: {target_atoms.get_list()}")
    
    # 6. Prepare inputs for the workchain
    from nmr_converse_workchain import NmrConverseWorkChain
    
    inputs = {
        'structure': structure,
        'pw_code': pw_code,
        'converse_code': converse_code,
        'scf_parameters': scf_params,
        'converse_parameters': converse_params,
        'pseudos': pseudos,
        'target_atoms': target_atoms,
        'options': options,
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
    
    # Get chemical shifts
    chemical_shifts = workchain.outputs.chemical_shifts.get_dict()
    print("\nChemical Shift Tensor Components (ppm):")
    print("-"*60)
    for atom_label, shifts in chemical_shifts.items():
        print(f"\n{atom_label}:")
        print(f"  σ_xx = {shifts['x']:8.3f} ppm")
        print(f"  σ_yy = {shifts['y']:8.3f} ppm")
        print(f"  σ_zz = {shifts['z']:8.3f} ppm")
    
    # Get isotropic shielding
    isotropic = workchain.outputs.isotropic_shielding.get_dict()
    print("\nIsotropic Shielding (ppm):")
    print("-"*60)
    for atom_label, values in isotropic.items():
        print(f"{atom_label}: {values['isotropic']:8.3f} ppm (trace = {values['trace']:8.3f})")
    
    print("\n" + "="*60)
    
    # Export data to file if needed
    import json
    output_file = f'nmr_results_{workchain_pk}.json'
    results = {
        'chemical_shifts': chemical_shifts,
        'isotropic_shielding': isotropic
    }
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults exported to: {output_file}")


if __name__ == '__main__':
    # Submit the workchain
    workchain = main()
    
    # To retrieve results later, use:
    # retrieve_results(workchain.pk)
    
    # Or wait for completion (not recommended for long calculations)
    # from aiida.engine import run
    # results = run(NmrConverseWorkChain, **inputs)
