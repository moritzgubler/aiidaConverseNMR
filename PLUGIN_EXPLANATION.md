# Summary: How the AiiDA Plugin System Works

## Your Question

> "If I set up my qe-converse code in aiida, how does your toolchain know that it can use the code?"

## The Answer

AiiDA needs **two separate pieces of information**:

### 1. WHERE is the executable? (Code Setup)
```bash
verdi code create core.code.installed \
    --label qe-converse \
    --filepath-executable /path/to/qe-converse.x
```

This creates a database entry saying: "There's an executable called qe-converse.x at this location"

### 2. HOW do I use it? (Plugin Installation)
```bash
pip install -e aiida-qe-converse/
```

This registers Python classes that know:
- How to write input files for qe-converse
- How to parse output files from qe-converse
- What inputs/outputs to expect

## The Connection

When you set up the code, you specify which plugin to use:

```bash
verdi code create core.code.installed \
    --label qe-converse \
    --default-calc-job-plugin qeconverse \  # ← Links code to plugin
    --filepath-executable /path/to/qe-converse.x
```

The `--default-calc-job-plugin qeconverse` tells AiiDA: "Use the 'qeconverse' plugin (which you installed with pip) to interact with this executable"

## What Happens in Your Workflow

```python
# 1. Your workflow asks for the plugin
from aiida.plugins import CalculationFactory
QeConverseCalculation = CalculationFactory('qeconverse')
                                           # ↑ Finds plugin from setup.py

# 2. Your workflow uses the code
running = self.submit(QeConverseCalculation,
                     code=converse_code,  # ← The executable location
                     parameters=params)

# 3. Behind the scenes:
# - QeConverseCalculation writes input file using params
# - AiiDA runs /path/to/qe-converse.x with that input
# - QeConverseParser reads the output file
# - Results are stored in AiiDA database
```

## Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. Install Plugin Package                                        │
│    pip install -e aiida-qe-converse/                             │
│                                                                   │
│    This installs:                                                │
│    - QeConverseCalculation (how to create input)                 │
│    - QeConverseParser (how to read output)                       │
│                                                                   │
│    And registers entry point in setup.py:                        │
│    'qeconverse' → QeConverseCalculation                          │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 2. Restart Daemon                                                 │
│    verdi daemon restart                                           │
│                                                                   │
│    Ensures daemon knows about new plugin                         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 3. Setup Code (Link executable to plugin)                        │
│    verdi code create core.code.installed \                       │
│      --label qe-converse \                                       │
│      --default-calc-job-plugin qeconverse \  ← Links to plugin   │
│      --filepath-executable /path/to/qe-converse.x                │
│                                                                   │
│    Creates database entry:                                       │
│    Code(label='qe-converse',                                     │
│         executable='/path/to/qe-converse.x',                     │
│         plugin='qeconverse')                                     │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 4. Use in Workflow                                                │
│    from aiida.plugins import CalculationFactory                  │
│    QeConverseCalc = CalculationFactory('qeconverse')             │
│                          ↓                                        │
│                     Finds plugin from registry                   │
│                          ↓                                        │
│    self.submit(QeConverseCalc,                                   │
│               code=converse_code)  ← Uses registered code        │
│                          ↓                                        │
│                     AiiDA connects:                              │
│                     - Plugin (how to use)                        │
│                     - Code (where it is)                         │
└──────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────┐
│ 5. Execution                                                      │
│                                                                   │
│    QeConverseCalculation.prepare_for_submission():               │
│    - Creates input file from parameters                          │
│    - Sets up file retrieval                                      │
│    - Links to parent SCF folder                                  │
│                          ↓                                        │
│    AiiDA submits job:                                            │
│    - Copies files to compute node                                │
│    - Runs /path/to/qe-converse.x < input > output               │
│    - Retrieves output files                                      │
│                          ↓                                        │
│    QeConverseParser.parse():                                     │
│    - Reads output file                                           │
│    - Extracts chemical shift values                              │
│    - Stores in database                                          │
└──────────────────────────────────────────────────────────────────┘
```

## The Plugin Package Contents

```
aiida-qe-converse/
│
├── setup.py                      # Registration file
│   Contains:
│   entry_points={
│     'aiida.calculations': [
│       'qeconverse = aiida_qe_converse.calculations.qeconverse:QeConverseCalculation'
│     ],
│     'aiida.parsers': [
│       'qeconverse = aiida_qe_converse.parsers.qeconverse:QeConverseParser'
│     ]
│   }
│
└── aiida_qe_converse/
    │
    ├── calculations/
    │   └── qeconverse.py         # QeConverseCalculation class
    │       - define(): Declares inputs/outputs
    │       - prepare_for_submission(): Creates input files
    │       - _generate_input_file(): Formats parameters
    │
    └── parsers/
        └── qeconverse.py         # QeConverseParser class
            - parse(): Reads output file
            - _parse_output(): Extracts data
