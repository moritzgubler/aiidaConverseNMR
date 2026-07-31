"""
CLI for submitting and retrieving the EFG (electric field gradient) WorkChain.

Mirrors ``run_nmr_workchain.py`` (protocol-based submission, CPU-hour/cost
reporting, JSON export) but targets ``EfgWorkChain`` / ``qe-efg.x``.

Before running:
- AiiDA installed and configured
- pw.x and qe-efg.x codes set up in AiiDA
- GIPAW pseudopotentials loaded in a group ('gipaw_PBE' or 'gipaw_PBEsol')
"""

from aiida import orm, load_profile
from aiida.engine import submit
from ase.io import read

load_profile()


def main(inputfileName: str, protocol: str = 'moderate', pseudo_family='gipaw_PBE',
         target_atoms=None, nuclear_data=None, compute_spectra=False, larmor_frequency=None):
    """Submit the EFG workchain via get_builder_from_protocol."""
    print("Setting up EFG calculation...")

    allowed_pseudofamilies = ["gipaw_PBE", "gipaw_PBEsol"]
    if pseudo_family not in allowed_pseudofamilies:
        raise ValueError("Pseudofamily not allowed. Given pseudo_family: " + pseudo_family)

    pw_code = orm.load_code('qe-7.2@merlin')
    efg_code = orm.load_code('qe-efg@merlin')
    print(f"Using pw.x code: {pw_code.label}")
    print(f"Using qe-efg code: {efg_code.label}")

    ase_structure = read(inputfileName)
    structure = orm.StructureData(ase=ase_structure)
    print(f"Structure has {len(structure.sites)} atoms")

    from aiida_qe_converse.workflows.efg_workchain import EfgWorkChain

    builder = EfgWorkChain.get_builder_from_protocol(
        pw_code=pw_code,
        efg_code=efg_code,
        structure=structure,
        protocol=protocol,
        pseudo_family=pseudo_family,
        target_atoms=target_atoms,
        nuclear_data=nuclear_data,
        compute_spectra=compute_spectra,
        larmor_frequency=larmor_frequency,
        queue_name='daily',
    )

    print("\nSubmitting workchain...")
    workchain = submit(builder)
    print(f"Submitted EfgWorkChain with PK: {workchain.pk}")
    print(f"\nTo monitor:")
    print(f"  verdi process show {workchain.pk}")
    print(f"  verdi process status {workchain.pk}")
    print(f"  verdi process report {workchain.pk}")

    return workchain


def _parse_wall_time(line):
    """Parse wall time from a QE output line like '5h44m WALL' or '13m16.78s WALL'."""
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
    except Exception:
        return None


