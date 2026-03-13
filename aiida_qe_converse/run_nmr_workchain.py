"""
CLI for submitting and retrieving NMR converse WorkChain calculations.

Installed as `nmr-converse` via the console_scripts entry point.

Usage:
  nmr-converse --input structure.extxyz [options]
  nmr-converse --retrieve <PK>

Before running, make sure:
- AiiDA is installed and configured
- pw.x and qe-converse.x codes are set up in AiiDA
- GIPAW pseudopotentials are loaded (e.g. group 'gipaw_PBE')
"""

from aiida import orm, load_profile
from aiida.engine import submit
# from aiida_quantumespresso.data.pseudopotential import upload_pseudo_family
import numpy as np
from ase.io import read

# Load AiiDA profile
load_profile()


def main(inputfileName: str, protocol: str = 'moderate', pseudo_family='gipaw_PBE', target_atoms=None,
         spin_polarized=False, initial_magnetic_moments=None, smearing_type=None, smearing_degauss=None,
         npool=0, pw_code_label='qe-7.5@merlin', converse_code_label='qe-converse-7.5@merlin'):
    """
    Main function to submit the NMR converse workchain.

    This demonstrates the new get_builder_from_protocol method.
    """
    print("Setting up NMR converse calculation...")

    # 1. Define codes
    pw_code = orm.load_code(pw_code_label)
    converse_code = orm.load_code(converse_code_label)
    print(f"Using pw.x code: {pw_code.label}")
    print(f"Using qe-converse code: {converse_code.label}")

    # 2. Create structure
    ase_structure = read(inputfileName)
    structure = orm.StructureData(ase=ase_structure)
    nat = len(structure.sites)
    print(f"Structure has {len(structure.sites)} atoms")

    # 3. Get builder from protocol (NEW METHOD)
    from aiida_qe_converse.workflows.nmr_converse_workchain import NmrConverseWorkChain

    builder = NmrConverseWorkChain.get_builder_from_protocol(
        pw_code=pw_code,
        converse_code=converse_code,
        structure=structure,
        protocol=protocol,  # Options: 'fast', 'moderate', 'precise'
        pseudo_family=pseudo_family,
        target_atoms=target_atoms,  # None = all atoms, or provide list like [0, 1, 2]
        spin_polarized=spin_polarized,
        initial_magnetic_moments=initial_magnetic_moments,
        smearing_type=smearing_type,
        smearing_degauss=smearing_degauss,
        npool=npool,
        queue_name='daily',  # Optional: specify queue name
    )

    # Optional: Override specific parameters if needed
    # Example: builder.kpoints_distance = orm.Float(0.10)
    # Example: builder.mixing_beta = orm.Float(0.3)

    print(f"Will compute chemical shifts for {len(builder.target_atoms.get_list())} atoms")

    # 4. Submit the workchain
    print("\nSubmitting workchain...")
    workchain = submit(builder)
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
    print("COMPUTATIONAL COST")
    print("="*60)

    # Compute CPU hours
    total_cpu_hours = 0.0
    scf_cpu_hours = 0.0
    converse_cpu_hours = 0.0

    # Get all called descendants (SCF and converse calculations)
    from aiida.orm import QueryBuilder, CalcJobNode

    # Get all CalcJob descendants (including nested ones)
    calc_nodes = []
    scf_calc_nodes = []
    converse_calc_nodes = []

    # Method 1: Get direct children CalcJobs (converse calculations)
    qb = QueryBuilder()
    qb.append(orm.WorkChainNode, filters={'id': workchain_pk}, tag='wc')
    qb.append(CalcJobNode, with_incoming='wc')
    direct_calcs = qb.all(flat=True)

    # Method 2: Get CalcJobs from PwBaseWorkChain (SCF calculation)
    qb2 = QueryBuilder()
    qb2.append(orm.WorkChainNode, filters={'id': workchain_pk}, tag='wc')
    qb2.append(orm.WorkChainNode, with_incoming='wc', tag='pwbase')
    qb2.append(CalcJobNode, with_incoming='pwbase')
    scf_calcs = qb2.all(flat=True)

    calc_nodes = list(direct_calcs) + list(scf_calcs)

    # Categorize by looking at process_label
    for calc in calc_nodes:
        label = calc.base.attributes.all.get('process_label', '')
        if 'Pw' in label:
            scf_calc_nodes.append(calc)
        else:
            converse_calc_nodes.append(calc)

    print(f"\nTotal calculations: {len(calc_nodes)}")
    print(f"  - {len(scf_calc_nodes)} SCF calculation(s)")
    print(f"  - {len(converse_calc_nodes)} converse calculations")

    def parse_wall_time(line):
        """Parse wall time from QE output line like '5h44m WALL' or '13m16.78s WALL'"""
        try:
            wall_idx = line.index('WALL')
            time_part = line[:wall_idx].strip().split()[-1]
            total_seconds = 0.0
            if 'h' in time_part:
                hours, time_part = time_part.split('h', 1)
                total_seconds += float(hours) * 3600
            if 'm' in time_part:
                minutes, time_part = time_part.split('m', 1)
                total_seconds += float(minutes) * 60
            if time_part:
                time_part = time_part.rstrip('s')
                if time_part:
                    total_seconds += float(time_part)
            return total_seconds if total_seconds > 0 else None
        except:
            return None

    for calc in calc_nodes:
        try:
            all_attrs = calc.base.attributes.all
            calc_label = all_attrs.get('process_label', '')

            # Get wall time from output_parameters or parse from file
            wall_time_seconds = None
            try:
                output_params = calc.outputs.output_parameters.get_dict()
                wall_time_seconds = output_params.get('wall_time_seconds')
            except:
                pass

            # If not found, parse from output file
            if wall_time_seconds is None:
                try:
                    retrieved = calc.outputs.retrieved
                    output_filename = all_attrs.get('output_filename', 'aiida.out')
                    with retrieved.open(output_filename, 'r') as f:
                        for line in f:
                            if 'WALL' in line and ('QE-CONVERSE' in line or 'PWSCF' in line):
                                wall_time_seconds = parse_wall_time(line)
                                if wall_time_seconds:
                                    break
                except:
                    pass

            if not wall_time_seconds or wall_time_seconds <= 0:
                continue

            # Get number of cores
            resources = all_attrs.get('resources', {})
            num_machines = resources.get('num_machines', 1)
            num_mpiprocs_per_machine = resources.get('num_mpiprocs_per_machine', 1)
            total_cores = num_machines * num_mpiprocs_per_machine

            # Compute CPU hours
            cpu_hours = (wall_time_seconds / 3600.0) * total_cores
            total_cpu_hours += cpu_hours

            if 'Pw' in calc_label:
                scf_cpu_hours += cpu_hours
            else:
                converse_cpu_hours += cpu_hours

        except:
            continue

    print(f"\nCPU Hours (core-hours) breakdown:")
    print(f"  SCF calculation:       {scf_cpu_hours:8.2f} CPU-h")
    print(f"  Converse calculations: {converse_cpu_hours:8.2f} CPU-h")
    print(f"  {'─'*40}")
    print(f"  TOTAL:                 {total_cpu_hours:8.2f} CPU-h")

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
    combined_results['computational_cost'] = {
        'total_cpu_hours': total_cpu_hours,
        'scf_cpu_hours': scf_cpu_hours,
        'converse_cpu_hours': converse_cpu_hours,
        'num_calculations': len(calc_nodes),
    }
    output_file = f'nmr_results_{workchain_pk}.json'
    with open(output_file, 'w') as f:
        json.dump(combined_results, f, indent=2)
    print(f"\nResults exported to: {output_file}")

