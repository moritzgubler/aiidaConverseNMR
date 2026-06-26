"""
AiiDA WorkChain for computing electric field gradient (EFG) tensors and
NMR/NQR quadrupolar parameters with ``qe-efg.x``.

Unlike :class:`NmrConverseWorkChain`, the EFG is a pure ground-state property:
a single SCF followed by **one** ``qe-efg.x`` run returns the full 3x3 tensor
for every atom at once (no per-atom / per-direction loop, no tensor assembly).
The SCF keeps symmetry on (``qe-efg.x`` symmetrises via ``symtensor``), which is
faster than the NMR converse SCF.

Outline: setup -> run_scf -> inspect_scf -> run_efg -> inspect_efg ->
compute_results -> maybe_compute_spectra -> finalize.
"""

from aiida import orm
from aiida.engine import WorkChain, ToContext, calcfunction
from aiida_quantumespresso.workflows.pw.base import PwBaseWorkChain

from .efg_base import QeEfgBaseWorkChain
from . import common
from ..data.nuclear import efg_arrays_from_structure
from ..postprocessing.quadrupolar_spectrum import simulate_powder_spectrum


@calcfunction
def collect_efg_results(efg_output, structure, target_atoms):
    """Map the parser output (keyed by 1-based atom index) onto atom labels.

    Produces two dictionaries keyed by ``<kind_name><1-based index>`` (e.g.
    ``O1``, ``Si2``): the symmetrized EFG tensors and the per-atom quadrupolar
    parameters (principal values, eigenvectors, eta, and Cq/nu_Q when present).
    ``target_atoms`` (0-based site indices) only flags which atoms are of
    interest; the tensor is computed for every atom regardless.
    """
    data = efg_output.get_dict()
    sites = structure.sites
    targets = set(target_atoms.get_list())

    tensors = {}
    quad = {}

    natoms = data.get('natoms', 0)
    for na in range(1, natoms + 1):
        key = str(na)
        idx0 = na - 1
        kind_name = sites[idx0].kind_name
        label = f'{kind_name}{na}'

        tensors[label] = data['efg_tensors'].get(key)

        entry = {}
        pv = data.get('principal_values', {}).get(key, {})
        entry.update({k: pv[k] for k in ('Vxx', 'Vyy', 'Vzz') if k in pv})
        entry['eigenvectors'] = data.get('eigenvectors', {}).get(key, {})
        entry.update(data.get('quadrupolar_parameters', {}).get(key, {}))
        entry['is_target'] = idx0 in targets
        quad[label] = entry

    return {
        'efg_tensors': orm.Dict(dict=tensors),
        'quadrupolar_parameters': orm.Dict(dict=quad),
    }