def retrieve_results(workchain_pk):
    """Retrieve, display, and export results from a completed EFG workchain."""
    workchain = orm.load_node(workchain_pk)

    if not workchain.is_finished_ok:
        print("Workchain did not complete successfully")
        print(f"Status: {workchain.process_state}")
        if workchain.exit_status:
            print(f"Exit status: {workchain.exit_status}")
            print(f"Exit message: {workchain.exit_message}")
        return

    print("Workchain completed successfully!")
    print("\n" + "=" * 60)
    print("COMPUTATIONAL COST")
    print("=" * 60)

    from aiida.orm import QueryBuilder, CalcJobNode

    # Direct CalcJobs (the qe-efg run via its base workchain)
    qb = QueryBuilder()
    qb.append(orm.WorkChainNode, filters={'id': workchain_pk}, tag='wc')
    qb.append(orm.WorkChainNode, with_incoming='wc', tag='child')
    qb.append(CalcJobNode, with_incoming='child')
    calc_nodes = list(qb.all(flat=True))

    # Also catch any CalcJob directly under the top workchain
    qb2 = QueryBuilder()
    qb2.append(orm.WorkChainNode, filters={'id': workchain_pk}, tag='wc')
    qb2.append(CalcJobNode, with_incoming='wc')
    calc_nodes += list(qb2.all(flat=True))

    scf_cpu_hours = 0.0
    efg_cpu_hours = 0.0
    total_cpu_hours = 0.0

    for calc in calc_nodes:
        try:
            all_attrs = calc.base.attributes.all
            calc_label = all_attrs.get('process_label', '')

            wall_time_seconds = None
            try:
                wall_time_seconds = calc.outputs.output_parameters.get_dict().get('wall_time_seconds')
            except Exception:
                pass
            if wall_time_seconds is None:
                try:
                    retrieved = calc.outputs.retrieved
                    output_filename = all_attrs.get('output_filename', 'aiida.out')
                    with retrieved.open(output_filename, 'r') as f:
                        for line in f:
                            if 'WALL' in line and ('QE-EFG' in line or 'PWSCF' in line):
                                wall_time_seconds = _parse_wall_time(line)
                                if wall_time_seconds:
                                    break
                except Exception:
                    pass

            if not wall_time_seconds or wall_time_seconds <= 0:
                continue

            resources = all_attrs.get('resources', {})
            total_cores = resources.get('num_machines', 1) * resources.get('num_mpiprocs_per_machine', 1)
            cpu_hours = (wall_time_seconds / 3600.0) * total_cores
            total_cpu_hours += cpu_hours
            if 'Pw' in calc_label:
                scf_cpu_hours += cpu_hours
            else:
                efg_cpu_hours += cpu_hours
        except Exception:
            continue

    print(f"\nCPU Hours (core-hours) breakdown:")
    print(f"  SCF calculation:  {scf_cpu_hours:8.2f} CPU-h")
    print(f"  EFG calculation:  {efg_cpu_hours:8.2f} CPU-h")
    print(f"  {'-' * 40}")
    print(f"  TOTAL:            {total_cpu_hours:8.2f} CPU-h")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    tensors = workchain.outputs.efg_tensors.get_dict()
    quad = workchain.outputs.quadrupolar_parameters.get_dict()

    print("\nEFG tensors and quadrupolar parameters:")
    print("-" * 60)
    for label in tensors.keys():
        params = quad.get(label, {})
        print(f"\n{label}:")
        if 'Vzz' in params:
            print(f"  Vzz = {params['Vzz']:.4f} (Ha/bohr^2)")
        if 'eta' in params:
            print(f"  eta = {params['eta']:.5f}")
        if 'Cq' in params:
            print(f"  Cq  = {params['Cq']:.4f} MHz")
        if 'nu_Q' in params:
            print(f"  nu_Q = {params['nu_Q']:.4f} MHz")

    import json
    combined = {
        label: {
            'efg_tensor_Ha_bohr2': tensors[label],
            'quadrupolar_parameters': quad.get(label, {}),
        }
        for label in tensors.keys()
    }
    combined['computational_cost'] = {
        'total_cpu_hours': total_cpu_hours,
        'scf_cpu_hours': scf_cpu_hours,
        'efg_cpu_hours': efg_cpu_hours,
        'num_calculations': len(calc_nodes),
    }
    output_file = f'efg_results_{workchain_pk}.json'
    with open(output_file, 'w') as f:
        json.dump(combined, f, indent=2)
    print(f"\nResults exported to: {output_file}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Run or retrieve results from the EFG workflow')
    parser.add_argument('--retrieve', '-r', type=int, metavar='PK',
                        help='Retrieve results from a completed workchain (provide PK)')
    parser.add_argument('--input', '-i', type=str, metavar='FILE',
                        help='Input structure file (.extxyz format)')
    parser.add_argument('--protocol', '-p', type=str,
                        choices=['fast', 'moderate', 'precise'], default='moderate',
                        help="Protocol for parameter selection (default: 'moderate')")
    parser.add_argument('--pseudo-family', '-f', type=str,
                        choices=['gipaw_PBE', 'gipaw_PBEsol'], default='gipaw_PBE',
                        help="Pseudopotential family (default: 'gipaw_PBE')")
    parser.add_argument('--target-atoms', '-t', type=int, nargs='+', default=None, metavar='IDX',
                        help='Zero-based indices of atoms of interest (default: all). Example: -t 0 3 5')
    parser.add_argument('--nuclear-data', '-n', type=str, default=None, metavar='JSON',
                        help='Override Q (1e-30 m^2) and I per element/kind as JSON, '
                             'e.g. \'{"O": {"Q": -2.558, "I": 2.5}}\'')
    parser.add_argument('--spectra', action='store_true', default=False,
                        help='Also simulate quadrupolar powder NMR spectra (needs --larmor)')
    parser.add_argument('--larmor', type=float, default=None, metavar='MHz',
                        help='Larmor frequency nu_L (MHz) for the spectrum simulation')
    args = parser.parse_args()

    if args.retrieve:
        retrieve_results(args.retrieve)
    else:
        if not args.input:
            parser.error('--input/-i is required when not using --retrieve')
        nuclear_data = None
        if args.nuclear_data:
            import json
            nuclear_data = json.loads(args.nuclear_data)
        main(args.input, args.protocol, args.pseudo_family, args.target_atoms,
             nuclear_data, args.spectra, args.larmor)
