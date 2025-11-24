# AiiDA Workflow for NMR Chemical Shifts (Converse Approach)

This repository contains an AiiDA workflow for computing NMR chemical shifts using the converse approach with Quantum ESPRESSO and qe-converse.

## Overview

The workflow automates the calculation of NMR chemical shifts by:
1. Running a standard SCF calculation with Quantum ESPRESSO (with -k symmetry disabled)
2. Performing qe-converse calculations for each target atom in x, y, and z directions
3. Computing the isotropic shielding tensor for each atom

This replaces your bash script with a robust, reproducible, and provenance-tracking workflow management system.

## Files Included

- **`nmr_converse_workchain.py`**: Main WorkChain that orchestrates the entire calculation
- **`qe_converse_calcjob.py`**: AiiDA CalcJob plugin for qe-converse.x
- **`run_nmr_workchain.py`**: Example script showing how to submit the workflow
- **`test_nmr_workflow.py`**: Test script to verify your setup
- **`SETUP_GUIDE.md`**: Comprehensive setup and usage guide

## Quick Start

### 1. Prerequisites

Install AiiDA and required packages:

```bash
# Create virtual environment
python -m venv ~/aiida_env
source ~/aiida_env/bin/activate

# Install AiiDA
pip install aiida-core aiida-quantumespresso numpy ase

# Setup AiiDA
verdi quicksetup
verdi daemon start
```

### 2. Configure Your System

Set up codes and computer:

```bash
# Setup computer (local or remote cluster)
verdi computer setup
verdi computer configure core.local localhost

# Setup pw.x code
verdi code create core.code.installed \
    --label pw \
    --computer localhost \
    --default-calc-job-plugin quantumespresso.pw \
    --filepath-executable /path/to/pw.x

# Setup qe-converse.x code
verdi code create core.code.installed \
    --label qe-converse \
    --computer localhost \
    --filepath-executable /path/to/qe-converse.x

# Install pseudopotentials
aiida-pseudo install sssp -v 1.3 -x PBE -p efficiency
```

### 3. Test Your Setup

```bash
verdi run test_nmr_workflow.py
```

This will check:
- AiiDA configuration
- Code availability
- Pseudopotentials
- Workflow structure

### 4. Prepare Your Calculation

Edit `run_nmr_workchain.py` to:
- Load your structure (from CIF, XYZ, or create manually)
- Specify target atoms for chemical shift calculations
- Adjust computational parameters
- Set resource requirements

### 5. Submit the Workflow

```bash
verdi run run_nmr_workchain.py
```

### 6. Monitor Progress

```bash
# Show status
verdi process status <PK>

# Show detailed report
verdi process report <PK>

# List all processes
verdi process list

# Monitor in real-time
watch -n 5 'verdi process status <PK>'
```

### 7. Retrieve Results

```python
from aiida import orm

workchain = orm.load_node(<PK>)

if workchain.is_finished_ok:
    # Get isotropic shielding
    isotropic = workchain.outputs.isotropic_shielding.get_dict()
    
    for atom, values in isotropic.items():
        print(f"{atom}: {values['isotropic']:.3f} ppm")
```

Or use the provided retrieval function:

```bash
verdi run -c "from run_nmr_workchain import retrieve_results; retrieve_results(<PK>)"
```

## Workflow Architecture

```
NmrConverseWorkChain
│
├── setup()                      # Initialize workflow
│
├── run_scf()                    # Submit SCF calculation
│   └── PwBaseWorkChain          # Uses aiida-quantumespresso
│
├── inspect_scf()                # Check SCF completed
│
├── run_converse_calculations() # Submit N×3 converse jobs
│   ├── qe-converse (atom1_x)   # (N atoms × 3 directions)
│   ├── qe-converse (atom1_y)
│   ├── qe-converse (atom1_z)
│   └── ...
│
├── inspect_converse()           # Check all completed
│
├── compute_results()            # Parse and compute
│   └── compute_isotropic_shielding()
│
└── finalize()                   # Output results
```

## Key Features

### Compared to Bash Script

| Feature | Bash Script | AiiDA Workflow |
|---------|-------------|----------------|
| **Provenance** | None | Full tracking of all inputs/outputs |
| **Error Handling** | Manual | Automatic with recovery options |
| **Monitoring** | Log files | Database queries, web interface |
| **Reproducibility** | Requires documentation | Built-in with full input archive |
| **Parallelism** | Sequential | Automatic parallel job submission |
| **Scalability** | Limited | Designed for HPC clusters |
| **Results Management** | Manual file handling | Structured database storage |

### Advantages