def cli():
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
    parser.add_argument(
        '--input', '-i',
        type=str,
        metavar='FILE',
        help='Input structure file (.extxyz format)'
    )
    parser.add_argument(
        '--protocol', '-p',
        type=str,
        choices=['fast', 'moderate', 'precise'],
        default='moderate',
        help="Protocol for parameter selection (default: 'moderate')"
    )
    parser.add_argument(
        '--pseudo-family', '-f',
        type=str,
        default='gipaw_PBE',
        help="AiiDA pseudopotential family label (default: 'gipaw_PBE')"
    )
    parser.add_argument(
        '--target-atoms', '-t',
        type=int,
        nargs='+',
        default=None,
        metavar='IDX',
        help='Zero-based indices of atoms of interest (default: all atoms). Example: -t 0 3 5'
    )
    parser.add_argument(
        '--spin-polarized',
        action='store_true',
        default=False,
        help='Perform a spin-polarized (nspin=2) collinear calculation'
    )
    parser.add_argument(
        '--magnetic-moments', '-m',
        type=str,
        default=None,
        metavar='JSON',
        help='Initial magnetic moments as JSON, e.g. \'{"Fe": 0.5, "O": 0.0}\'. '
             'Only used with --spin-polarized. Defaults to 0.0 for all kinds.'
    )
    parser.add_argument(
        '--smearing-type', '-s',
        type=str,
        default=None,
        choices=['fermi-dirac', 'methfessel-paxton', 'marzari-vanderbilt', 'gaussian'],
        help="Smearing function (default: 'fermi-dirac')"
    )
    parser.add_argument(
        '--smearing-degauss', '-d',
        type=float,
        default=None,
        metavar='RY',
        help='Smearing width in Ry (default: from protocol)'
    )
    parser.add_argument(
        '--npool', '-n',
        type=int,
        default=0,
        metavar='N',
        help='Number of k-point pools for converse calculations (-nk). '
             '0 = auto-determine from k-mesh and MPI count (default).'
    )
    parser.add_argument(
        '--pw-code',
        type=str,
        default='qe-7.5@merlin',
        metavar='CODE',
        help="AiiDA label for the pw.x code (default: 'qe-7.5@merlin')"
    )
    parser.add_argument(
        '--converse-code',
        type=str,
        default='qe-converse-7.5@merlin',
        metavar='CODE',
        help="AiiDA label for the qe-converse.x code (default: 'qe-converse-7.5@merlin')"
    )
    args = parser.parse_args()

    if args.retrieve:
        retrieve_results(args.retrieve)
    else:
        if not args.input:
            parser.error('--input/-i is required when not using --retrieve')
        magnetic_moments = None
        if args.magnetic_moments:
            import json
            magnetic_moments = json.loads(args.magnetic_moments)
        workchain = main(args.input, args.protocol, args.pseudo_family, args.target_atoms,
                         args.spin_polarized, magnetic_moments, args.smearing_type, args.smearing_degauss,
                         args.npool, args.pw_code, args.converse_code)


if __name__ == '__main__':
    cli()
