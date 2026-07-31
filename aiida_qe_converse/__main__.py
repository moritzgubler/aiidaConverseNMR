"""Entry point for ``python -m aiida_qe_converse <command>``.

The aiidalab-qe Plugin Store runs a plugin's post-install step this way
(``plugins.yaml``'s ``post_install`` field is passed as the command), rather
than via the ``aiida-qe-converse-setup`` console script. Re-dispatch into the
same provisioning CLI so both invocation paths share one implementation.
"""
from .provision import cli

if __name__ == "__main__":
    cli()
