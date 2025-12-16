# -*- coding: utf-8 -*-
"""Workchain to run a qe-converse.x calculation with automated error handling and restarts."""
from aiida import orm
from aiida.common import AttributeDict
from aiida.engine import BaseRestartWorkChain, ExitCode, ProcessHandlerReport, process_handler, while_
from aiida.plugins import CalculationFactory

QeConverseCalculation = CalculationFactory('qeconverse')


class QeConverseBaseWorkChain(BaseRestartWorkChain):
    """Workchain to run a qe-converse.x calculation with automated error handling and restarts."""

    _process_class = QeConverseCalculation

    defaults = AttributeDict({
        'delta_factor_max_seconds': 0.95,
        'delta_factor_mixing_beta': 0.8,
    })

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        spec.expose_inputs(QeConverseCalculation, namespace='qeconverse')

        spec.outline(
            cls.setup,
            while_(cls.should_run_process)(
                cls.prepare_process,
                cls.run_process,
                cls.inspect_process,
            ),
            cls.results,
        )

        spec.expose_outputs(QeConverseCalculation)

        spec.exit_code(300, 'ERROR_UNRECOVERABLE_FAILURE',
            message='The calculation failed with an unidentified unrecoverable error.')
        spec.exit_code(310, 'ERROR_KNOWN_UNRECOVERABLE_FAILURE',
            message='The calculation failed with a known unrecoverable error.')
        spec.exit_code(320, 'ERROR_INITIALIZATION_CALCULATION_FAILED',
            message='The initialization calculation failed.')
        spec.exit_code(710, 'WARNING_CONVERGENCE_NOT_REACHED',
            message='The calculation did not reach convergence, but may be usable.')

    def setup(self):
        """Call the ``setup`` of the ``BaseRestartWorkChain`` and create the inputs dictionary in ``self.ctx.inputs``.

        This ``self.ctx.inputs`` dictionary will be used by the ``BaseRestartWorkChain`` to submit the calculations
        in the internal loop.

        The ``parameters`` and ``settings`` input ``Dict`` nodes are converted into a regular dictionary.
        """
        super().setup()
        self.ctx.inputs = AttributeDict(self.exposed_inputs(QeConverseCalculation, 'qeconverse'))

        # Convert parameters to dictionary for easier manipulation
        if 'parameters' in self.ctx.inputs:
            self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
            # Ensure input_qeconverse namelist exists
            if 'input_qeconverse' not in self.ctx.inputs.parameters:
                params = self.ctx.inputs.parameters.copy()
                self.ctx.inputs.parameters = {'input_qeconverse': params}

    def prepare_process(self):
        """Prepare the inputs for the next calculation."""
        max_wallclock_seconds = self.ctx.inputs.metadata.options.get('max_wallclock_seconds', None)

        if max_wallclock_seconds is not None:
            # Set max_seconds to a fraction of max_wallclock_seconds to allow graceful shutdown
            max_seconds = max_wallclock_seconds * self.defaults.delta_factor_max_seconds
            self.ctx.inputs.parameters['input_qeconverse']['max_seconds'] = max_seconds

        # Convert parameters back to Dict node
        self.ctx.inputs.parameters = orm.Dict(dict=self.ctx.inputs.parameters)

    def report_error_handled(self, calculation, action):
        """Report an action taken for a calculation that has failed.

        This should be called in a registered error handler if its condition is met and an action was taken.

        :param calculation: the failed calculation node
        :param action: a string message with the action taken
        """
        arguments = [calculation.process_label, calculation.pk, calculation.exit_status, calculation.exit_message]
        self.report('{}<{}> failed with exit status {}: {}'.format(*arguments))
        self.report(f'Action taken: {action}')

    @process_handler(priority=600)
    def handle_unrecoverable_failure(self, calculation):
        """Handle calculations with an exit status below 400 which are unrecoverable, so abort the work chain."""
        if calculation.is_excepted:
            self.report_error_handled(calculation, 'calculation was excepted, aborting')
            return ProcessHandlerReport(True, self.exit_codes.ERROR_UNRECOVERABLE_FAILURE)

        if calculation.is_killed:
            self.report_error_handled(calculation, 'calculation was killed, aborting')
            return ProcessHandlerReport(True, self.exit_codes.ERROR_UNRECOVERABLE_FAILURE)

        return None

    @process_handler(priority=590, exit_codes=[
        QeConverseCalculation.exit_codes.ERROR_NO_RETRIEVED_FOLDER,
        QeConverseCalculation.exit_codes.ERROR_OUTPUT_FILES,
    ])
    def handle_known_unrecoverable_failure(self, calculation):
        """Handle calculations with exit codes that are known to be unrecoverable."""
        self.report_error_handled(calculation, 'known unrecoverable error, aborting')
        return ProcessHandlerReport(True, self.exit_codes.ERROR_KNOWN_UNRECOVERABLE_FAILURE)

    @process_handler(
        priority=580,
        exit_codes=[
            QeConverseCalculation.exit_codes.ERROR_CONVERGENCE,
        ]
    )
    def handle_convergence_not_reached(self, calculation):
        """Handle convergence issues by adjusting mixing_beta."""
        self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
        
        current_mixing_beta = self.ctx.inputs.parameters['input_qeconverse'].get('mixing_beta', 0.7)
        new_mixing_beta = current_mixing_beta * self.defaults.delta_factor_mixing_beta
        
        # Don't let mixing_beta get too small
        if new_mixing_beta < 0.1:
            self.report_error_handled(calculation, 'mixing_beta already very low, cannot recover')
            return ProcessHandlerReport(True, self.exit_codes.ERROR_KNOWN_UNRECOVERABLE_FAILURE)
        
        self.ctx.inputs.parameters['input_qeconverse']['mixing_beta'] = new_mixing_beta
        
        action = f'reduced mixing_beta from {current_mixing_beta} to {new_mixing_beta} and restarting'
        self.report_error_handled(calculation, action)
        return ProcessHandlerReport(True)

    @process_handler(
        priority=570,
        exit_codes=[
            QeConverseCalculation.exit_codes.ERROR_OUTPUT_INCOMPLETE,
        ]
    )
    def handle_output_incomplete(self, calculation):
        """Handle incomplete output - may be due to walltime."""
        # Check if it's a walltime issue
        max_seconds = self.ctx.inputs.parameters.get_dict()['input_qeconverse'].get('max_seconds', None)
        
        if max_seconds:
            # Reduce max_seconds further to ensure proper shutdown
            new_max_seconds = max_seconds * 0.9
            self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
            self.ctx.inputs.parameters['input_qeconverse']['max_seconds'] = new_max_seconds
            
            action = f'reduced max_seconds from {max_seconds} to {new_max_seconds} and restarting'
            self.report_error_handled(calculation, action)
            return ProcessHandlerReport(True)
        
        # Otherwise, it's unrecoverable
        self.report_error_handled(calculation, 'output incomplete and cannot recover')
        return ProcessHandlerReport(True, self.exit_codes.ERROR_KNOWN_UNRECOVERABLE_FAILURE)

    @process_handler(priority=400, exit_codes=[
        ExitCode(0),
    ])
    def sanity_check_outputs(self, calculation):
        """Perform sanity checks on successfully completed calculations."""
        # Check if output_parameters exists and has expected content
        if 'output_parameters' not in calculation.outputs:
            self.report('calculation completed but output_parameters is missing')
            return ProcessHandlerReport(True, self.exit_codes.ERROR_KNOWN_UNRECOVERABLE_FAILURE)
                
        return None

    def on_terminated(self):
        """Clean up any resources if the workchain is terminated."""
        super().on_terminated()
        self.report('QeConverseBaseWorkChain terminated')

    def results(self):
        """Attach the output parameters and retrieved folder to the outputs."""
        calculation = self.ctx.children[self.ctx.iteration - 1]

        # We check the `is_finished` attribute of the work chain and not the successfulness of the last calculation
        # because the error handlers in the last iteration can have qualified a "failed" calculation as acceptable.
        if not self.ctx.is_finished:
            self.report(f'calculation did not finish successfully, not attaching outputs')
            return

        self.report(f'workchain completed after {self.ctx.iteration} iterations')

        # Expose all outputs from the final calculation
        for output_name, output_node in calculation.outputs.items():
            self.out(output_name, output_node)
