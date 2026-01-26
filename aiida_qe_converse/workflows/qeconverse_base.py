from aiida import orm
from aiida.common import AttributeDict
from aiida.engine import BaseRestartWorkChain, ProcessHandlerReport, process_handler, while_
from aiida.plugins import CalculationFactory

QeConverseCalculation = CalculationFactory('qeconverse')


class QeConverseBaseWorkChain(BaseRestartWorkChain):
    """Workchain to run a qe-converse.x calculation with automated error handling and restarts."""

    _process_class = QeConverseCalculation


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


    def setup(self):
        """Call the ``setup`` of the ``BaseRestartWorkChain`` and create the inputs dictionary in ``self.ctx.inputs``.

        This ``self.ctx.inputs`` dictionary will be used by the ``BaseRestartWorkChain`` to submit the calculations
        in the internal loop.

        The ``parameters`` and ``settings`` input ``Dict`` nodes are converted into a regular dictionary.
        """
        super().setup()
        self.ctx.inputs = AttributeDict(self.exposed_inputs(QeConverseCalculation, 'qeconverse'))
        if 'parameters' in self.ctx.inputs:
            self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
            if 'input_qeconverse' not in self.ctx.inputs.parameters:
                params = self.ctx.inputs.parameters.copy()
                self.ctx.inputs.parameters = {'input_qeconverse': params}

    def prepare_process(self):
        """Prepare the inputs for the next calculation."""
        max_wallclock_seconds = self.ctx.inputs.metadata.options.get('max_wallclock_seconds', None)

        if max_wallclock_seconds is not None:
            max_seconds = max_wallclock_seconds * 0.95
            self.ctx.inputs.parameters['input_qeconverse']['max_seconds'] = max_seconds
        self.ctx.inputs.parameters = orm.Dict(dict=self.ctx.inputs.parameters)

    @process_handler(priority=600)
    def handle_crash_file(self, calculation):
        """Check for CRASH file and abort if found."""
        try:
            retrieved = calculation.outputs.retrieved
        except AttributeError:
            return None

        if 'CRASH' in retrieved.list_object_names():
            self.report(f'{calculation.process_label}<{calculation.pk}> found CRASH file, aborting')
            return ProcessHandlerReport(True, self.exit_codes.ERROR_UNRECOVERABLE_FAILURE)

        return None

    def results(self):
        """Attach the output parameters and retrieved folder to the outputs."""
        calculation = self.ctx.children[self.ctx.iteration - 1]
        for link_label in calculation.outputs:
            self.out(link_label, calculation.outputs[link_label])