1. **Provenance Tracking**: Every calculation is stored with full history
2. **Error Recovery**: Automatic restart capabilities
3. **Reproducibility**: Full input/output tracking
4. **Collaboration**: Easy sharing of calculations and results
5. **Analysis**: Query database for trends across many calculations
6. **Integration**: Works with HPC schedulers (SLURM, PBS, etc.)

## Customization

### Adding More Atoms

Simply modify the `target_atoms` list:

```python
target_atoms = orm.List(list=[0, 2, 3, 4, 5, 6])  # 0-indexed
```

### Adjusting Parameters

Modify the parameter dictionaries in `run_nmr_workchain.py`:

```python
def prepare_scf_parameters():
    parameters = {
        'SYSTEM': {
            'ecutwfc': 80.0,  # Increase cutoff
            'ecutrho': 640.0,
            # ... other parameters
        }
    }
```

### Using Different Codes

Change the code labels in `setup_codes()`:

```python
pw_code = orm.load_code('pw@supercomputer')
converse_code = orm.load_code('qe-converse@supercomputer')
```

## Troubleshooting

### Common Issues

**"Code not found"**
```bash
verdi code list  # Check available codes
verdi code show pw@localhost  # Verify code details
```

**"Pseudopotentials missing"**
```bash
verdi data core.upf listfamilies  # Check available families
aiida-pseudo install sssp  # Install SSSP library
```

**"Calculation failed"**
```bash
verdi process report <PK>  # See detailed error
verdi calcjob outputcat <PK>  # View output file
```

**"Parser errors"**
- Check that qe-converse output format matches expected format
- Modify `_parse_output()` in `qe_converse_calcjob.py` if needed

### Getting Help

- AiiDA Documentation: https://aiida.readthedocs.io
- AiiDA Quantum ESPRESSO: https://aiida-quantumespresso.readthedocs.io
- AiiDA Discourse: https://aiida.discourse.group

## Advanced Usage

### Batch Processing

Submit multiple structures:

```python
for structure_file in structure_files:
    structure = load_structure(structure_file)
    inputs = prepare_inputs(structure)
    workchain = submit(NmrConverseWorkChain, **inputs)
    print(f"Submitted {workchain.pk}")
```

### Custom Analysis

Query results across multiple calculations:

```python
from aiida import orm
from aiida.orm import QueryBuilder

qb = QueryBuilder()
qb.append(NmrConverseWorkChain, tag='wc', filters={'attributes.process_state': 'finished'})
qb.append(orm.Dict, with_incoming='wc', edge_filters={'label': 'isotropic_shielding'})

for wc, results in qb.all():
    print(f"Calculation {wc.pk}: {results.get_dict()}")
```

### Integration with Other Tools

Export to other formats:

```python
# Export to DataFrame
import pandas as pd

results = []
for workchain in workchains:
    iso = workchain.outputs.isotropic_shielding.get_dict()
    for atom, values in iso.items():
        results.append({
            'calculation': workchain.pk,
            'atom': atom,
            'isotropic': values['isotropic']
        })

df = pd.DataFrame(results)
df.to_csv('nmr_results.csv')
```

## Contributing

Feel free to:
- Report issues
- Suggest improvements
- Add features (e.g., spin-orbit coupling, error handlers)
- Improve documentation

## Citation

If you use this workflow, please cite:
- AiiDA: Computational Materials Science 43 (2018)
- Quantum ESPRESSO: J. Phys.: Condens. Matter 21, 395502 (2009)
- Your qe-converse reference

## License

This workflow is provided as-is for research purposes.

## Author

Generated for NMR chemical shift calculations using the converse approach.

## Comparison: Bash Script vs AiiDA Workflow

### Your Original Bash Script

**Advantages:**
- Simple and straightforward
- Easy to understand the flow
- Quick to set up

**Limitations:**
- No automatic error recovery
- Manual result collection
- No provenance tracking
- Difficult to reproduce
- Hard to scale to many systems
- Manual job monitoring

### AiiDA Workflow

**Advantages:**
- Automatic error handling and restart
- Full provenance tracking
- Easy result querying
- Built for reproducibility
- Scales to thousands of calculations
- Web interface for monitoring
- Integration with HPC schedulers
- Database of all results

**Learning Curve:**
- Initial setup takes more time
- Requires understanding AiiDA concepts
- More code complexity

**Recommendation:**
- Use bash script for: one-off calculations, quick tests
- Use AiiDA workflow for: production calculations, parameter studies, reproducible research

## Next Steps

1. Read `SETUP_GUIDE.md` for detailed setup instructions
2. Run `test_nmr_workflow.py` to verify your installation
3. Customize `run_nmr_workchain.py` for your system
4. Submit your first calculation
5. Explore AiiDA's advanced features

Happy computing! 🚀
