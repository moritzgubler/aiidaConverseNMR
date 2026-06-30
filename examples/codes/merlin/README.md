# Merlin7 (PSI) code setup

Ready-to-use AiiDA code configurations for running the EFG/NMR workflows on the
**Merlin7 CPU** partition, using `pw.x`, `qe-converse.x` and `qe-efg.x` built
there (QE 7.5 + QE-CONVERSE 7.5, loaded via environment modules).

## 1. Set up the `merlin7-cpu` computer (once)

`merlin7-cpu` is a known cluster in the [aiida-resource-registry][reg], so the
easiest way is the **aiidalab-qe GUI**: in the *Resources* step open
*"Set up a new computer/code"* and pick `merlin7-cpu` (it fills in the SSH
transport, SLURM scheduler, work dir and launcher for you), then configure SSH
with your PSI username.

Equivalently, from the command line you can point `verdi` straight at the
registry's computer YAML (it accepts a URL), then configure SSH:

```bash
verdi computer setup --config <merlin7-cpu computer.yaml URL from the registry>
verdi computer configure core.ssh merlin7-cpu            # your SSH user/key
verdi computer test merlin7-cpu
```

(We don't vendor the computer YAML here on purpose — `merlin7-cpu` is maintained
upstream in the registry; only the EFG/NMR **codes** are specific to this plugin.)

## 2. Install the codes

With `merlin7-cpu` configured, create the three codes from the YAMLs here:

```bash
verdi code create core.code.installed --non-interactive --config pw-7.5.yml
verdi code create core.code.installed --non-interactive --config qe-converse.yml
verdi code create core.code.installed --non-interactive --config qe-efg.yml
```

This gives you `pw-7.5@merlin7-cpu`, `qe-converse@merlin7-cpu` and
`qe-efg@merlin7-cpu`. Each YAML carries the absolute binary path and a
`prepend_text` that loads the modules at job runtime:

```
module use /data/user/gubler_m/modulefiles/
module load qe/7.5
module load qe-converse/7.5     # qe-converse / qe-efg only
```

> These paths/modules are specific to the `gubler_m` build. For another account,
> edit `filepath_executable` and `prepend_text` (or rebuild and re-point them).

## 3. Pseudopotentials

The GIPAW pseudopotential groups are profile-wide (not per-computer), so import
them once with the plugin's provisioning CLI (see the repo `docker/README.md`):

```bash
aiida-qe-converse-setup pseudos        # imports gipaw_PBE / gipaw_PBEsol
```

You can then select the `*@merlin7-cpu` codes in the aiidalab-qe Resources step
and submit EFG/NMR runs to the cluster.

[reg]: https://github.com/aiidateam/aiida-resource-registry
