# aiida-qe-converse

AiiDA plugin + aiidalab-qe GUI for **NMR chemical shielding** (converse approach,
`qe-converse.x`) and **EFG / NMR-NQR quadrupolar parameters** (`qe-efg.x`) with
Quantum ESPRESSO. See [QE-CONVERSE](https://github.com/mammasmias/QE-CONVERSE)
and [arXiv:2503.04664](https://arxiv.org/abs/2503.04664).

More detail lives in per-area docs: `docker/CLAUDE.md` (deployment image
internals), `aiida_qe_converse/postprocessing/CLAUDE.md` (spectrum physics /
formulas / units), `aiida_qe_converse/app_efg/CLAUDE.md` (EFG GUI architecture).

## Project structure

```
aiida_qe_converse/
  calculations/   qeconverse.py, qeefg.py      # CalcJobs: write Fortran namelist, symlink SCF out/
  parsers/        qeconverse.py                # NMR parser
                  qeefg.py + efg_parsing.py    # EFG parser (efg_parsing = AiiDA-free core, unit-tested)
  workflows/      common.py                    # SHARED: protocol table, pseudo lookup, SCF params, options
                  nmr_converse_workchain.py    # SCF + 3 converse runs per atom + tensor assembly
                  efg_workchain.py             # SCF + ONE qe-efg run (all atoms) + results
                  qeconverse_base.py, efg_base.py  # BaseRestartWorkChains (CRASH-file handler)
  data/nuclear.py                              # isotope Q/I table, gyromagnetic ratios, species->q_efg mapping
  postprocessing/ quadrupolar_spectrum.py      # powder + single-crystal spectra (thesis eqs 2.28-2.33)
                  efg_analysis.py              # recompute Vzz/eta/Cq/nu_Q/axes from stored tensor for any Q,I
  app/ app_efg/ app_common/                    # aiidalab-qe GUI plugins (NMR, EFG, shared atom-selection base)
  provision.py                                 # `aiida-qe-converse-setup` CLI: register codes + import pseudos
docker/                                        # canonical deployment image (see docker/CLAUDE.md + README.md)
examples/codes/merlin/                         # `verdi code create --config` YAMLs for PSI Merlin7 (CLI format!)
pseudos/gipaw_PBE*, gipaw_PBEsol/              # GIPAW UPFs shipped in-repo, imported into AiiDA groups
run_nmr_workchain.py, run_efg_workchain.py     # CLI submit/retrieve scripts
tests/                                         # pure-Python tests, NO AiiDA profile needed: pytest tests/ -q
```

## Entry points (setup.py)

```
aiida.calculations:     qeconverse, qeefg
aiida.parsers:          qeconverse, qeefg
aiida.workflows:        qeconverse.nmr_converse, qeconverse.qeconverse_base,
                        qeconverse.efg, qeconverse.qeefg_base
aiidalab_qe.properties: qeconverse (NMR GUI), qeefg (EFG GUI)
console_scripts:        aiida-qe-converse-setup
```

## The two workflows

**NMR** (`NmrConverseWorkChain`): SCF with `nosym=True, noinv=True` (required),
then 3 converse runs per target atom (x/y/z dipole directions); each returns one
column of the 3x3 shielding tensor; isotropic shielding = trace/3.

**EFG** (`EfgWorkChain`): EFG is a pure ground-state property — one SCF
(**symmetry ON**; never reuse an NMR SCF) + **one** `qe-efg.x` run gives the full
tensor for all atoms. Outline: setup → run_scf → inspect_scf → run_efg →
inspect_efg → compute_results → maybe_compute_spectra → finalize.
`target_atoms` is only a reporting filter (the calc always does all atoms).

Both expose `get_builder_from_protocol()`. `EfgWorkChain` derives `withmpi`
from the code's `with_mpi` setting (`_options_for_code` in efg_workchain.py) —
AiiDA hard-errors when the option and the code disagree. **The NMR workchain
does not do this yet**; mirror `_options_for_code` there if a serial code is
ever used with it.

## Critical conventions

- **species → `q_efg`/`i_efg` index mapping**: `qe-efg.x` indexes these arrays
  per ATOM TYPE in the order of the pw.x `ATOMIC_SPECIES` card, which
  aiida-quantumespresso writes **alphabetically sorted by kind name**
  (`calculations/__init__.py` in aiida-qe, ~line 567).
  `data/nuclear.py::build_efg_arrays()` reproduces exactly that ordering.
  Getting this wrong silently attaches Q/I to the wrong element — it is tested
  explicitly (`tests/test_nuclear_mapping.py`).
- **Units of Q**: `1e-30 m²` (= 10 mbarn); 1 barn = 100 of these. `Q = 0` means
  "skip Cq" for that species; `ν_Q` needs `I ≥ 1`. Values that look odd are
  usually unit confusion (e.g. ⁵⁹Co Q = 42 = 0.42 barn — correct).
- **The EFG tensor is Q/I-independent.** Q and I only enter the final Cq/ν_Q
  arithmetic. The workchain stores the raw symmetrized tensor (Ha/bohr²), and
  the GUI recomputes everything from it for any user-chosen Q/I (isotope
  switching without re-running DFT) via `postprocessing/efg_analysis.py`.
  Parser-extracted Cq/ν_Q are "as computed with the submission-time Q".
- **Atom indexing**: Python 0-based; Fortran 1-based (`m_0_atom = idx + 1`).
  Atom labels are `kind_name + 1-based index` ("O1", "Si2").
- **Namelist wrapping**: parameters live under `input_qeconverse` /
  `input_qeefg` keys; the base workchains' `setup()` add the wrapper if missing.
- **SCF remote folder** is symlinked into converse/efg calcs (`out/` via
  `remote_symlink_list`).
- **Pseudos**: GIPAW UPFs as `UpfData` in groups `gipaw_PBE` / `gipaw_PBEsol`,
  looked up **by element symbol** of each kind (custom kind names OK). GIPAW is
  *required* — SSSP/PseudoDojo lack the reconstruction data; the GUI says so and
  ignores the aiidalab Advanced-step pseudo choice.

## Protocols (`workflows/common.py`)

`fast` / `moderate` / `precise`, with GUI aliases `balanced`→moderate,
`stringent`→precise (aiidalab-qe passes its own names — keep the alias map).
`precise` uses `max_memory_kb = 480000000` (~469 GB): deliberately below PSI
Merlin7's real per-node ceiling of 483,328 MB (`RealMemory 515120` −
`MemSpecLimit 31792`; the raw `sinfo` memory is NOT allocatable — exceeding the
real ceiling gives instant `sbatch: Requested node configuration is not
available`). Don't raise it back to 5e8.

## aiidalab-qe GUI integration pitfalls (hard-won)

- The dependency system dlinks **traits**: depend on/observe `structure_uuid`
  (a trait), not `input_structure` (a property). Wrong name crashes the whole
  Configuration step with `TraitError: ... has no trait`.
- Plotly must be embedded as `go.FigureWidget(fig)` placed in the widget tree;
  `display(fig)` into an `ipw.Output` renders nothing in this app.
- The GUI's global protocol names are `fast/balanced/stringent` (see aliases).
- The Resources panel crashes (`BoundedIntText max=None`) if the computer's
  `default_mpiprocs_per_machine` is unset — the Docker startup hook sets it.
- `examples/codes/merlin/*.yml` are **CLI** (`verdi code create --config`)
  format. The GUI's "Set up new code" wizard reads a *different* schema from the
  aiida-resource-registry (`aiidateam.github.io/aiida-resource-registry/database.json`),
  whose URL is effectively hardcoded in `aiidalab_widgets_base`.
- Requires aiida-quantumespresso ≥ 4.16 (QE 7.5 writes XML schema `qes_250521`;
  older aiida-qe rejects it with exit 322) → Python ≥ 3.10 → hence the pinned
  pr-1512 base image in `docker/`.

## Exit codes

| Code | Location | Meaning |
|------|----------|---------|
| 300/310/320/330 | CalcJobs (both) | no retrieved folder / read-parse error / no convergence / incomplete output |
| 300 | BaseRestart (both) | unrecoverable (CRASH file found) |
| 300/301/302 | WorkChains | SCF failed / converse-or-efg failed / parsing failed |

## Testing & verification

- `python -m pytest tests/ -q` — pure Python (parser against exact `efg.f90`
  formats via `tests/sample_efg_output.py`, species mapping, spectrum physics,
  efg_analysis, provisioning helpers). No AiiDA profile, no QE needed.
- Static: after `pip install -e .`, `verdi plugin list aiida.workflows` shows
  the entry points; build a builder via `get_builder_from_protocol`.
- End-to-end smoke test: small Si+O cell, `fast` protocol, `pw-7.5` + `qe-efg`
  codes; expect `Finished [0]` and symmetric/traceless tensors.

## Deployment & provisioning

- `docker/` builds the canonical image (MPI QE 7.5 + qe-converse + plugin +
  auto-provisioning); `cd docker && docker compose up -d`. Dev override
  `docker-compose.dev.yml` bind-mounts the source. Details: `docker/CLAUDE.md`.
- `aiida-qe-converse-setup pseudos|codes` provisions any AiiDA profile
  idempotently (what the container hook calls). Pseudo dir resolution:
  `--pseudo-dir` → `$AIIDA_QE_CONVERSE_PSEUDO_DIR` →
  `/opt/aiida-qe-converse/pseudos` → repo `pseudos/`.
- Merlin7 cluster codes: `examples/codes/merlin/` (module-loading prepend_text,
  `with_mpi: true`).
