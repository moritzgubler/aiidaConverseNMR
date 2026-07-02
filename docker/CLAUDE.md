# docker/ — deployment image internals

Agent notes for the Dockerfile/compose. User-facing quick start is in README.md.
Every non-obvious line in the Dockerfile exists because something broke without
it — do not "clean up" without checking this list.

## Base image

- `FROM ghcr.io/aiidalab/qe:pr-1512@sha256:5589c74e…` — the aiidalab-qe PR #1512
  dev image (Python 3.12, aiida-core 2.8, aiida-quantumespresso 4.17). It is the
  first stack that can parse QE 7.5's XML schema (`qes_250521`); stable
  `aiidalab/qe` images are Python 3.9 + aiida-qe 4.12 and fail with exit 322.
  Pinned by digest because `pr-###` tags are mutable and vanish when the PR
  closes. Re-pin: `docker buildx imagetools inspect ghcr.io/aiidalab/qe:<tag>`.
  TODO: switch to a stable release once one ships py3.12 + aiida-qe ≥4.17.

## Build

- Build **context is the repo root** (`context: ..` in compose) so
  `COPY . /opt/aiida-qe-converse` gets the plugin + `pseudos/` + `examples/`;
  the root `.dockerignore` applies.
- QE 7.5 is built **with MPI** (OpenMPI from apt; `./configure` auto-detects
  `mpif90`). qe-converse configure hard-requires QE **7.5 source tree**
  (`--with-qe-source`, checks `make.inc` + version) — conda QE packages cannot
  be used. qe-converse is pinned to a commit via `ARG QE_CONVERSE_REF`.
- `PIP_USER=0 pip install -e /opt/aiida-qe-converse`: the base image defaults to
  user installs under `/home/jovyan/.local`, which is (a) shadowed at runtime by
  the home volume and (b) root-owned at build time, which **breaks the base
  image's first-start home extraction** (`00_untar-home.sh` permission errors).
  Editable so the dev compose override (`..:/opt/aiida-qe-converse`) makes host
  edits live (restart the app kernel; no rebuild).
- `pip uninstall aiidalab-qe-muon aiidalab-qe-vibroscopy`: both are broken
  against aiida-core 2.8 (removed `get_stack_size`, renamed `ResultPanel`) and
  only spam load errors in the app.
- `pip install upf-tools`: optional dep of aiidalab-qe's Advanced→Pseudos tab;
  missing it raises a (non-fatal but ugly) ModuleNotFoundError when the tab renders.
- `rm /usr/local/bin/before-notebook.d/43_start-hq.sh`: disables HyperQueue.
- `OMPI_MCA_btl_vader_single_copy_mechanism=none`: quiets OpenMPI shared-memory
  transport warnings in containers.

## Startup hook (`90-register-qe-converse.sh`)

Runs on every container start, idempotent; calls the plugin CLI
(`aiida-qe-converse-setup pseudos` / `codes --with-mpi …`) and then fixes the
`localhost` computer — all three fixes are properties of the aiidalab base
image, not of the plugin:

1. **scheduler → `core.direct`**: the base configures HyperQueue; its worker
   advertises less memory than the protocol requests, so jobs queue forever.
2. **mpirun template → `mpirun -np {tot_num_mpiprocs} --oversubscribe`**: the
   base sets `{num_cpus}`, which the direct scheduler cannot substitute
   (`KeyError: 'num_cpus'` at presubmit). `--oversubscribe` lets requested
   ranks exceed host cores on small machines.
3. **`default_mpiprocs_per_machine = os.cpu_count()`**: left unset by the base,
   which crashes the QE app Resources panel (`BoundedIntText` with `max=None`).

## Compose

- `docker-compose.yml`: deploy — published `8888:8888`, named home volume
  `aiida-qe-converse-home`, **no source mount** (image is self-contained).
- `docker-compose.dev.yml`: adds the source bind-mount; combine with `-f`.
- `docker compose up -d` does **not** rebuild after pulling changes; use
  `docker compose up -d --build` (QE layers stay cached; only COPY-and-after re-run).
- The Jupyter token changes on every container start:
  `docker compose logs aiidalab | grep -o 'token=[a-f0-9]*' | tail -1`.
