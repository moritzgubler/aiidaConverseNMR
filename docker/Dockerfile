# Reproducible AiiDAlab deployment image for the aiida-qe-converse (EFG/NMR) plugin.
#
# Base: the aiidalab-qe PR #1512 dev image (Python 3.12, aiida-core 2.8,
# aiida-quantumespresso >=4.17) -- the first stack new enough to parse QE 7.5's
# XML schema (qes_250521). Pinned by digest for reproducibility.
# TODO: switch to a stable `aiidalab/qe` release once it ships Python 3.12 +
#       aiida-quantumespresso >=4.17, and drop the PR-image pin below.
#
# Bakes in, on top of that base:
#   * an MPI Fortran toolchain (OpenMPI + gfortran + FFTW + OpenBLAS)
#   * Quantum ESPRESSO 7.5 (pw.x + libraries, parallel/MPI)
#   * qe-converse / qe-efg built from the official mammasmias repo (pinned commit)
#   * the aiida-qe-converse plugin (this repo, copied from the build context)
#   * a before-notebook.d hook that calls `aiida-qe-converse-setup` to register
#     the codes (MPI-enabled) + import the GIPAW pseudos, and applies the
#     aiidalab-base-specific localhost scheduler fix
#
# Build context is the repo root (see docker-compose.yml).

FROM ghcr.io/aiidalab/qe:pr-1512@sha256:5589c74e4d1727ced0b4bcb7110d06ebd30886bb8b792840c17d601dc4e59780

USER root

