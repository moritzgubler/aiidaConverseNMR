"""
Parser for qe-efg.x output files.

Thin AiiDA wrapper around :func:`efg_parsing.parse_efg_output`; all the actual
text parsing lives in the AiiDA-independent ``efg_parsing`` module so it can be
unit-tested without a profile.
"""

from aiida import orm
from aiida.parsers import Parser
from aiida.common import exceptions

from .efg_parsing import parse_efg_output


class QeEfgParser(Parser):
    """Parser for qe-efg.x output files."""

    def parse(self, **kwargs):
        """Parse the output file of a qe-efg calculation."""
        try:
            output_folder = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        output_filename = self.node.get_option('output_filename')
        try:
            with output_folder.open(output_filename, 'r') as handle:
                output_text = handle.read()
        except (OSError, IOError):
            return self.exit_codes.ERROR_OUTPUT_FILES

        result_dict = parse_efg_output(output_text)

        if result_dict is None:
            return self.exit_codes.ERROR_OUTPUT_FILES

        for warning in result_dict.get('warnings', []):
            self.logger.warning(warning)

        if not result_dict.get('converged', False):
            self.out('output_parameters', orm.Dict(dict=result_dict))
            return self.exit_codes.ERROR_OUTPUT_INCOMPLETE

        self.out('output_parameters', orm.Dict(dict=result_dict))
        return None  # success
