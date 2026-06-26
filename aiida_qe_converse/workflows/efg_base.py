"""BaseRestartWorkChain wrapper for the qe-efg.x calculation."""

from aiida import orm
from aiida.common import AttributeDict
from aiida.engine import BaseRestartWorkChain, ProcessHandlerReport, process_handler, while_
from aiida.plugins import CalculationFactory

QeEfgCalculation = CalculationFactory('qeefg')


class QeEfgBaseWorkChain(BaseRestartWorkChain):
    """Run a qe-efg.x calculation with automated error handling and restarts."""

    _process_class = QeEfgCalculation

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)
        spec.expose_inputs(QeEfgCalculation, namespace='qeefg')

        spec.outline(
            cls.setup,
            while_(cls.should_run_process)(
                cls.prepare_process,
                cls.run_process,
                cls.inspect_process,
            ),
            cls.results,
        )

        spec.expose_outputs(QeEfgCalculation)

        spec.exit_code(300, 'ERROR_UNRECOVERABLE_FAILURE',
                       message='The calculation failed with an unidentified unrecoverable error.')

    def setup(self):
        """Create ``self.ctx.inputs`` and ensure the namelist wrapping is present."""
        super().setup()
        self.ctx.inputs = AttributeDict(self.exposed_inputs(QeEfgCalculation, 'qeefg'))
        if 'parameters' in self.ctx.inputs:
            self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
            if 'input_qeefg' not in self.ctx.inputs.parameters:
                params = self.ctx.inputs.parameters.copy()
                self.ctx.inputs.parameters = {'input_qeefg': params}

    def prepare_process(self):
        """Prepare the inputs for the next calculation."""
        self.ctx.inputs.parameters = orm.Dict(dict=self.ctx.inputs.parameters)

    @process_handler(priority=600)
    def handle_crash_file(self, calculation):
        """Check for a CRASH file and abort if found (same as the converse base)."""
        try:
            retrieved = calculation.outputs.retrieved
        except AttributeError:
            return None

        if 'CRASH' in retrieved.list_object_names():
            self.report(f'{calculation.process_label}<{calculation.pk}> found CRASH file, aborting')
            return ProcessHandlerReport(True, self.exit_codes.ERROR_UNRECOVERABLE_FAILURE)

        return None

    def results(self):
        """Attach the outputs of the last calculation."""
        calculation = self.ctx.children[self.ctx.iteration - 1]
        for link_label in calculation.outputs:
            self.out(link_label, calculation.outputs[link_label])
