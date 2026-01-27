"""
Parser for qe-converse.x output files.
"""

from aiida import orm
from aiida.parsers import Parser
from aiida.common import exceptions
import numpy as np


class QeConverseParser(Parser):
    """
    Parser for qe-converse.x output files.
    
    This class extracts chemical shift information from the output.
    """
    
    def parse(self, **kwargs):
        """
        Parse the output file of a qe-converse calculation.
        
        Returns:
            Exit code indicating success or failure
        """
        # Get the retrieved folder
        try:
            output_folder = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER
        
        # Read output file
        output_filename = self.node.get_option('output_filename')
        try:
            with output_folder.open(output_filename, 'r') as handle:
                output_text = handle.read()
        except (OSError, IOError):
            return self.exit_codes.ERROR_OUTPUT_FILES
        
        # Parse the output
        result_dict = self._parse_output(output_text)
        
        if result_dict is None:
            return self.exit_codes.ERROR_OUTPUT_FILES
        
        # Check if output seems incomplete
        if not result_dict.get('converged', False):
            self.logger.warning('Calculation may not have converged properly')
        
        if result_dict.get('chemical_shift') == [0.0, 0.0, 0.0]:
            self.logger.warning('Chemical shift values are all zero - check output')
        
        # Set outputs
        self.out('output_parameters', orm.Dict(dict=result_dict))
        
        return None  # Success
    
    def _parse_output(self, output_text):
        """
        Parse the output text to extract chemical shift values.
        
        Args:
            output_text: string content of the output file
            
        Returns:
            Dictionary with parsed values
        """
        result = {
            'chemical_shift': [np.nan, np.nan, np.nan],
            'converged': False,
            'warnings': []
        }

        chemical_shift_set = False
        
        lines = output_text.split('\n')
        
        for i, line in enumerate(lines):
            # Look for chemical shift line
            # Example format: "Chemical shift (ppm)     12.345  23.456  34.567"
            if 'Chemical shift (ppm)' in line or 'chemical shift (ppm)' in line.lower():
                parts = line.split()
                # Find the numerical values (should be last 3 elements)
                try:
                    # Try to find 3 consecutive numbers
                    numbers = []
                    for part in parts:
                        try:
                            num = float(part)
                            numbers.append(num)
                        except ValueError:
                            continue
                    
                    if len(numbers) >= 3:
                        # Take the last 3 numbers
                        result['chemical_shift'] = numbers[-3:]
                        chemical_shift_set = True
                        result['converged'] = True
                except (ValueError, IndexError) as e:
                    result['warnings'].append(f'Could not parse chemical shift: {e}')
            
            # Check for convergence messages
            convergence_indicators = [
                'convergence has been achieved',
                'convergence achieved',
                'convergence reached',
                'scf convergence',
            ]
            for indicator in convergence_indicators:
                if indicator in line.lower():
                    result['converged'] = True
                    break
            
            # Check for errors
            error_indicators = [
                'error',
                'failed',
                'stop',
                'abort',
            ]
            for indicator in error_indicators:
                if indicator in line.lower() and 'convergence' not in line.lower():
                    result['warnings'].append(f'Possible error in line {i}: {line.strip()}')
        
        if not chemical_shift_set:
            result['converged'] = False
            result["warnings"].append("Chemical shift has not been set.!!!")
        
        return result
