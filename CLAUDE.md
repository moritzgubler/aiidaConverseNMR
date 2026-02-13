# aiida-qe-converse

AiiDA plugin for computing NMR chemical shielding tensors using the converse approach with Quantum ESPRESSO.

The converse approach is a non-perturbative method for computing orbital magnetization (NMR chemical shifts, EPR g-tensors) in periodic systems, avoiding the ill-defined position operator problem of perturbative methods. See [arXiv:2503.04664](https://arxiv.org/abs/2503.04664) and [QE-CONVERSE](https://github.com/mammasmias/QE-CONVERSE).

## Project structure

```
aiida_qe_converse/
  calculations/qeconverse.py    # CalcJob plugin for qe-converse.x
  parsers/qeconverse.py         # Parser: extracts chemical shift vectors from output
  workflows/
    qeconverse_base.py           # BaseRestartWorkChain wrapper with crash detection
    nmr_converse_workchain.py    # Main workflow: SCF + converse + tensor assembly
run_nmr_workchain.py             # CLI entry point for submitting/retrieving workflows
pseudos/                         # GIPAW pseudopotentials (gipaw_PBE, gipaw_PBEsol)
setup.py                         # AiiDA entry points registration
```

## How the workflow works

`NmrConverseWorkChain` orchestrates:

1. **SCF** via `PwBaseWorkChain` (pw.x) with `nosym=True, noinv=True` (required for NMR)
2. **3 converse calculations per target atom** (x, y, z magnetic field directions) via `QeConverseBaseWorkChain`
3. **Tensor assembly**: each converse run returns one column of the 3x3 shielding tensor
4. **Isotropic shielding**: trace/3 of the assembled tensor

The `get_builder_from_protocol()` class method configures everything from a protocol name (`fast`, `moderate`, `precise`).

## Key conventions

- **Atom indexing**: Python-side is 0-based; Fortran-side (qe-converse.x `m_0_atom`) is 1-based. Conversion: `m_0_atom = atom_idx + 1`
- **Pseudopotentials**: stored in AiiDA as `UpfData` nodes in named groups (e.g. `gipaw_PBE`). The workflow looks them up by element from the group via QueryBuilder.
- **Parameters format**: converse parameters are wrapped in an `input_qeconverse` namelist key. `QeConverseBaseWorkChain.setup()` ensures this wrapping exists.
- **Input file generation**: `QeConverseCalculation._generate_input_file()` writes Fortran namelist format (`&input_qeconverse ... /`)
- **SCF remote folder**: symlinked into converse calculations via `remote_symlink_list` (the `out/` directory)

## AiiDA entry points (setup.py)

```
aiida.calculations: qeconverse -> QeConverseCalculation
aiida.parsers:      qeconverse -> QeConverseParser
```

## Dependencies

- `aiida-core >= 2.0.0`
- `aiida-quantumespresso >= 4.0.0`
- `aiida-pseudo` (for `UpfData`)
- `numpy`, `ase` (structure I/O)
- External: Quantum ESPRESSO pw.x (v7.2+), qe-converse.x

## Exit codes

| Code | Location | Meaning |
|------|----------|---------|
| 300 | CalcJob | No retrieved folder |
| 310 | CalcJob | Output file read/parse error |
| 320 | CalcJob | Convergence failure |
| 330 | CalcJob | Incomplete output |
| 300 | BaseRestart | Unrecoverable failure (CRASH file) |
| 300 | WorkChain | SCF failed |
| 301 | WorkChain | Converse calculation(s) failed |
| 302 | WorkChain | Parsing/tensor assembly failed |

## Common modifications

- **Add new workchain input**: define in `spec.input()` in `NmrConverseWorkChain.define()`, add to `get_builder_from_protocol()` signature and builder assignment, expose in `run_nmr_workchain.py` CLI
- **Change SCF parameters**: modify protocol dicts in `get_builder_from_protocol()` or pass `overrides` dict
- **Change converse parameters**: modify `run_converse_calculations()` where `params` dict is built
- **Add new parser output**: extend `QeConverseParser._parse_output()` and update `compute_results()` in the workchain
