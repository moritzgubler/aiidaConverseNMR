"""
AiiDA CalcJob plugin for qe-efg.x

``qe-efg.x`` computes the electric field gradient (EFG) tensor and NMR/NQR
quadrupolar parameters from a converged pw.x SCF.  Like ``qe-converse.x`` it
reads a Fortran namelist on stdin and symlinks the SCF ``out/`` directory, but
the namelist is ``&input_qeefg`` with the per-species arrays ``q_efg``/``i_efg``.
It is a single ground-state post-processing step (no converse SCF), so one run
returns the full tensor for every atom at once.
"""

from aiida import orm
from aiida.common import datastructures
from aiida.engine import CalcJob
import os


class QeEfgCalculation(CalcJob):
    """AiiDA CalcJob plugin for qe-efg.x calculations."""

    _DEFAULT_INPUT_FILE = 'aiida.in'
    _DEFAULT_OUTPUT_FILE = 'aiida.out'
    _DEFAULT_PARENT_FOLDER_NAME = 'out'

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)

        spec.input('parameters', valid_type=orm.Dict,
                   help='Input parameters for qe-efg (wrapped in an `input_qeefg` namelist)')
        spec.input('parent_folder', valid_type=orm.RemoteData,
                   help='Remote folder from the previous SCF calculation')
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

        spec.output('output_parameters', valid_type=orm.Dict, required=True,
                    help='Parsed EFG tensors and quadrupolar parameters')

        spec.inputs['metadata']['options']['parser_name'].default = 'qeefg'

        # Exit codes (mirror the converse CalcJob conventions)
        spec.exit_code(300, 'ERROR_NO_RETRIEVED_FOLDER',
                       message='The retrieved folder data node could not be accessed')
        spec.exit_code(310, 'ERROR_OUTPUT_FILES',
                       message='The output file could not be read or parsed')
        spec.exit_code(320, 'ERROR_CONVERGENCE',
                       message='The calculation did not converge')
        spec.exit_code(330, 'ERROR_OUTPUT_INCOMPLETE',
                       message='The output file is incomplete or missing expected content')

    def prepare_for_submission(self, folder):
        """Create the input files and the CalcInfo for the qe-efg calculation."""
        parameters = self.inputs.parameters.get_dict()

        input_filename = self.metadata.options.input_filename
        with folder.open(input_filename, 'w') as handle:
            handle.write(self._generate_input_file(parameters))

        calcinfo = datastructures.CalcInfo()
        calcinfo.uuid = str(self.uuid)

        calcinfo.codes_info = [datastructures.CodeInfo()]
        codeinfo = calcinfo.codes_info[0]
        codeinfo.cmdline_params = []
        codeinfo.stdin_name = input_filename
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.withmpi = self.metadata.options.withmpi

        calcinfo.retrieve_list = [
            self.metadata.options.output_filename,
        ]

        # Symlink the SCF out/ directory (same mechanism as the converse calc)
        calcinfo.remote_symlink_list = []
        if 'parent_folder' in self.inputs:
            parent_folder = self.inputs.parent_folder
            parent_folder_name = self.metadata.options.parent_folder_name
            calcinfo.remote_symlink_list.append((
                parent_folder.computer.uuid,
                os.path.join(parent_folder.get_remote_path(), parent_folder_name),
                parent_folder_name
            ))

        return calcinfo

    def _generate_input_file(self, parameters):
        """Generate the ``&input_qeefg`` Fortran namelist.

        ``q_efg`` and ``i_efg`` are per-atom-type arrays; written as
        comma-separated values they map to ``q_efg(1), q_efg(2), ...`` in the
        order of the ATOMIC_SPECIES card, which is exactly what ``qe-efg.x``
        expects.
        """
        if 'input_qeefg' in parameters:
            params = parameters['input_qeefg']
        else:
            params = parameters

        lines = ['&input_qeefg']
        for key, value in params.items():
            if isinstance(value, bool):
                value_str = '.true.' if value else '.false.'
            elif isinstance(value, str):
                value_str = f"'{value}'"
            elif isinstance(value, (list, tuple)):
                value_str = ', '.join(str(v) for v in value)
            else:
                value_str = str(value)
            lines.append(f"    {key} = {value_str}")
        lines.append('/')
        lines.append('')

        return '\n'.join(lines)
