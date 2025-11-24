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
    ],
    entry_points={
        'aiida.calculations': [
            'qeconverse = aiida_qe_converse.calculations.qeconverse:QeConverseCalculation',
        ],
        'aiida.parsers': [
            'qeconverse = aiida_qe_converse.parsers.qeconverse:QeConverseParser',
        ],
    },
)
