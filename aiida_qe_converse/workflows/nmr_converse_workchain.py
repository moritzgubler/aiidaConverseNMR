"""
AiiDA WorkChain for computing NMR chemical shifts using the converse approach.

This workchain performs:
1. SCF calculation with Quantum ESPRESSO (with -k symmetry disabled)
2. Multiple qe-converse calculations for each atom in x, y, z directions
3. Computes isotropic shielding for each atom

Author: Generated for AiiDA workflow
"""

from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction
from aiida_quantumespresso.workflows.pw.base import PwBaseWorkChain
from aiida_quantumespresso.common.types import ElectronicType
from .qeconverse_base import QeConverseBaseWorkChain
import numpy as np


@calcfunction
def compute_isotropic_shielding(tensor_data_dict):
    """
    Compute isotropic shielding from full chemical shift tensors.
    
    Args:
        tensor_data_dict: Dictionary with 3x3 tensors for each atom
                         Format: {atom_label: [[xx,xy,xz], [yx,yy,yz], [zx,zy,zz]]}
    
    Returns:
        Dictionary with tensor components and isotropic shielding values
    """
    results = {}
    tensor_dict = tensor_data_dict.get_dict()
    
    for atom_label, tensor in tensor_dict.items():
        trace = tensor[0][0] + tensor[1][1] + tensor[2][2]
        isotropic = trace / 3.0
        
        results[atom_label] = {
            # 'absolute_shift_tensor_ppm': tensor,  # Full 3x3 tensor
            'isotropic_shielding_ppm': isotropic,
            # Optionally add anisotropy, asymmetry, etc.
        }
    
    return orm.Dict(dict=results)


