"""
AiiDA CalcJob plugin for qe-converse.x

This plugin allows running qe-converse calculations within AiiDA.
"""

from aiida import orm
from aiida.common import datastructures, exceptions
from aiida.engine import CalcJob
from aiida_quantumespresso.calculations import BasePwCpInputGenerator
import os


class QeConverseCalculation(CalcJob):
    """
    AiiDA CalcJob plugin for qe-converse.x calculations.
    """
    
    _DEFAULT_INPUT_FILE = 'aiida.in'
    _DEFAULT_OUTPUT_FILE = 'aiida.out'
    
    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        
        # Input specifications
        spec.input('parameters', valid_type=orm.Dict,
                   help='Input parameters for qe-converse')
        spec.input('parent_folder', valid_type=orm.RemoteData,
                   help='Remote folder from previous SCF calculation')
        spec.input('metadata.options.resources', valid_type=dict, required=True)
        spec.input('metadata.options.withmpi', valid_type=bool, default=True)
        spec.input('metadata.options.input_filename', valid_type=str,
                   default=cls._DEFAULT_INPUT_FILE)
        spec.input('metadata.options.output_filename', valid_type=str,
                   default=cls._DEFAULT_OUTPUT_FILE)
        
        # Output specifications
        spec.output('output_parameters', valid_type=orm.Dict,
                    help='Output parameters parsed from the calculation')
        
        # Exit codes
        spec.exit_code(300, 'ERROR_NO_RETRIEVED_FOLDER',
                      message='The retrieved folder data node could not be accessed')
        spec.exit_code(310, 'ERROR_OUTPUT_FILES',
                      message='The output file could not be read or parsed')
        spec.exit_code(320, 'ERROR_CONVERGENCE',
                      message='The calculation did not converge')
    
    def prepare_for_submission(self, folder):
        """
        Create the input files for the qe-converse calculation.
        
        Args:
            folder: an `aiida.common.folders.Folder` to temporarily write files on disk
            
        Returns:
            `aiida.common.datastructures.CalcInfo` instance
        """
        # Get parameters
        parameters = self.inputs.parameters.get_dict()
        
        # Write input file
        input_filename = self.metadata.options.input_filename
        with folder.open(input_filename, 'w') as handle:
            handle.write(self._generate_input_file(parameters))
        
        # Prepare CalcInfo
        calcinfo = datastructures.CalcInfo()
        calcinfo.uuid = str(self.uuid)
        calcinfo.codes_info = [datastructures.CodeInfo()]
        
        codeinfo = calcinfo.codes_info[0]
        codeinfo.cmdline_params = []
        codeinfo.stdin_name = input_filename
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.withmpi = self.metadata.options.withmpi
        
        # Retrieve list
        calcinfo.retrieve_list = [
            self.metadata.options.output_filename,
        ]
        
        # Local copy list (for outdir from parent calculation)
        calcinfo.remote_symlink_list = []
        if 'parent_folder' in self.inputs:
            parent_folder = self.inputs.parent_folder
            calcinfo.remote_symlink_list.append((
                parent_folder.computer.uuid,
                os.path.join(parent_folder.get_remote_path(), 'out'),
                'out'
            ))
        
        return calcinfo
    
    def _generate_input_file(self, parameters):
        """
        Generate the input file content for qe-converse.
        
        Args:
            parameters: dictionary of input parameters
            
        Returns:
            String content of the input file
        """
        lines = []
        
        # Write input_qeconverse namelist
        if 'input_qeconverse' in parameters:
            params = parameters['input_qeconverse']
        else:
            params = parameters
        
        lines.append('&input_qeconverse')
        
        for key, value in params.items():
            if isinstance(value, bool):
                value_str = '.true.' if value else '.false.'
            elif isinstance(value, str):
                value_str = f"'{value}'"
            elif isinstance(value, list):
                # Handle array parameters
                if key == 'm_0':
                    value_str = f"{value[0]}, {value[1]}, {value[2]}"
                else:
                    value_str = ', '.join(str(v) for v in value)
            else:
                value_str = str(value)
            
            lines.append(f"    {key} = {value_str}")
        
        lines.append('/')
        lines.append('')
        
        return '\n'.join(lines)


class QeConverseParser(orm.Parser):
    """
    Parser for qe-converse.x output files.
    """
    
    def parse(self, **kwargs):
        """
        Parse the output file of a qe-converse calculation.
        """
        try:
            output_folder = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER
        
        # Read output file
        try:
            with output_folder.open(self.node.get_option('output_filename'), 'r') as handle:
                output_text = handle.read()
        except (OSError, IOError):
            return self.exit_codes.ERROR_OUTPUT_FILES
        
        # Parse the output
        result_dict = self._parse_output(output_text)
        
        if result_dict is None:
            return self.exit_codes.ERROR_OUTPUT_FILES
        
        # Set outputs
        self.out('output_parameters', orm.Dict(dict=result_dict))
    
    def _parse_output(self, output_text):
        """
        Parse the output text to extract chemical shift values.
        
        Args:
            output_text: string content of the output file
            
        Returns:
            Dictionary with parsed values
        """
        result = {
            'chemical_shift': [0.0, 0.0, 0.0],
            'converged': False
        }
        
        lines = output_text.split('\n')
        
        for line in lines:
            # Look for chemical shift line
            # Example: "Chemical shift (ppm)     12.345  23.456  34.567"
            if 'Chemical shift (ppm)' in line:
                parts = line.split()
                if len(parts) >= 6:
                    try:
                        result['chemical_shift'] = [
                            float(parts[3]),
                            float(parts[4]),
                            float(parts[5])
                        ]
                    except (ValueError, IndexError):
                        pass
            
            # Check for convergence
            if 'convergence has been achieved' in line.lower() or \
               'convergence achieved' in line.lower():
                result['converged'] = True
        
        return result