class EfgWorkChain(WorkChain):
    """WorkChain for computing EFG tensors and quadrupolar parameters."""

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        super().define(spec)

        spec.input('structure', valid_type=orm.StructureData,
                   help='Crystal structure for the calculation')
        spec.input('pw_code', valid_type=orm.Code,
                   help='Code for pw.x (Quantum ESPRESSO)')
        spec.input('efg_code', valid_type=orm.Code,
                   help='Code for qe-efg.x')
        spec.input('scf_parameters', valid_type=orm.Dict,
                   help='Parameters for the SCF calculation')
        spec.input('efg_parameters', valid_type=orm.Dict, required=False,
                   help='Extra parameters for the qe-efg namelist (prefix/outdir/q_efg/i_efg '
                        'are filled in automatically)')
        spec.input('pseudos', valid_type=orm.Dict,
                   help='Dictionary mapping kind names to pseudopotential node PKs')
        spec.input('target_atoms', valid_type=orm.List,
                   help='List of atom indices (0-based) flagged as of interest (reporting only)')
        spec.input('options', valid_type=orm.Dict,
                   help='Computational resources (num_machines, num_mpiprocs_per_machine, etc.)')
        spec.input('kpoints_distance', valid_type=orm.Float,
                   help='K-points distance in inverse Angstrom (e.g. 0.2)')
        spec.input('nuclear_data', valid_type=orm.Dict, required=False,
                   help='Override default Q (1e-30 m^2) and I per element or kind name, '
                        'e.g. {"O": {"Q": -2.558, "I": 2.5}}. Q=0 skips Cq for that species.')
        spec.input('compute_spectra', valid_type=orm.Bool, required=False,
                   default=lambda: orm.Bool(False),
                   help='Also simulate first/second-order quadrupolar powder NMR spectra')
        spec.input('larmor_frequency', valid_type=orm.Float, required=False,
                   help='Larmor frequency nu_L (MHz) used for the optional spectrum simulation')

        spec.outline(
            cls.setup,
            cls.run_scf,
            cls.inspect_scf,
            cls.run_efg,
            cls.inspect_efg,
            cls.compute_results,
            cls.maybe_compute_spectra,
            cls.finalize,
        )

        spec.output('scf_remote_folder', valid_type=orm.RemoteData,
                    help='Remote folder containing SCF results')
        spec.output('efg_tensors', valid_type=orm.Dict,
                    help='Symmetrized EFG tensor (Ha/bohr^2) per atom label')
        spec.output('quadrupolar_parameters', valid_type=orm.Dict,
                    help='Per-atom Vxx/Vyy/Vzz, eta, Cq, nu_Q and eigenvectors')
        spec.output('efg_parameters_raw', valid_type=orm.Dict,
                    help='Full raw parser output of qe-efg.x')
        spec.output_namespace('spectra', valid_type=orm.ArrayData, required=False, dynamic=True,
                              help='Optional simulated powder quadrupolar spectra per atom label')

        spec.exit_code(300, 'ERROR_SCF_FAILED',
                       message='SCF calculation failed')
        spec.exit_code(301, 'ERROR_EFG_FAILED',
                       message='The qe-efg calculation failed')
        spec.exit_code(302, 'ERROR_PARSING_FAILED',
                       message='Failed to parse EFG output')

    @classmethod
    def get_builder_from_protocol(
        cls,
        pw_code,
        efg_code,
        structure,
        protocol='moderate',
        pseudo_family='gipaw_PBE',
        target_atoms=None,
        electronic_type=None,
        nuclear_data=None,
        compute_spectra=False,
        larmor_frequency=None,
        overrides=None,
        **kwargs
    ):
        """Return a builder configured from a protocol (``fast``/``moderate``/``precise``)."""
        proto = common.get_protocol(protocol, overrides=overrides)

        pseudos = common.lookup_pseudos(structure, pseudo_family)

        scf_parameters = common.build_scf_parameters(
            proto, electronic_type=electronic_type, nosym=False, noinv=False
        )

        options = common.build_options(
            proto,
            queue_name=kwargs.get('queue_name') or (overrides or {}).get('queue_name'),
        )

        if target_atoms is None:
            target_atoms = list(range(len(structure.sites)))

        builder = cls.get_builder()
        builder.structure = structure
        builder.pw_code = pw_code
        builder.efg_code = efg_code
        builder.scf_parameters = orm.Dict(dict=scf_parameters)
        builder.pseudos = orm.Dict(dict=pseudos)
        builder.target_atoms = orm.List(list=target_atoms)
        builder.options = orm.Dict(dict=options)
        builder.kpoints_distance = orm.Float(proto['kpoints_distance'])
        builder.compute_spectra = orm.Bool(bool(compute_spectra))
        if nuclear_data is not None:
            builder.nuclear_data = orm.Dict(dict=nuclear_data)
        if larmor_frequency is not None:
            builder.larmor_frequency = orm.Float(larmor_frequency)

        return builder

    def setup(self):
        """Initialise the workchain context."""
        self.report('Setting up EFG workchain')
        structure = self.inputs.structure
        self.ctx.num_sites = len(structure.sites)
        self.ctx.target_atoms = self.inputs.target_atoms.get_list()

        overrides = self.inputs.nuclear_data.get_dict() if 'nuclear_data' in self.inputs else None
        arrays = efg_arrays_from_structure(structure, overrides=overrides)
        self.ctx.efg_arrays = arrays
        self.report(
            'ATOMIC_SPECIES order (q_efg/i_efg indexing): '
            + ', '.join(
                f'{name}(Q={q}, I={i})'
                for name, q, i in zip(arrays['species_order'], arrays['q_efg'], arrays['i_efg'])
            )
        )

    def run_scf(self):
        """Run the SCF calculation (symmetry kept on)."""
        self.report('Submitting SCF calculation')
        pseudo_dict = self.inputs.pseudos.get_dict()
        pseudos = {kind: orm.load_node(pk) for kind, pk in pseudo_dict.items()}

        inputs = {
            'pw': {
                'code': self.inputs.pw_code,
                'structure': self.inputs.structure,
                'parameters': self.inputs.scf_parameters,
                'pseudos': pseudos,
                'metadata': {'options': self.inputs.options.get_dict()},
            },
            'kpoints_distance': self.inputs.kpoints_distance,
        }
        running = self.submit(PwBaseWorkChain, **inputs)
        self.report(f'Submitted SCF calculation <{running.pk}>')
        return ToContext(scf_calc=running)

    def inspect_scf(self):
        """Check the SCF completed successfully."""
        if not self.ctx.scf_calc.is_finished_ok:
            self.report('SCF calculation failed')
            return self.exit_codes.ERROR_SCF_FAILED
        self.report('SCF calculation completed successfully')
        self.ctx.scf_remote_folder = self.ctx.scf_calc.outputs.remote_folder
        self.out('scf_remote_folder', self.ctx.scf_remote_folder)

    def run_efg(self):
        """Submit the single qe-efg.x calculation for all atoms."""
        self.report('Submitting qe-efg calculation')

        scf_params = self.inputs.scf_parameters.get_dict()
        prefix = scf_params.get('CONTROL', {}).get('prefix', 'aiida')

        base_params = self.inputs.efg_parameters.get_dict() if 'efg_parameters' in self.inputs else {}
        params = base_params.copy()
        params['prefix'] = prefix
        params['outdir'] = './out/'
        params['q_efg'] = self.ctx.efg_arrays['q_efg']
        params['i_efg'] = self.ctx.efg_arrays['i_efg']

        inputs = {
            'qeefg': {
                'code': self.inputs.efg_code,
                'parameters': orm.Dict(dict={'input_qeefg': params}),
                'parent_folder': self.ctx.scf_remote_folder,
                'metadata': {
                    'options': self.inputs.options.get_dict(),
                    'label': 'efg',
                    'description': 'EFG tensor calculation for all atoms',
                },
            }
        }
        running = self.submit(QeEfgBaseWorkChain, **inputs)
        self.report(f'Submitted qe-efg calculation <{running.pk}>')
        return ToContext(efg_calc=running)

    def inspect_efg(self):
        """Check the qe-efg calculation completed successfully."""
        if not self.ctx.efg_calc.is_finished_ok:
            self.report('qe-efg calculation failed')
            return self.exit_codes.ERROR_EFG_FAILED
        self.report('qe-efg calculation completed successfully')

    def compute_results(self):
        """Map parser output onto atom labels and attach outputs."""
        self.report('Collecting EFG results')
        try:
            efg_output = self.ctx.efg_calc.outputs.output_parameters
        except AttributeError:
            self.report('No output_parameters produced by qe-efg')
            return self.exit_codes.ERROR_PARSING_FAILED

        if not efg_output.get_dict().get('converged', False):
            self.report('qe-efg output did not parse cleanly')
            return self.exit_codes.ERROR_PARSING_FAILED

        results = collect_efg_results(
            efg_output, self.inputs.structure, self.inputs.target_atoms
        )
        self.out('efg_tensors', results['efg_tensors'])
        self.out('quadrupolar_parameters', results['quadrupolar_parameters'])
        self.out('efg_parameters_raw', efg_output)
        self.ctx.quadrupolar_parameters = results['quadrupolar_parameters']

    def maybe_compute_spectra(self):
        """Optionally simulate powder quadrupolar NMR spectra (gated feature)."""
        if not self.inputs.compute_spectra.value:
            return
        if 'larmor_frequency' not in self.inputs:
            self.report('compute_spectra requested but no larmor_frequency given; skipping spectra')
            return

        self.report('Simulating quadrupolar powder spectra')
        quad = self.ctx.quadrupolar_parameters.get_dict()
        nu_L = self.inputs.larmor_frequency
        for label, entry in quad.items():
            nu_Q = entry.get('nu_Q')
            spin = entry.get('I')
            if nu_Q is None or spin is None or spin < 1.0:
                continue  # spectrum needs a defined nu_Q and I >= 1
            spectrum = simulate_powder_spectrum(
                orm.Float(nu_Q),
                orm.Float(entry.get('eta', 0.0)),
                orm.Float(spin),
                nu_L,
            )
            self.out(f'spectra.{label}', spectrum)

    def finalize(self):
        """Print a short summary."""
        self.report('EFG workchain completed successfully')
        quad = self.node.outputs.quadrupolar_parameters.get_dict()
        for label, entry in quad.items():
            if not entry.get('is_target', True):
                continue
            vzz = entry.get('Vzz')
            eta = entry.get('eta')
            cq = entry.get('Cq')
            msg = f'  {label}: Vzz={vzz}'
            if eta is not None:
                msg += f', eta={eta:.4f}'
            if cq is not None:
                msg += f', Cq={cq:.4f} MHz'
            self.report(msg)