class NmrConverseWorkChain(WorkChain):
    """
    WorkChain for computing NMR chemical shifts using the converse approach.
    """
    
    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        
        # Input specifications
        spec.input('structure', valid_type=orm.StructureData,
                   help='Crystal structure for the calculation')
        spec.input('pw_code', valid_type=orm.Code,
                   help='Code for pw.x (Quantum ESPRESSO)')
        spec.input('converse_code', valid_type=orm.Code,
                   help='Code for qe-converse.x')
        spec.input('scf_parameters', valid_type=orm.Dict,
                   help='Parameters for the SCF calculation')
        spec.input('converse_parameters', valid_type=orm.Dict,
                   help='Base parameters for converse calculations')
        # spec.input('pseudos', valid_type=dict,
        spec.input('pseudos', valid_type=orm.Dict,
                   help='Dictionary mapping element symbols to pseudopotential nodes')
        spec.input('target_atoms', valid_type=orm.List,
                   help='List of atom indices (0-based) to compute chemical shifts for')
        spec.input('options', valid_type=orm.Dict,
                   help='Computational resources (num_machines, num_mpiprocs_per_machine, etc.)')
        spec.input('q_gipaw', valid_type=orm.Float, required=False, default=lambda: orm.Float(0.01),
                   help='GIPAW q parameter')
        spec.input('kpoints_distance', valid_type=orm.Float,
           help='K-points distance in inverse Angstrom (e.g., 0.15)')
        spec.input('mixing_beta', valid_type=orm.Float, required=False, default=lambda: orm.Float(0.5),
                   help='Mixing beta parameter for converse')
        spec.input('dudk_method', valid_type=orm.Str, required=False, default=lambda: orm.Str('covariant'),
                   help='dudk method (covariant or kdotp)')
        spec.input('dudk_in_memory', valid_type=orm.Bool, required=False, default=lambda: orm.Bool(True),
                   help='Whether to keep du/dk in memory (default: True)')
        spec.input('electronic_type', valid_type=orm.Str, required=False, default=lambda: orm.Str('METAL'),
                   help='Electronic type: METAL, INSULATOR, or UNKNOWN (default: METAL)')

        # Outline
        spec.outline(
            cls.setup,
            cls.run_scf,
            cls.inspect_scf,
            cls.run_converse_calculations,
            cls.inspect_converse,
            cls.compute_results,
            cls.finalize
        )
        
        # Output specifications
        spec.output('scf_remote_folder', valid_type=orm.RemoteData,
                    help='Remote folder containing SCF results')
        spec.output('absolute_shift_tensor_ppm', valid_type=orm.Dict,
                    help='Chemical shift tensor components for each atom')
        spec.output('isotropic_shielding_ppm', valid_type=orm.Dict,
                    help='Isotropic shielding values for each atom')
        
        # Exit codes
        spec.exit_code(300, 'ERROR_SCF_FAILED',
                      message='SCF calculation failed')
        spec.exit_code(301, 'ERROR_CONVERSE_FAILED',
                      message='One or more converse calculations failed')
        spec.exit_code(302, 'ERROR_PARSING_FAILED',
                      message='Failed to parse chemical shift values')

    @classmethod
    def get_builder_from_protocol(
        cls,
        pw_code,
        converse_code,
        structure,
        protocol='moderate',
        pseudo_family='gipaw',
        target_atoms=None,
        electronic_type=None,
        overrides=None,
        **kwargs
    ):
        """
        Return a builder with inputs set according to the specified protocol.

        Args:
            pw_code: Code for pw.x (Quantum ESPRESSO)
            converse_code: Code for qe-converse.x
            structure: StructureData node
            protocol: Protocol to use ('fast', 'moderate', 'precise')
            pseudo_family: Label of the pseudopotential family to use
            target_atoms: List of atom indices (0-based) to compute shifts for.
                         If None, computes for all atoms.
            electronic_type: ElectronicType enum (METAL, INSULATOR, or UNKNOWN).
                            Defaults to METAL if not specified.
            overrides: Dict with override parameters for specific inputs
            **kwargs: Additional inputs to override

        Returns:
            ProcessBuilder for NmrConverseWorkChain
        """
        from aiida.orm import QueryBuilder, Group

        # Protocol definitions
        protocols = {
            'fast': {
                'ecutwfc': 40.0,
                'kpoints_distance': 0.5,
                'conv_thr': 1.0e-8,
                'mixing_beta': 0.2,
                'q_gipaw': 0.01,
                'num_machines': 1,
                'num_mpiprocs_per_machine': 8,
                'max_wallclock_seconds': 3600 * 23,
                'max_memory_kb': 16000000,
            },
            'moderate': {
                'ecutwfc': 60.0,
                'kpoints_distance': 0.25,
                'conv_thr': 1.0e-9,
                'mixing_beta': 0.2,
                'q_gipaw': 0.01,
                'num_machines': 1,
                'num_mpiprocs_per_machine': 16,
                'max_wallclock_seconds': 3600 * 23,
                'max_memory_kb': 32000000,
            },
            'precise': {
                'ecutwfc': 80.0,
                'kpoints_distance': 0.15,
                'conv_thr': 1.0e-9,
                'mixing_beta': 0.2,
                'q_gipaw': 0.01,
                'num_machines': 1,
                'num_mpiprocs_per_machine': 32,
                'max_wallclock_seconds': 3600 * 23,
                'max_memory_kb': 64000000,
            }
        }

        if protocol not in protocols:
            raise ValueError(f"Unknown protocol '{protocol}'. Choose from: {list(protocols.keys())}")

        proto = protocols[protocol]

        # Apply overrides if provided
        if overrides:
            proto.update(overrides)

        # Get pseudopotentials
        pseudos = {}
        for kind in structure.get_kind_names():
            qb = QueryBuilder()
            qb.append(Group, filters={'label': pseudo_family}, tag='group')
            # qb.append(orm.UpfData, with_group='group',
            #           filters={'attributes.element': kind})
            from aiida_pseudo.data.pseudo.upf import UpfData
            qb.append(UpfData, with_group='group',
                    filters={'attributes.element': kind})

            results = qb.all()

            if results:
                pseudos[kind] = results[0][0].pk
            else:
                raise ValueError(f"No pseudo found for element {kind} in family '{pseudo_family}'")

        # Handle electronic type - default to METAL if not specified
        if electronic_type is None:
            electronic_type = ElectronicType.METAL
        elif isinstance(electronic_type, str):
            electronic_type = ElectronicType(electronic_type)

        # Set degauss based on electronic type
        if electronic_type == ElectronicType.INSULATOR:
            degauss = 1e-8
        else:  # METAL or UNKNOWN
            degauss = 1e-2

        # Prepare SCF parameters
        scf_parameters = {
            'CONTROL': {
                'calculation': 'scf',
                'restart_mode': 'from_scratch',
                'verbosity': 'high',
            },
            'SYSTEM': {
                'ecutwfc': proto['ecutwfc'],
                'occupations': 'smearing',
                'smearing': 'gaussian',
                'degauss': degauss,
                'nosym': True,  # CRITICAL: Disable symmetry for NMR
                'noinv': True,  # CRITICAL: Disable inversion symmetry
            },
            'ELECTRONS': {
                'conv_thr': proto['conv_thr'],
                'mixing_beta': proto['mixing_beta'],
            },
        }

        # Prepare converse parameters
        converse_parameters = {
            'mixing_beta': proto['mixing_beta']
        }

        # Prepare computational options
        options = {
            'resources': {
                'num_machines': proto['num_machines'],
                'num_mpiprocs_per_machine': proto['num_mpiprocs_per_machine'],
            },
            'max_wallclock_seconds': proto['max_wallclock_seconds'],
            'max_memory_kb': proto['max_memory_kb'],
        }

        # Add queue_name if provided in overrides or kwargs
        queue_name = kwargs.get('queue_name') or (overrides or {}).get('queue_name')
        if queue_name:
            options['queue_name'] = queue_name

        # Determine target atoms
        if target_atoms is None:
            target_atoms = list(range(len(structure.sites)))

        # Build the inputs
        builder = cls.get_builder()
        builder.structure = structure
        builder.pw_code = pw_code
        builder.converse_code = converse_code
        builder.scf_parameters = orm.Dict(dict=scf_parameters)
        builder.converse_parameters = orm.Dict(dict=converse_parameters)
        builder.pseudos = orm.Dict(dict=pseudos)
        builder.target_atoms = orm.List(list=target_atoms)
        builder.options = orm.Dict(dict=options)
        builder.kpoints_distance = orm.Float(proto['kpoints_distance'])
        builder.q_gipaw = orm.Float(proto['q_gipaw'])
        builder.mixing_beta = orm.Float(proto['mixing_beta'])
        builder.dudk_method = orm.Str(kwargs.get('dudk_method', 'covariant'))
        builder.dudk_in_memory = orm.Bool(kwargs.get('dudk_in_memory', True))
        builder.electronic_type = orm.Str(electronic_type.value)

        return builder

    def setup(self):
        """Initialize the workchain."""
        self.report('Setting up NMR converse workchain')
        
        # Get structure information
        structure = self.inputs.structure
        self.ctx.num_sites = len(structure.sites)
        
        # Get target atoms
        target_atoms = self.inputs.target_atoms.get_list()
        self.ctx.target_atoms = target_atoms
        self.ctx.directions = ['x', 'y', 'z']
        
        # Get atom labels for each target
        self.ctx.atom_labels = []
        for idx in target_atoms:
            site = structure.sites[idx]
            kind_name = site.kind_name
            self.ctx.atom_labels.append(f"{kind_name}{idx+1}")
        
        self.report(f'Will compute chemical shifts for {len(target_atoms)} atoms')
        self.report(f'Target atoms: {self.ctx.atom_labels}')
    
    def run_scf(self):
        """Run the SCF calculation with -k symmetry disabled."""
        self.report('Submitting SCF calculation')

        pseudo_dict = self.inputs.pseudos.get_dict()
        pseudos = {kind: orm.load_node(pk) for kind, pk in pseudo_dict.items()}
        
        # Prepare inputs for PwBaseWorkChain
        inputs = {
            'pw': {
                'code': self.inputs.pw_code,
                'structure': self.inputs.structure,
                'parameters': self.inputs.scf_parameters,
                'pseudos': pseudos,
                'metadata': {
                    'options': self.inputs.options.get_dict(),
                }
            },
            'kpoints_distance': self.inputs.kpoints_distance,
        }
        
        # Submit the calculation
        running = self.submit(PwBaseWorkChain, **inputs)
        self.report(f'Submitted SCF calculation <{running.pk}>')
        
        return ToContext(scf_calc=running)
    
    def inspect_scf(self):
        """Check if the SCF calculation completed successfully."""
        if not self.ctx.scf_calc.is_finished_ok:
            self.report('SCF calculation failed')
            return self.exit_codes.ERROR_SCF_FAILED
        
        self.report('SCF calculation completed successfully')
        
        # Get the remote folder for use in converse calculations
        self.ctx.scf_remote_folder = self.ctx.scf_calc.outputs.remote_folder
        
        # Store for output
        self.out('scf_remote_folder', self.ctx.scf_remote_folder)
    
    def run_converse_calculations(self):
        """Submit all converse calculations for each atom and direction."""
        self.report('Submitting converse calculations')
        
        base_params = self.inputs.converse_parameters.get_dict()
        
        # Get prefix from SCF parameters (usually 'aiida')
        scf_params = self.inputs.scf_parameters.get_dict()
        prefix = scf_params.get('CONTROL', {}).get('prefix', 'aiida')
        
        converse_calcs = {}
        
        for atom_idx, atom_label in zip(self.ctx.target_atoms, self.ctx.atom_labels):
            for dir_idx, direction in enumerate(self.ctx.directions):
                
                # Prepare converse parameters
                params = base_params.copy()
                params['prefix'] = prefix
                params['outdir'] = './out/'
                params['q_gipaw'] = self.inputs.q_gipaw.value
                params['dudk_method'] = self.inputs.dudk_method.value
                params['dudk_in_memory'] = self.inputs.dudk_in_memory.value
                params['mixing_beta'] = self.inputs.mixing_beta.value
                params['verbosity'] = 'high'
                params['diagonalization'] = 'david'
                
                # Set magnetic field direction (1-indexed in the code)
                params['m_0'] = [0.0, 0.0, 0.0]
                params['m_0'][dir_idx] = 1.0
                params['m_0_atom'] = atom_idx + 1  # 1-indexed
                
                # Set lambda_so to zero (can be customized if needed)
                params['lambda_so'] = [0.0]
                params['delete_dudk_files'] = True
                
                # Create the input dictionary for QeConverseBaseWorkChain
                inputs = {
                    'qeconverse': {
                        'code': self.inputs.converse_code,
                        'parameters': orm.Dict(dict={'input_qeconverse': params}),
                        'parent_folder': self.ctx.scf_remote_folder,
                        'metadata': {
                            'options': self.inputs.options.get_dict(),
                            'label': f'converse_{atom_label}_{direction}',
                            'description': f'Converse calculation for atom {atom_label} in {direction} direction'
                        }
                    }
                }
                
                # Submit calculation using QeConverseBaseWorkChain for error handling
                calc_label = f'{atom_label}_{direction}'
                running = self.submit(QeConverseBaseWorkChain, **inputs)
                converse_calcs[calc_label] = running
                
                self.report(f'Submitted converse calculation for {atom_label} ({direction}) <{running.pk}>')
        
        return ToContext(**converse_calcs)
    
    def inspect_converse(self):
        """Check if all converse calculations completed successfully."""
        self.report('Inspecting converse calculations')
        
        failed = []
        for atom_label in self.ctx.atom_labels:
            for direction in self.ctx.directions:
                calc_label = f'{atom_label}_{direction}'
                calc = self.ctx[calc_label]
                
                if not calc.is_finished_ok:
                    failed.append(calc_label)
                    self.report(f'Converse calculation {calc_label} failed')
        
        if failed:
            self.report(f'Failed calculations: {failed}')
            return self.exit_codes.ERROR_CONVERSE_FAILED
        
        self.report('All converse calculations completed successfully')
    
    def compute_results(self):
        """Parse results and build full chemical shift tensor."""
        self.report('Computing chemical shifts and isotropic shielding')

        # Build full 3x3 tensor for each atom
        chemical_shift_tensors = {}

        for atom_label in self.ctx.atom_labels:
            tensor = [[0.0, 0.0, 0.0],  # Row 0: σ_xx, σ_xy, σ_xz
                      [0.0, 0.0, 0.0],  # Row 1: σ_yx, σ_yy, σ_yz
                      [0.0, 0.0, 0.0]]  # Row 2: σ_zx, σ_zy, σ_zz

            for dir_idx, direction in enumerate(self.ctx.directions):
                calc_label = f'{atom_label}_{direction}'
                calc = self.ctx[calc_label]

                try:
                    output_params = calc.outputs.output_parameters.get_dict()

                    # Check if the calculation converged and chemical shift was set
                    converged = output_params.get('converged', False)
                    if not converged:
                        warnings = output_params.get('warnings', [])
                        self.report(f'Chemical shift parsing failed for {calc_label}. Converged: {converged}')
                        self.report(f'Warnings: {warnings}')
                        return self.exit_codes.ERROR_PARSING_FAILED

                    column = output_params.get('chemical_shift', [0, 0, 0])

                    # column contains [σ_x?, σ_y?, σ_z?] where ? is the current direction
                    for row_idx in range(3):
                        tensor[row_idx][dir_idx] = column[row_idx]

                except (AttributeError, KeyError) as e:
                    self.report(f'Failed to parse output for {calc_label}: {e}')
                    return self.exit_codes.ERROR_PARSING_FAILED

            chemical_shift_tensors[atom_label] = tensor

        # Store full tensors
        tensors_node = orm.Dict(dict=chemical_shift_tensors).store()
        self.out('absolute_shift_tensor_ppm', tensors_node)

        # Compute isotropic shielding
        isotropic = compute_isotropic_shielding(tensors_node)
        self.out('isotropic_shielding_ppm', isotropic)
    
    def finalize(self):
        """Finalize the workchain."""
        self.report('NMR converse workchain completed successfully')
        
        # Print summary
        isotropic_dict = self.node.outputs.isotropic_shielding_ppm.get_dict()
        self.report('Isotropic shielding values:')
        for atom_label, values in isotropic_dict.items():
            self.report(f"  {atom_label}: {values['isotropic_shielding_ppm']:.3f} ppm")