# --- MPI Fortran toolchain (build + runtime) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        gfortran g++ make git ca-certificates \
        libfftw3-dev libopenblas-dev \
        openmpi-bin libopenmpi-dev \
    && rm -rf /var/lib/apt/lists/*

# Quieter/safer OpenMPI shared-memory transport inside containers.
ENV OMPI_MCA_btl_vader_single_copy_mechanism=none

# One OpenMP thread per MPI rank. fftw and openblas only get one core
ENV OMP_NUM_THREADS=1

ENV CODES=/opt/codes
ARG QE_TAG=qe-7.5
ARG QE_CONVERSE_REPO=https://github.com/mammasmias/QE-CONVERSE.git
ARG QE_CONVERSE_REF=c89e1fc2b46e468d0518fcca42ee71b4f37e3d84

# --- Quantum ESPRESSO 7.5 (parallel: mpif90 auto-detected, OpenBLAS + FFTW3) ---
RUN mkdir -p "$CODES" && cd "$CODES" \
    && git clone --depth 1 --branch "$QE_TAG" https://gitlab.com/QEF/q-e.git \
    && cd q-e \
    && ./configure \
    && make -j"$(nproc)" pw \
    && make -j"$(nproc)" -C LR_Modules \
    && find . -name '*.o' -delete

# --- qe-converse / qe-efg (official repo, pinned commit) ---
RUN cd "$CODES" \
    && git clone "$QE_CONVERSE_REPO" \
    && cd QE-CONVERSE \
    && git checkout "$QE_CONVERSE_REF" \
    && ./configure --with-qe-source="$CODES/q-e" \
    && make \
    && test -x src/qe-efg.x && test -x src/qe-converse.x

# --- the aiida-qe-converse plugin (build context = repo root) ---
# Install into the *system* site-packages (PIP_USER=0): the base image defaults
# to user installs under /home/jovyan/.local, which is shadowed by the runtime
# home volume (and, owned by root, breaks first-run home extraction).
# Editable install: works standalone for deployment, and lets the dev compose
# override bind-mount live source over it without a rebuild.
COPY . /opt/aiida-qe-converse
# Appmode (the AiiDAlab notebook launcher) writes a tmp copy of the opened
# notebook INTO the app directory (~/apps/quadrupolar-simulator ->
# /opt/aiida-qe-converse), so it must be group-writable for NB_USER --
# otherwise opening the app tile 403s with "Permission denied: ...-0.ipynb".
# Same pattern as the base image's /opt/aiidalab-home (drwsrwsr-x root:users).
RUN chgrp -R users /opt/aiida-qe-converse && chmod -R g+w /opt/aiida-qe-converse
RUN PIP_USER=0 pip install --no-cache-dir -e /opt/aiida-qe-converse

# Drop two bundled QE plugins broken on this dev stack (aiida-core 2.8 API drift:
# aiida_pythonjob 'get_stack_size', old 'ResultPanel' import) -- they only spam
# load errors in the app.
RUN PIP_USER=0 pip uninstall -y aiidalab-qe-muon aiidalab-qe-vibroscopy || true

# Optional 'upf_tools' dependency: aiidalab-qe's Advanced > Pseudopotentials tab
# parses UPF metadata with it. The base image omits it, which raises a
# (non-fatal) error when that tab renders -- install it to keep the UI clean.
RUN PIP_USER=0 pip install --no-cache-dir upf-tools

# Disable the HyperQueue startup hook; we use the direct scheduler on localhost
# (set in the registration hook below).
RUN rm -f /usr/local/bin/before-notebook.d/43_start-hq.sh

# --- startup hook: provision via the plugin CLI + fix the localhost scheduler ---
RUN mkdir -p /usr/local/bin/before-notebook.d \
    && cat > /usr/local/bin/before-notebook.d/90-register-qe-converse.sh <<'SH'
#!/bin/bash
# Expose the standalone quadrupolar-simulator app on the AiiDAlab home page
# (must run at startup, not build time: /home/jovyan is a volume). Guards:
# - a pre-existing REAL directory (e.g. a git clone from the app manager) is
#   left alone -- ln -sfn would silently nest the symlink inside it;
# - nothing here may fail unguarded: this hook is sourced under start.sh's
#   `set -e`, so an error would abort container startup entirely.
app_link=/home/jovyan/apps/quadrupolar-simulator
if [ ! -e "$app_link" ] || [ -L "$app_link" ]; then
    { mkdir -p /home/jovyan/apps \
        && ln -sfn /opt/aiida-qe-converse "$app_link"; } \
        || echo "[qe-converse] app symlink failed; home tile unavailable"
else
    echo "[qe-converse] $app_link exists (real directory); leaving it alone"
fi
echo "[qe-converse] provisioning codes + GIPAW pseudos ..."
aiida-qe-converse-setup pseudos || echo "[qe-converse] pseudo import deferred to next start"
aiida-qe-converse-setup codes --computer localhost --with-mpi \
    --pw /opt/codes/q-e/bin/pw.x \
    --converse /opt/codes/QE-CONVERSE/src/qe-converse.x \
    --efg /opt/codes/QE-CONVERSE/src/qe-efg.x \
    || echo "[qe-converse] code registration deferred to next start"
# aiidalab-base-specific: the image configures localhost with the HyperQueue
# scheduler and a '{num_cpus}' mpirun template the direct scheduler cannot
# substitute. Force core.direct + a valid mpirun template with --oversubscribe
# (so a single-node box can request more ranks than it has cores).
python - <<'PY' || true
import os
from aiida import load_profile, orm
try:
    load_profile()
    c = orm.load_computer("localhost")
    if c.scheduler_type != "core.direct":
        c.scheduler_type = "core.direct"
        print("[qe-converse] set localhost scheduler to core.direct")
    cmd = " ".join(c.get_mpirun_command())
    if "{num_cpus}" in cmd or "--oversubscribe" not in cmd:
        c.set_mpirun_command(["mpirun", "-np", "{tot_num_mpiprocs}", "--oversubscribe"])
        print("[qe-converse] set localhost mpirun_command")
    # The aiidalab image leaves default_mpiprocs_per_machine unset (None), which
    # makes the QE app Resources panel crash (BoundedIntText max=None). Set it to
    # the node's core count.
    if c.get_default_mpiprocs_per_machine() is None:
        c.set_default_mpiprocs_per_machine(os.cpu_count() or 4)
        print("[qe-converse] set localhost default_mpiprocs_per_machine")
except Exception as exc:
    print(f"[qe-converse] localhost config fix deferred: {exc}")
PY
SH
RUN chmod +x /usr/local/bin/before-notebook.d/90-register-qe-converse.sh

USER ${NB_USER}
