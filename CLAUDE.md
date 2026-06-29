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
aiida.calculations:    qeconverse -> QeConverseCalculation
                       qeefg      -> QeEfgCalculation
aiida.parsers:         qeconverse -> QeConverseParser
                       qeefg      -> QeEfgParser
aiida.workflows:       qeconverse.nmr_converse    -> NmrConverseWorkChain
                       qeconverse.qeconverse_base -> QeConverseBaseWorkChain
                       qeconverse.efg             -> EfgWorkChain
                       qeconverse.qeefg_base      -> QeEfgBaseWorkChain
aiidalab_qe.properties: qeconverse -> aiida_qe_converse.app:property      (NMR GUI)
                        qeefg      -> aiida_qe_converse.app_efg:property   (EFG GUI)
```

## EFG (electric field gradient) workflow

`EfgWorkChain` (`qeconverse.efg`) computes EFG tensors and NMR/NQR quadrupolar
parameters (`Cq`, `η`, `ν_Q`) via the standalone `qe-efg.x` driver. Unlike NMR,
the EFG is a **pure ground-state property**: a single SCF (symmetry left ON) plus
**one** `qe-efg.x` run returns the full 3x3 tensor for all atoms — no per-atom /
per-direction loop, no tensor assembly. Outline: `setup -> run_scf ->
inspect_scf -> run_efg -> inspect_efg -> compute_results ->
maybe_compute_spectra -> finalize`.

Key EFG conventions:

- **Namelist** is `&input_qeefg` with `prefix`, `outdir`, `q_efg(n)`, `i_efg(n)`.
  `prefix`/`outdir` match the SCF; the SCF `out/` is symlinked exactly like the
  converse calc.
- **`q_efg`/`i_efg` are per ATOM TYPE (species)**, in the order
  aiida-quantumespresso writes `ATOMIC_SPECIES`, which is the **alphabetical sort
  of kind names**. `data/nuclear.py::build_efg_arrays()` reproduces that ordering;
  getting it wrong attaches Q/I to the wrong element. `q_efg` is in units of
  `1e-30 m²` (= 10 mbarn); `Q = 0` skips `Cq`; `ν_Q` needs `I ≥ 1`.
- **Symmetry stays ON** for the EFG SCF (do NOT reuse an NMR converse SCF, which
  needs `nosym/noinv/nspin=2`). `qe-efg.x` symmetrises via `symtensor`.
- **Parser** (`parsers/efg_parsing.py`, AiiDA-independent core) extracts the
  symmetrized tensor, principal values/eigenvectors, `η`, `Cq`, `ν_Q`. Atoms are
  keyed by 1-based sequential index. `Cq`/`η`/`ν_Q` are parsed (already in MHz)
  rather than recomputed; the raw symmetrized tensor (Ha/bohr²) is also stored.
- **Nuclear data**: built-in default `Q`/`I` table in `data/nuclear.py`, with a
  user `nuclear_data` override (Dict keyed by element or kind name).
- **Optional spectrum**: `postprocessing/quadrupolar_spectrum.py` simulates a
  powder quadrupolar NMR spectrum (thesis eqs 2.28–2.33); gated behind
  `compute_spectra` + `larmor_frequency`, kept separate from the core outputs.
- **Shared helpers**: `workflows/common.py` holds the pseudo lookup, protocol
  table, SCF-parameter and options builders used by both `NmrConverseWorkChain`
  and `EfgWorkChain`. The atom-selection GUI panel lives in
  `app_common/atom_selection.py` and is subclassed by both GUI plugins.

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
| 301 | WorkChain | Converse calculation(s) failed (NMR) / EFG calc failed (EFG) |
| 302 | WorkChain | Parsing/tensor assembly failed |

EFG CalcJob (`QeEfgCalculation`) reuses the same 300/310/320/330 exit-code
layout as the converse CalcJob.

## Common modifications

- **Add new workchain input**: define in `spec.input()` in `NmrConverseWorkChain.define()`, add to `get_builder_from_protocol()` signature and builder assignment, expose in `run_nmr_workchain.py` CLI
- **Change SCF parameters**: modify protocol dicts in `get_builder_from_protocol()` or pass `overrides` dict
- **Change converse parameters**: modify `run_converse_calculations()` where `params` dict is built
- **Add new parser output**: extend `QeConverseParser._parse_output()` and update `compute_results()` in the workchain

## Deployment

`docker/` is the canonical, self-deployable container: an AiiDAlab image with the plugin, an
**MPI** Quantum ESPRESSO 7.5 build and `qe-converse`/`qe-efg`, plus auto-registration of codes and
GIPAW pseudos. `cd docker && docker compose up -d` (see `docker/README.md`). The dev override
`docker-compose.dev.yml` bind-mounts the source for live editing. Base image and `qe-converse`
commit are pinned (the base is an unmerged aiidalab PR image — Python 3.12 / aiida-quantumespresso
>=4.17 — until a stable release ships that stack).

## Provisioning CLI

`aiida-qe-converse-setup` (entry point `aiida_qe_converse.provision:cli`) registers the codes and
imports the GIPAW pseudo groups idempotently against the active profile (`pseudos` and `codes`
subcommands). It is what the Docker startup hook calls, and is reusable on any AiiDA profile. The
pure helpers `discover_pseudo_families()` / `default_pseudo_dir()` are unit-tested
(`tests/test_provision.py`). Pseudo dir resolves from `--pseudo-dir`,
`$AIIDA_QE_CONVERSE_PSEUDO_DIR`, `/opt/aiida-qe-converse/pseudos`, then the repo `pseudos/`.
