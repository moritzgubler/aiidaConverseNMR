# Quick Reference: Setting Up qe-converse with AiiDA

## The Complete Picture

```
┌─────────────────────────────────────────────────────────────┐
│  1. INSTALL PLUGIN (tells AiiDA HOW to use qe-converse)    │
│     pip install -e aiida-qe-converse/                       │
│     verdi plugin list aiida.calculations                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. SETUP CODE (tells AiiDA WHERE qe-converse is)           │
│     verdi code create core.code.installed \                 │
│       --label qe-converse \                                 │
│       --default-calc-job-plugin qeconverse \                │
│       --filepath-executable /path/to/qe-converse.x          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. RUN WORKFLOW (now AiiDA knows HOW and WHERE)            │
│     verdi run run_nmr_workchain.py                          │
└─────────────────────────────────────────────────────────────┘
```

## Installation Commands

```bash
# 1. Extract and install plugin
tar -xzf aiida-qe-converse.tar.gz
cd aiida-qe-converse
pip install -e .

# 2. Verify plugin is registered
verdi plugin list aiida.calculations | grep qeconverse
verdi plugin list aiida.parsers | grep qeconverse

# 3. Restart daemon
verdi daemon restart

# 4. Setup qe-converse code
verdi code create core.code.installed \
    --label qe-converse \
    --computer localhost \
    --default-calc-job-plugin qeconverse \
    --filepath-executable /path/to/qe-converse.x

# 5. Verify code
verdi code show qe-converse@localhost

# 6. Test the setup
verdi run test_nmr_workflow.py

# 7. Run your workflow
verdi run run_nmr_workchain.py
```

## What Each Component Does

| Component | Purpose | Location |
|-----------|---------|----------|
| **Plugin Package** | Tells AiiDA how to use qe-converse | `aiida-qe-converse.tar.gz` |
| **CalcJob Class** | Prepares input files, manages execution | Inside plugin package |
| **Parser Class** | Extracts results from output files | Inside plugin package |
| **setup.py** | Registers plugin with AiiDA | Inside plugin package |
| **WorkChain** | Orchestrates entire NMR calculation | `nmr_converse_workchain.py` |
| **Run Script** | Example of how to use the workchain | `run_nmr_workchain.py` |
| **Test Script** | Verifies everything is set up correctly | `test_nmr_workflow.py` |

## Your Question Answered

> "If I set up my qe-converse code in aiida, how does your toolchain know that it can use the code?"

**Answer:** You need BOTH:

1. **Code Setup** (WHERE the executable is):
   ```bash
   verdi code create ... --filepath-executable /path/to/qe-converse.x
   ```
   This tells AiiDA: "qe-converse.x is located here"

2. **Plugin Installation** (HOW to use the executable):
   ```bash
   pip install -e aiida-qe-converse/
   ```
   This tells AiiDA: "Here's how to create input files and parse output"

The plugin and code are linked via the `--default-calc-job-plugin qeconverse` flag when setting up the code.

## Flow in Your Workflow

```python
# In nmr_converse_workchain.py:

from aiida.plugins import CalculationFactory

# This line loads the plugin you installed
QeConverseCalculation = CalculationFactory('qeconverse')
                                          # ↑
                                          # This name comes from setup.py entry_points

# Submit a calculation
running = self.submit(QeConverseCalculation, 
                     code=self.inputs.converse_code,  # Uses the code you set up
                     parameters=params,
                     parent_folder=scf_folder)

# Behind the scenes:
# 1. QeConverseCalculation.prepare_for_submission() creates input file
# 2. AiiDA submits to the computer where the code is installed
# 3. qe-converse.x runs
# 4. QeConverseParser.parse() extracts chemical shifts from output
```

## Comparison: With vs Without Plugin

### Without Plugin (Your Bash Script)
```bash
# You manually:
1. Write input file
2. Submit job
3. Wait for completion
4. Parse output
5. Repeat for each atom/direction
```

### With Plugin (AiiDA)
```python
# AiiDA automatically:
1. Creates input file (via CalcJob.prepare_for_submission)
2. Submits job (via daemon)
3. Monitors completion (via daemon)
4. Parses output (via Parser.parse)
5. Parallelizes all calculations
```

## Common Mistakes

❌ **Setting up code WITHOUT installing plugin first:**
```bash
verdi code create ... --default-calc-job-plugin qeconverse  # Fails!
# Error: Plugin 'qeconverse' not found
```

✅ **Correct order:**
```bash
pip install -e aiida-qe-converse/  # Install plugin first
verdi daemon restart
verdi code create ... --default-calc-job-plugin qeconverse  # Now works!
```

---

❌ **Forgetting to restart daemon after installing plugin:**
```bash
pip install -e aiida-qe-converse/
verdi run run_nmr_workchain.py  # Might use cached version
```

✅ **Correct approach:**
```bash
pip install -e aiida-qe-converse/
verdi daemon restart  # Reload plugins
verdi run run_nmr_workchain.py  # Now uses new plugin
```

---

❌ **Using wrong plugin name:**
```python
QeConverse = CalculationFactory('qe-converse')  # Wrong! (has dash)
```

✅ **Correct name:**
```python
QeConverse = CalculationFactory('qeconverse')  # Correct! (no dash)
```

## Debugging Commands

```bash
# Check if plugin is registered
verdi plugin list aiida.calculations

# Check specific plugin details
verdi plugin list aiida.calculations qeconverse

# See what codes are available
verdi code list

# See code details (including which plugin it uses)
verdi code show qe-converse@localhost

# Test plugin in Python
python -c "from aiida.plugins import CalculationFactory; print(CalculationFactory('qeconverse'))"

# Check daemon status
verdi daemon status

# View daemon log (for errors)
verdi daemon logshow
```

## Files You Need

1. **`aiida-qe-converse.tar.gz`** - The plugin package (extract and install this)
2. **`nmr_converse_workchain.py`** - The main workflow
3. **`run_nmr_workchain.py`** - Script to submit the workflow
4. **`test_nmr_workflow.py`** - Script to test your setup

## Complete Setup Checklist

- [ ] AiiDA installed and configured (`verdi status`)
- [ ] Daemon running (`verdi daemon start`)
- [ ] Computer set up (`verdi computer list`)
- [ ] pw.x code set up (`verdi code show pw@localhost`)
- [ ] **Plugin extracted** (`tar -xzf aiida-qe-converse.tar.gz`)
- [ ] **Plugin installed** (`pip install -e aiida-qe-converse/`)
- [ ] **Plugin verified** (`verdi plugin list aiida.calculations | grep qeconverse`)
- [ ] **Daemon restarted** (`verdi daemon restart`)
- [ ] **qe-converse code set up** with plugin linked
- [ ] Code verified (`verdi code show qe-converse@localhost`)
- [ ] Pseudopotentials installed (`verdi data core.upf listfamilies`)
- [ ] Test passes (`verdi run test_nmr_workflow.py`)

Once all boxes are checked, you're ready to run your NMR workflow!
