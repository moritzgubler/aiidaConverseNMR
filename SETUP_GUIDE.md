# AiiDA NMR Converse Workflow - Setup and Usage Guide

This guide will help you set up and use the AiiDA workflow for computing NMR chemical shifts using the converse approach with Quantum ESPRESSO.

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Setting Up AiiDA](#setting-up-aiida)
4. [Configuring Codes](#configuring-codes)
5. [Running the Workflow](#running-the-workflow)
6. [Monitoring and Results](#monitoring-and-results)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.9+** installed
- **Quantum ESPRESSO** (pw.x) compiled and accessible
- **qe-converse.x** compiled and accessible
- **PostgreSQL** database (for AiiDA)
- **RabbitMQ** message broker (for AiiDA workflows)
- Access to a computing cluster (or local machine for testing)

---

## Installation

### 1. Install AiiDA

```bash
# Create a virtual environment (recommended)
python -m venv ~/aiida_env
source ~/aiida_env/bin/activate

# Install AiiDA
pip install aiida-core aiida-quantumespresso

# Verify installation
verdi status
```

### 2. Install Required Python Packages

```bash
pip install numpy ase pymatgen  # For structure manipulation
pip install pgsu  # Optional, for easier PostgreSQL setup
```

### 3. Set Up PostgreSQL and RabbitMQ

#### PostgreSQL (if not already installed)
```bash
# On Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# On macOS
brew install postgresql

# Start PostgreSQL
sudo systemctl start postgresql  # Linux
brew services start postgresql   # macOS
```

#### RabbitMQ (if not already installed)
```bash
# On Ubuntu/Debian
sudo apt-get install rabbitmq-server

# On macOS
brew install rabbitmq

# Start RabbitMQ
sudo systemctl start rabbitmq-server  # Linux
brew services start rabbitmq          # macOS
```

---

## Setting Up AiiDA

### 1. Create an AiiDA Profile

```bash
# Quick setup (interactive)
verdi quicksetup

# Or manual setup
verdi setup --profile my_profile \
    --email your.email@example.com \
    --first-name Your \
    --last-name Name \
    --institution "Your Institution"

# Set as default profile
verdi profile setdefault my_profile
```

### 2. Start the AiiDA Daemon

The daemon manages job submissions and monitors calculations:

```bash
# Start the daemon
verdi daemon start

# Check daemon status
verdi daemon status

# To stop the daemon later
verdi daemon stop
```

### 3. Set Up a Computer

Configure the computer where calculations will run:

```bash
# Interactive setup
verdi computer setup

# Example for a local computer:
# Computer name: localhost
# Hostname: localhost
# Transport: core.local
# Scheduler: core.direct
# Work directory: /tmp/aiida_work
```

Then configure the computer:

```bash
verdi computer configure core.local localhost
# Follow prompts (for local: just press Enter for defaults)

# Test the computer
verdi computer test localhost
```

For remote clusters, use SSH transport:

```bash
verdi computer setup
# Computer name: cluster
# Hostname: cluster.university.edu
# Transport: core.ssh
# Scheduler: core.slurm (or core.pbs, etc.)
# Work directory: /scratch/username/aiida_work

# Configure SSH
verdi computer configure core.ssh cluster
# Enter SSH username, key file, etc.
```

---

## Configuring Codes

### 1. Set Up pw.x Code

```bash
verdi code create core.code.installed \
    --label pw \
    --computer localhost \
    --default-calc-job-plugin quantumespresso.pw \
    --filepath-executable /path/to/pw.x \
    --prepend-text "module load quantumespresso" \
    --append-text ""

# Verify
verdi code list
verdi code show pw@localhost
```

### 2. Set Up qe-converse.x Code

Since qe-converse might not have a built-in plugin, you can set it up as a generic code:

```bash
verdi code create core.code.installed \
    --label qe-converse \
    --computer localhost \
    --filepath-executable /path/to/qe-converse.x \
    --prepend-text "module load quantumespresso" \
    --append-text ""
```

### 3. Upload Pseudopotentials

Download pseudopotentials (e.g., from SSSP) and upload to AiiDA:

```bash
# Option 1: Upload from SSSP library (recommended)
aiida-pseudo install sssp -v 1.3 -x PBE -p efficiency

# Option 2: Upload your own pseudo family
verdi data core.upf uploadfamily /path/to/pseudo/folder "My_Pseudos" "Description"

# Verify
verdi data core.upf listfamilies
```

---

## Running the Workflow

### 1. Prepare Your Structure

Create a file to define your structure (e.g., `structure_setup.py`):

```python
from aiida import orm
from ase.io import read

# Load structure from file
ase_structure = read('na3ir3o8.cif')
structure = orm.StructureData(ase=ase_structure)
structure.store()

print(f"Structure stored with PK: {structure.pk}")
```

Run it:
```bash
verdi run structure_setup.py
```

### 2. Copy the Workflow Files

Copy the provided files to your working directory:
- `nmr_converse_workchain.py`
- `qe_converse_calcjob.py`
- `run_nmr_workchain.py`

### 3. Customize the Run Script

Edit `run_nmr_workchain.py` to match your setup:

```python
def setup_codes():
    """Update with your code labels"""
    pw_code = orm.load_code('pw@localhost')  # Your pw.x code
    converse_code = orm.load_code('qe-converse@localhost')  # Your qe-converse code
    return pw_code, converse_code

def create_structure():
    """Load your structure"""
    structure = orm.load_node(YOUR_STRUCTURE_PK)  # From step 1
    return structure

def get_pseudopotentials():
    """Use your pseudo family"""
    pseudo_family_name = 'SSSP/1.3/PBE/efficiency'  # Your family name
    # ... rest of function
```

### 4. Submit the Workflow

```bash
verdi run run_nmr_workchain.py
```

Or in interactive Python:

```python
from aiida import orm, load_profile
load_profile()

# Import and run
from run_nmr_workchain import main
workchain = main()
```

---

## Monitoring and Results

### Monitoring the Workflow

```bash
# Show workchain details
verdi process show <PK>

# Show hierarchical status
verdi process status <PK>

# Show detailed report
verdi process report <PK>

# Monitor in real-time
watch -n 5 'verdi process status <PK>'

# List all running processes
verdi process list
```

### Retrieving Results

Once completed, retrieve results:

```python
from aiida import orm

# Load the workchain
workchain = orm.load_node(PK)

# Check if successful
if workchain.is_finished_ok:
    # Get chemical shifts
    chemical_shifts = workchain.outputs.chemical_shifts.get_dict()
    
    # Get isotropic shielding
    isotropic = workchain.outputs.isotropic_shielding.get_dict()
    
    # Print results
    for atom, values in isotropic.items():
        print(f"{atom}: {values['isotropic']:.3f} ppm")
```

Or use the provided function:

```bash
verdi run -c "from run_nmr_workchain import retrieve_results; retrieve_results(<PK>)"
```

### Export Results

Results are automatically exported to JSON:

```bash
# Results file: nmr_results_<PK>.json
cat nmr_results_<PK>.json
```

---

## Troubleshooting

### Common Issues

#### 1. "Code not found"
```bash
# List all codes
verdi code list

# If missing, set up the code again
verdi code create core.code.installed ...
```

#### 2. "Structure not valid"
```bash
# Check structure
verdi data core.structure show <PK>

# Verify it has all required atoms and cell parameters
```

#### 3. "Pseudopotentials missing"
```bash
# List available pseudo families
verdi data core.upf listfamilies

# Show which elements are in a family
verdi data core.upf show <FAMILY_NAME>
```

#### 4. Workchain fails at SCF step
- Check SCF parameters (especially `nosym` and `noinv` must be True)
- Verify pseudopotentials are correct
- Check computational resources
- Look at the SCF output: `verdi calcjob outputcat <SCF_PK>`

#### 5. Workchain fails at converse step
- Check that SCF completed successfully
- Verify qe-converse code is correctly configured
- Check that `outdir` is accessible and contains SCF results
- Look at converse output: `verdi calcjob outputcat <CONVERSE_PK>`

#### 6. Parser errors
- The output parser might need adjustment based on your qe-converse output format
- Check the actual output: `verdi calcjob outputcat <PK>`
- Modify `_parse_output()` in `qe_converse_calcjob.py` if needed

### Debugging Tips

```bash
# Get full error information
verdi process report <PK>

# Open Python shell with AiiDA loaded
verdi shell

# In the shell, inspect nodes
from aiida import orm
node = orm.load_node(PK)
node.outputs  # See available outputs
node.inputs   # See inputs
node.exit_status  # Check exit status
```

### Getting Help

```bash
# AiiDA help
verdi --help
verdi <command> --help

# Check daemon logs
verdi daemon logshow

# Database maintenance
verdi database summary
```

---

## Advanced Usage

### Running Multiple Workflows

You can submit multiple workflows for different structures or parameters:

```python
structures = [structure1, structure2, structure3]
workchains = []

for structure in structures:
    inputs = prepare_inputs(structure)
    wc = submit(NmrConverseWorkChain, **inputs)
    workchains.append(wc)
    print(f"Submitted {wc.pk} for {structure.get_formula()}")
```

### Customizing the Workflow

You can modify `nmr_converse_workchain.py` to:
- Add different magnetic field directions
- Include spin-orbit coupling (lambda_so)
- Add error handlers for automatic restarts
- Implement adaptive convergence parameters

### Batch Processing

For large-scale calculations, consider using AiiDA's `WorkChain` features:
- Checkpointing
- Error recovery
- Dynamic resource allocation
- Results caching

---

## File Structure Summary

```
your_project/
├── nmr_converse_workchain.py    # Main workchain
├── qe_converse_calcjob.py       # CalcJob plugin for qe-converse
├── run_nmr_workchain.py         # Example submission script
├── structure_setup.py           # Structure preparation
└── results/
    └── nmr_results_<PK>.json    # Exported results
```

---

## Next Steps

1. Test the workflow on a small system first
2. Verify the chemical shift values against known benchmarks
3. Optimize computational parameters (k-points, cutoffs, etc.)
4. Scale up to your production systems

For more information:
- AiiDA documentation: https://aiida.readthedocs.io
- AiiDA Quantum ESPRESSO: https://aiida-quantumespresso.readthedocs.io
- AiiDA tutorials: https://aiida-tutorials.readthedocs.io
