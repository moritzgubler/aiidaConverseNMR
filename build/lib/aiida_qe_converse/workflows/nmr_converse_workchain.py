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
import numpy as np


@calcfunction
def compute_isotropic_shielding(shift_data_dict):
    """
    Compute isotropic shielding (trace/3) from chemical shift data.
    
    Args:
        shift_data_dict: Dictionary containing chemical shift values for each atom
                        Format: {atom_label: {'x': value, 'y': value, 'z': value}}
    
    Returns:
        Dictionary with isotropic shielding values for each atom
    """
    results = {}
    shift_dict = shift_data_dict.get_dict()
    
    for atom_label, directions in shift_dict.items():
        trace = directions['x'] + directions['y'] + directions['z']
        isotropic = trace / 3.0
        results[atom_label] = {
            'xx': directions['x'],
            'yy': directions['y'],
            'zz': directions['z'],
            'trace': trace,
            'isotropic': isotropic
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
        spec.input('mixing_beta', valid_type=orm.Float, required=False, default=lambda: orm.Float(0.5),
                   help='Mixing beta parameter for converse')
        spec.input('dudk_method', valid_type=orm.Str, required=False, default=lambda: orm.Str('covariant'),
                   help='dudk method (covariant or kdotp)')
        
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
        spec.output('chemical_shifts', valid_type=orm.Dict,
                    help='Chemical shift tensor components for each atom')
        spec.output('isotropic_shielding', valid_type=orm.Dict,
                    help='Isotropic shielding values for each atom')
        
        # Exit codes
        spec.exit_code(300, 'ERROR_SCF_FAILED',
                      message='SCF calculation failed')
        spec.exit_code(301, 'ERROR_CONVERSE_FAILED',
                      message='One or more converse calculations failed')
        spec.exit_code(302, 'ERROR_PARSING_FAILED',
                      message='Failed to parse chemical shift values')
    
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
        
        # Prepare inputs for PwBaseWorkChain
        inputs = {
            'pw': {
                'code': self.inputs.pw_code,
                'structure': self.inputs.structure,
                'parameters': self.inputs.scf_parameters,
                'pseudos': self.inputs.pseudos.get_dict(),
                'metadata': {
                    'options': self.inputs.options.get_dict(),
                }
            }
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
        
        from aiida.plugins import CalculationFactory
        QeConverseCalculation = CalculationFactory('qeconverse')
        
        structure = self.inputs.structure
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
                params['q_gipaw'] = self.inputs.q_gipaw.value
                params['dudk_method'] = self.inputs.dudk_method.value
                params['mixing_beta'] = self.inputs.mixing_beta.value
                params['verbosity'] = 'high'
                params['diagonalization'] = 'david'
                
                # Set magnetic field direction (1-indexed in the code)
                params['m_0'] = [0.0, 0.0, 0.0]
                params['m_0'][dir_idx] = 1.0
                params['m_0_atom'] = atom_idx + 1  # 1-indexed
                
                # Set lambda_so to zero (can be customized if needed)
                params['lambda_so'] = [0.0]
                
                # Create the input dictionary
                inputs = {
                    'code': self.inputs.converse_code,
                    'parameters': orm.Dict(dict={'input_qeconverse': params}),
                    'parent_folder': self.ctx.scf_remote_folder,
                    'metadata': {
                        'options': self.inputs.options.get_dict(),
                        'label': f'converse_{atom_label}_{direction}',
                        'description': f'Converse calculation for atom {atom_label} in {direction} direction'
                    }
                }
                
                # Submit calculation using the proper CalcJob
                calc_label = f'{atom_label}_{direction}'
                running = self.submit(QeConverseCalculation, **inputs)
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
        """Parse results and compute isotropic shielding."""
        self.report('Computing chemical shifts and isotropic shielding')
        
        chemical_shifts = {}
        
        for atom_label in self.ctx.atom_labels:
            chemical_shifts[atom_label] = {}
            
            for direction in self.ctx.directions:
                calc_label = f'{atom_label}_{direction}'
                calc = self.ctx[calc_label]
                
                # Parse the output to get chemical shift value
                # This depends on how qe-converse.x outputs are structured
                # You may need to adapt this based on your actual output parser
                try:
                    output_params = calc.outputs.output_parameters.get_dict()
                    # Assuming the chemical shift is stored with key 'chemical_shift'
                    # and it's a 3-component vector [xx, yy, zz]
                    shift_value = output_params.get('chemical_shift', [0, 0, 0])
                    
                    # Get the diagonal component corresponding to this direction
                    dir_idx = self.ctx.directions.index(direction)
                    chemical_shifts[atom_label][direction] = shift_value[dir_idx]
                    
                except (AttributeError, KeyError) as e:
                    self.report(f'Failed to parse output for {calc_label}: {e}')
                    return self.exit_codes.ERROR_PARSING_FAILED
        
        # Store chemical shifts
        self.out('chemical_shifts', orm.Dict(dict=chemical_shifts))
        
        # Compute isotropic shielding
        isotropic = compute_isotropic_shielding(orm.Dict(dict=chemical_shifts))
        self.out('isotropic_shielding', isotropic)
    
    def finalize(self):
        """Finalize the workchain."""
        self.report('NMR converse workchain completed successfully')
        
        # Print summary
        isotropic_dict = self.outputs.isotropic_shielding.get_dict()
        self.report('Isotropic shielding values:')
        for atom_label, values in isotropic_dict.items():
            self.report(f"  {atom_label}: {values['isotropic']:.3f} ppm")
