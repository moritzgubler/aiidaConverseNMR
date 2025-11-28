"""
AiiDA CalcJob plugin for qe-converse.x

This plugin tells AiiDA how to run qe-converse calculations.
"""

from aiida import orm
from aiida.common import datastructures, exceptions
from aiida.engine import CalcJob
import os


class QeConverseCalculation(CalcJob):
    """
    AiiDA CalcJob plugin for qe-converse.x calculations.
    
    This class defines how to:
    1. Prepare input files
    2. Run the calculation
    3. Retrieve output files
    """
    
    _DEFAULT_INPUT_FILE = 'aiida.in'
    _DEFAULT_OUTPUT_FILE = 'aiida.out'
    _DEFAULT_PARENT_FOLDER_NAME = 'out'
    
    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        
        # Input specifications
        spec.input('parameters', valid_type=orm.Dict,
                   help='Input parameters for qe-converse')
        spec.input('parent_folder', valid_type=orm.RemoteData,
                   help='Remote folder from previous SCF calculation')
        spec.input('metadata.options.resources', valid_type=dict, required=True,
                   help='Computational resources')
        spec.input('metadata.options.withmpi', valid_type=bool, default=True,
                   help='Run with MPI')
        spec.input('metadata.options.input_filename', valid_type=str,
                   default=cls._DEFAULT_INPUT_FILE,
                   help='Name of input file')
        spec.input('metadata.options.output_filename', valid_type=str,
                   default=cls._DEFAULT_OUTPUT_FILE,
                   help='Name of output file')
        spec.input('metadata.options.parent_folder_name', valid_type=str,
                   default=cls._DEFAULT_PARENT_FOLDER_NAME,
                   help='Name of parent folder to symlink (usually "out")')
        
        # Output specifications
        spec.output('output_parameters', valid_type=orm.Dict, required=True,
                    help='Output parameters parsed from the calculation')
        
        # Default parser
        spec.inputs['metadata']['options']['parser_name'].default = 'qeconverse'
        
        # Exit codes
        spec.exit_code(300, 'ERROR_NO_RETRIEVED_FOLDER',
                      message='The retrieved folder data node could not be accessed')
        spec.exit_code(310, 'ERROR_OUTPUT_FILES',
                      message='The output file could not be read or parsed')
        spec.exit_code(320, 'ERROR_CONVERGENCE',
                      message='The calculation did not converge')
        spec.exit_code(330, 'ERROR_OUTPUT_INCOMPLETE',
                      message='The output file is incomplete or missing expected content')
    
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
        
        # Code information
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
    
        # COPY parent folder instead of symlink (qe-converse writes to outdir)
        calcinfo.remote_copy_list = []
        if 'parent_folder' in self.inputs:
            parent_folder = self.inputs.parent_folder
            parent_folder_name = self.metadata.options.parent_folder_name
            calcinfo.remote_copy_list.append((
                parent_folder.computer.uuid,
                os.path.join(parent_folder.get_remote_path(), parent_folder_name),
                parent_folder_name
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
        
        # Get parameters from input_qeconverse namelist
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
                if key == 'm_0' or key == 'lambda_so':
                    # Write as comma-separated values
                    value_str = ', '.join(str(v) for v in value)
                else:
                    value_str = ', '.join(str(v) for v in value)
            else:
                value_str = str(value)
            
            lines.append(f"    {key} = {value_str}")
        
        lines.append('/')
        lines.append('')
        
        return '\n'.join(lines)
