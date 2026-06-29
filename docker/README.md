# Docker deployment

A self-contained AiiDAlab instance with the **aiida-qe-converse** (EFG/NMR) plugin,
**Quantum ESPRESSO 7.5** and **qe-converse/qe-efg** all baked in (MPI build), plus
automatic registration of the codes and GIPAW pseudopotentials on first start.

## Quick start

```bash
cd docker
docker compose up -d          # first build compiles QE 7.5 (~10-15 min)
```

Then open the app. Get the Jupyter token:

```bash
docker compose logs aiidalab | grep -o 'token=[a-f0-9]*' | tail -1
```

and browse to `http://localhost:8888/?token=<token>` (the Quantum ESPRESSO app is at
`/apps/apps/quantum-espresso/qe.ipynb`).

Stop / remove:

```bash
docker compose down           # keep data    (named volume persists)
docker compose down -v        # also wipe the AiiDA profile/data volume
```

## What's baked in

- Base: `ghcr.io/aiidalab/qe` (Python 3.12, aiida-core 2.8, aiida-quantumespresso >=4.17),
  pinned by digest. **TODO:** move to a stable `aiidalab/qe` release once one ships this stack
  (see the `FROM` line in the `Dockerfile`; re-pin with `docker buildx imagetools inspect <tag>`).
- **MPI** Quantum ESPRESSO 7.5 (`pw.x`) + `qe-converse`/`qe-efg` (pinned commit of
  `mammasmias/QE-CONVERSE`).
- The plugin, installed editable into the system site-packages.
- On container start, `aiida-qe-converse-setup` registers the codes `pw-7.5`, `qe-converse`,
  `qe-efg` (MPI-enabled) and imports the `gipaw_PBE` / `gipaw_PBEsol` pseudo groups; the localhost
  computer is set to the `core.direct` scheduler.

## MPI / resources

The codes are registered MPI-enabled, so jobs run under `mpirun`. Choose the number of ranks in
the app's **Resources** step (or via the workchain protocol). The localhost `mpirun` template uses
`--oversubscribe`, so you can request more ranks than the host has cores (it will run, just
slower) — match the rank count to your machine for best performance.

## Development

To iterate on the plugin without rebuilding, mount the source over the editable install:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

Edit files under this repo on the host, then restart the app's notebook kernel to pick them up.

## Provisioning by hand

`aiida-qe-converse-setup` is a normal console script (installed with the plugin), usable outside
Docker too — run it once against your AiiDA profile:

```bash
aiida-qe-converse-setup pseudos                       # import GIPAW pseudo groups
aiida-qe-converse-setup pseudos --pseudo-dir /path/to/pseudos
aiida-qe-converse-setup codes --computer localhost --with-mpi \
    --pw /path/pw.x --converse /path/qe-converse.x --efg /path/qe-efg.x
```

The pseudo directory defaults to `$AIIDA_QE_CONVERSE_PSEUDO_DIR`, then
`/opt/aiida-qe-converse/pseudos`, then the repo's `pseudos/` dir.

## Fedora / firewalld note

On Fedora, firewalld may silently drop traffic to Docker's published ports (the
`http://localhost:8888` connection times out even though the container is healthy). Two options:

1. Allow it through firewalld, e.g.:
   ```bash
   sudo firewall-cmd --permanent --zone=trusted --add-interface=docker0
   sudo firewall-cmd --reload
   ```
2. Or use host networking — edit `docker-compose.yml`: remove the `ports:` block and add
   `network_mode: host` under the service (Jupyter then binds the host's 8888 directly).

This only affects Linux/firewalld hosts; macOS/Windows and most Linux setups work with the
default published ports.
