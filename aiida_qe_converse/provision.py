"""
Provisioning CLI for aiida-qe-converse: register codes + import GIPAW pseudos.

Exposed as the ``aiida-qe-converse-setup`` console script. Every operation is
idempotent and runs against the currently configured AiiDA profile, so it is
used both by the Docker image's startup hook and by anyone who ``pip install``s
the plugin and wants to provision their own AiiDA (codes + GIPAW pseudo groups)
in one command.

The pure helpers (:func:`default_pseudo_dir`, :func:`discover_pseudo_families`)
have no AiiDA dependency and are unit-tested; the AiiDA imports are deferred
into the command bodies.
"""
import os
import pathlib

import click

# Known locations searched (in order) for the GIPAW pseudopotential directory.
_DEFAULT_PSEUDO_DIRS = (
    "/opt/aiida-qe-converse/pseudos",
)


def default_pseudo_dir():
    """Resolve the GIPAW pseudo directory.

    Order: ``$AIIDA_QE_CONVERSE_PSEUDO_DIR``, then known container paths, then a
    ``pseudos/`` directory shipped next to the package (repo layout).
    """
    env = os.environ.get("AIIDA_QE_CONVERSE_PSEUDO_DIR")
    if env:
        return pathlib.Path(env)
    for candidate in _DEFAULT_PSEUDO_DIRS:
        if pathlib.Path(candidate).is_dir():
            return pathlib.Path(candidate)
    # repo layout: <repo>/pseudos, with this file at <repo>/aiida_qe_converse/provision.py
    return pathlib.Path(__file__).resolve().parent.parent / "pseudos"


def discover_pseudo_families(pseudo_dir):
    """Return ``{group_label: [upf_paths]}`` for each ``gipaw*`` subdir.

    Pure (no AiiDA): the group label is the subdirectory name (e.g.
    ``gipaw_PBE``) and the values are its ``.upf``/``.UPF`` files, sorted.
    Subdirectories without any UPF are skipped.
    """
    pseudo_dir = pathlib.Path(pseudo_dir)
    families = {}
    if not pseudo_dir.is_dir():
        return families
    for sub in sorted(pseudo_dir.iterdir()):
        if sub.is_dir() and sub.name.lower().startswith("gipaw"):
            upfs = sorted(list(sub.glob("*.upf")) + list(sub.glob("*.UPF")))
            if upfs:
                families[sub.name] = upfs
    return families


@click.group()
def cli():
    """Provision AiiDA for aiida-qe-converse (codes + GIPAW pseudopotentials)."""


@cli.command()
@click.option("--pseudo-dir", type=click.Path(), default=None,
              help="Directory containing gipaw_* subdirectories of UPF files. "
                   "Defaults to $AIIDA_QE_CONVERSE_PSEUDO_DIR, a known container "
                   "path, or the repo's pseudos/ dir.")
def pseudos(pseudo_dir):
    """Import the GIPAW pseudopotential groups (idempotent)."""
    from aiida import load_profile
    from aiida.orm import Group
    from aiida_pseudo.data.pseudo.upf import UpfData
    load_profile()

    directory = pathlib.Path(pseudo_dir) if pseudo_dir else default_pseudo_dir()
    families = discover_pseudo_families(directory)
    if not families:
        click.echo(f"[qe-converse] no gipaw_* pseudo families found in {directory}")
        return
    for label, paths in families.items():
        group, _ = Group.collection.get_or_create(label=label)
        if group.count():
            click.echo(f"[qe-converse] pseudo group already populated: {label}")
            continue
        count = 0
        for upf in paths:
            with open(upf, "rb") as handle:
                node = UpfData(handle, filename=upf.name)
            node.store()
            group.add_nodes(node)
            count += 1
        click.echo(f"[qe-converse] imported {count} pseudos into group '{label}'")


@cli.command()
@click.option("--computer", default="localhost", show_default=True)
@click.option("--with-mpi/--no-with-mpi", default=False, show_default=True,
              help="Register the codes as MPI-enabled (run under mpirun).")
@click.option("--pw", "pw_path", default="/opt/codes/q-e/bin/pw.x", show_default=True)
@click.option("--converse", "converse_path",
              default="/opt/codes/QE-CONVERSE/src/qe-converse.x", show_default=True)
@click.option("--efg", "efg_path",
              default="/opt/codes/QE-CONVERSE/src/qe-efg.x", show_default=True)
def codes(computer, with_mpi, pw_path, converse_path, efg_path):
    """Register the pw-7.5 / qe-converse / qe-efg InstalledCodes (idempotent)."""
    from aiida import load_profile, orm
    from aiida.orm import InstalledCode
    load_profile()

    try:
        comp = orm.load_computer(computer)
    except Exception:
        click.echo(f"[qe-converse] computer '{computer}' not found; skipping code registration")
        return

    spec = {
        "pw-7.5": (pw_path, "quantumespresso.pw"),
        "qe-converse": (converse_path, "qeconverse"),
        "qe-efg": (efg_path, "qeefg"),
    }
    for label, (path, plugin) in spec.items():
        try:
            orm.load_code(f"{label}@{computer}")
            click.echo(f"[qe-converse] code already registered: {label}")
            continue
        except Exception:
            pass
        if not pathlib.Path(path).exists():
            click.echo(f"[qe-converse] binary missing, skipping: {path}")
            continue
        code = InstalledCode(computer=comp, filepath_executable=path)
        code.label = label
        code.default_calc_job_plugin = plugin
        code.with_mpi = with_mpi
        code.store()
        click.echo(f"[qe-converse] registered code: {label}@{computer} (mpi={with_mpi})")


if __name__ == "__main__":
    cli()
