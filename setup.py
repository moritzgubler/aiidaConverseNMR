"""
Setup file for the qe-converse AiiDA plugin.

This registers the CalcJob plugin so AiiDA knows how to use qe-converse.x
"""

from setuptools import setup, find_packages

setup(
    name='aiida-qe-converse',
    version='1.0.1',
    description='AiiDA plugin + aiidalab-qe GUI for NMR shielding and EFG/NQR '
                 'quadrupolar parameters with QE-CONVERSE',
    author='Moritz Gubler',
    author_email='moritz.gubler@gmail.com',
    url='https://github.com/moritzgubler/aiidaConverseNMR',
    license='GPL-3.0-or-later',
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
    ],
    # `pseudos/` ships as its own package (under package_dir remap, so its name
    # doesn't collide with other plugins' modules in the shared aiidalab kernel)
    # so that `pip install git+...` (no persisted clone) still carries the UPFs.
    packages=find_packages(exclude=('pseudos',)) + ['aiida_qe_converse_pseudos'],
    package_dir={'aiida_qe_converse_pseudos': 'pseudos'},
    include_package_data=True,
    package_data={
        'aiida_qe_converse_pseudos': ['**/*.upf', '**/*.UPF'],
    },
    install_requires=[
        'aiida-core>=2.0.0',
        'aiida-quantumespresso>=4.0.0',
        'aiida-pseudo',
        'numpy',
        'ase',
        'scipy',
        # GUI (aiidalab-qe plugins and the standalone simulator app)
        'ipywidgets',
        'plotly',
        'anywidget',  # plotly's FigureWidget backend (plotly >= 6)
    ],
    entry_points={
        'console_scripts': [
            'nmr-converse = aiida_qe_converse.run_nmr_workchain:cli',
            'aiida-qe-converse-setup = aiida_qe_converse.provision:cli',
        ],
        'aiida.calculations': [
            'qeconverse = aiida_qe_converse.calculations.qeconverse:QeConverseCalculation',
            'qeefg = aiida_qe_converse.calculations.qeefg:QeEfgCalculation',
        ],
        'aiida.parsers': [
            'qeconverse = aiida_qe_converse.parsers.qeconverse:QeConverseParser',
            'qeefg = aiida_qe_converse.parsers.qeefg:QeEfgParser',
        ],
        'aiida.workflows': [
            'qeconverse.nmr_converse = aiida_qe_converse.workflows.nmr_converse_workchain:NmrConverseWorkChain',
            'qeconverse.qeconverse_base = aiida_qe_converse.workflows.qeconverse_base:QeConverseBaseWorkChain',
            'qeconverse.efg = aiida_qe_converse.workflows.efg_workchain:EfgWorkChain',
            'qeconverse.qeefg_base = aiida_qe_converse.workflows.efg_base:QeEfgBaseWorkChain',
        ],
        'aiidalab_qe.properties': [
            "qeconverse = aiida_qe_converse.app:property",
            "qeefg = aiida_qe_converse.app_efg:property",
        ],
    },
)
