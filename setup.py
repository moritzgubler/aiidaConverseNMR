"""
Setup file for the qe-converse AiiDA plugin.

This registers the CalcJob plugin so AiiDA knows how to use qe-converse.x
"""

from setuptools import setup, find_packages

setup(
    name='aiida-qe-converse',
    version='0.1.0',
    description='AiiDA plugin for qe-converse calculations',
    author='Your Name',
    packages=find_packages(),
    install_requires=[
        'aiida-core>=2.0.0',
        'aiida-quantumespresso>=4.0.0',
        'aiida-pseudo',
        'numpy',
        'ase',
    ],
    entry_points={
        'console_scripts': [
            'nmr-converse = aiida_qe_converse.run_nmr_workchain:cli',
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
        ]
    },
)