```

## Why Both Are Needed

| Without Code Setup | Without Plugin | With Both |
|-------------------|----------------|-----------|
| AiiDA doesn't know WHERE executable is | AiiDA doesn't know HOW to use it | ✓ Complete |
| Can't run anything | Could run manually but can't automate | ✓ Automated |
| ❌ | ❌ | ✓ |

## Analogy

Think of it like a phone:

- **Code Setup** = Having someone's phone number
  - You know WHERE to reach them
  
- **Plugin** = Knowing their language
  - You know HOW to communicate

You need BOTH to have a conversation!

## Files Provided

1. **aiida-qe-converse.tar.gz** - The plugin package (install with pip)
2. **PLUGIN_INSTALLATION.md** - Detailed installation instructions
3. **QUICK_REFERENCE.md** - Quick command reference
4. **nmr_converse_workchain.py** - Main workflow
5. **run_nmr_workchain.py** - Example submission script
6. **test_nmr_workflow.py** - Setup verification script

## Installation Order (Critical!)

```bash
# STEP 1: Install plugin FIRST
tar -xzf aiida-qe-converse.tar.gz
cd aiida-qe-converse
pip install -e .

# STEP 2: Verify plugin is registered
verdi plugin list aiida.calculations | grep qeconverse

# STEP 3: Restart daemon
verdi daemon restart

# STEP 4: Setup code (linking to plugin)
verdi code create core.code.installed \
    --default-calc-job-plugin qeconverse \  # Must match plugin name!
    --filepath-executable /path/to/qe-converse.x

# STEP 5: Verify everything
verdi code show qe-converse@localhost  # Should show plugin: qeconverse
```

## Common Confusion

**Q: "I already have qe-converse.x installed. Why do I need a plugin?"**

**A:** qe-converse.x is a standalone program. It doesn't know anything about AiiDA. The plugin is the translator that:
- Speaks qe-converse's language (input file format)
- Translates AiiDA's data structures into qe-converse input
- Translates qe-converse output back into AiiDA's data structures

**Q: "Can't AiiDA just figure out how to use my code?"**

**A:** No. Every code has different:
- Input file formats
- Output file formats
- Required parameters
- Ways of reporting results

The plugin teaches AiiDA these specifics for YOUR code.

**Q: "Do I need to write a plugin for pw.x too?"**

**A:** No! The `aiida-quantumespresso` package you already installed includes plugins for pw.x, cp.x, etc. That's why pw.x "just works" - someone already wrote those plugins for you.

## Summary

Your question revealed that you needed to understand **plugin registration**. Here's the key insight:

```
Code Setup  →  Tells AiiDA WHERE
Plugin      →  Tells AiiDA HOW
Both        →  Lets AiiDA actually USE the code
```

Without the plugin, AiiDA would be like having a phone number (code location) but not knowing what language to speak (how to format inputs/parse outputs).

The plugin package I provided gives AiiDA the "instruction manual" for qe-converse, so it can automatically:
- Write properly formatted input files
- Submit jobs
- Parse output files
- Extract chemical shifts
- Store everything in the database

All without you having to manually handle any files!
