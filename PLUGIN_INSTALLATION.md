# Installing the qe-converse AiiDA Plugin

## Understanding the Problem

When you set up a code in AiiDA with:

```bash
verdi code create core.code.installed --label qe-converse ...
```

You're only telling AiiDA **where the executable is**. You're NOT telling it:
- How to prepare input files
- How to parse output files  
- What the calculation expects

This is why we need a **plugin** - it's the "instruction manual" for AiiDA to use your code.

## The Solution: Install the Plugin

### Method 1: Install as Local Package (Recommended for Development)

1. **Navigate to the plugin directory:**
   ```bash
   cd /path/to/plugin/directory  # Where setup.py is located
   ```

2. **Install in development mode:**
   ```bash
   pip install -e .
   ```

   The `-e` flag means "editable" - changes to the code take effect immediately.

3. **Verify the plugin is registered:**
   ```bash
   verdi plugin list aiida.calculations
   ```
   
   You should see `qeconverse` in the list.

   ```bash
   verdi plugin list aiida.parsers
   ```
   
   You should also see `qeconverse` here.

### Method 2: Install as Regular Package

1. **Install the package:**
   ```bash
   pip install /path/to/plugin/directory
   ```

2. **Verify as above**

### Method 3: Manual Registration (Quick Test)

If you want to test without installing, you can register manually in your script:

```python
from aiida.plugins import CalculationFactory, ParserFactory
from aiida_qe_converse.calculations.qeconverse import QeConverseCalculation
from aiida_qe_converse.parsers.qeconverse import QeConverseParser

# Now you can use them
QeConverse = CalculationFactory('qeconverse')
```

But this is NOT recommended for production use.

## Complete Installation Process

### Step-by-Step

```bash
# 1. Activate your AiiDA virtual environment
source ~/aiida_env/bin/activate

# 2. Navigate to where you saved the plugin files
cd /path/to/aiida-qe-converse

# 3. Verify the structure looks like this:
# aiida-qe-converse/
# ├── setup.py
# └── aiida_qe_converse/
#     ├── __init__.py
#     ├── calculations/
#     │   ├── __init__.py
#     │   └── qeconverse.py
#     └── parsers/
#         ├── __init__.py
#         └── qeconverse.py

ls -R

# 4. Install the plugin
pip install -e .

# 5. Verify installation
verdi plugin list aiida.calculations | grep qeconverse
verdi plugin list aiida.parsers | grep qeconverse

# 6. Restart the daemon (important!)
verdi daemon restart
```

## Setting Up the Code (After Plugin Installation)

Now that AiiDA knows HOW to use qe-converse, you can set up WHERE it is:

```bash
verdi code create core.code.installed \
    --label qe-converse \
    --computer localhost \
    --default-calc-job-plugin qeconverse \
    --filepath-executable /path/to/qe-converse.x \
    --prepend-text "module load quantumespresso" \
    --append-text ""
```

**Important:** Note the `--default-calc-job-plugin qeconverse` - this links the code to your plugin!

## Verify Everything Works

### Test 1: Check Plugin Registration

```bash
verdi plugin list aiida.calculations qeconverse
```

Should show:
```
Registered entry points for aiida.calculations:
* qeconverse
```

### Test 2: Check Code Setup

```bash
verdi code show qe-converse@localhost
```

Should show:
```
Default calculation plugin: qeconverse
```

### Test 3: Test in Python

```python
from aiida import load_profile
load_profile()

from aiida.plugins import CalculationFactory

# This should work without error
QeConverse = CalculationFactory('qeconverse')
print(f"Plugin loaded: {QeConverse}")
```

## Troubleshooting

### "Plugin 'qeconverse' not found"

**Cause:** Plugin not installed or AiiDA can't find it.

**Solution:**
```bash
# Reinstall the plugin
pip uninstall aiida-qe-converse
pip install -e /path/to/plugin

# Restart daemon
verdi daemon restart

# Clear cache
verdi daemon stop
rm -rf ~/.aiida/daemon/*
verdi daemon start
```

### "Entry point 'qeconverse' not found"

**Cause:** The `setup.py` wasn't read correctly.

**Solution:**
```bash
# Check setup.py has correct entry_points
cat setup.py

# Make sure entry_points section looks like:
#     entry_points={
#         'aiida.calculations': [
#             'qeconverse = aiida_qe_converse.calculations.qeconverse:QeConverseCalculation',
#         ],
#         ...
#     }

# Reinstall
pip install -e . --force-reinstall
```

### "Module 'aiida_qe_converse' not found"

**Cause:** Package structure is wrong or Python can't find it.

**Solution:**
```bash
# Check if package is in Python path
python -c "import aiida_qe_converse; print(aiida_qe_converse.__file__)"

# If not found, reinstall
pip install -e . --force-reinstall

# Or add to PYTHONPATH temporarily
export PYTHONPATH=/path/to/plugin:$PYTHONPATH
```

### Code setup fails

**Cause:** Plugin must be installed BEFORE setting up the code.

**Solution:**
```bash
# If you already set up the code, delete it
verdi code delete qe-converse@localhost

# Install plugin first
pip install -e .

# Then set up code again
verdi code create core.code.installed ...
```

## Package Structure Explained

```
aiida-qe-converse/           # Root directory
│
├── setup.py                 # Tells Python/AiiDA how to install
│                            # Contains entry_points that register plugins
│
└── aiida_qe_converse/       # Main package directory
    │
    ├── __init__.py          # Makes this a Python package
    │
    ├── calculations/        # CalcJob plugins
    │   ├── __init__.py
    │   └── qeconverse.py    # Defines how to run qe-converse
    │                        # (input file generation, file handling)
    │
    └── parsers/             # Parser plugins  
        ├── __init__.py
        └── qeconverse.py    # Defines how to parse qe-converse output
                             # (extracts chemical shifts, checks convergence)
```

## How It All Works Together

1. **setup.py** registers entry points:
   - `'qeconverse' = 'aiida_qe_converse.calculations.qeconverse:QeConverseCalculation'`
   - This tells AiiDA: "When someone asks for 'qeconverse' calculation, use this class"

2. **QeConverseCalculation** class:
   - Knows how to create input files for qe-converse
   - Knows what files to retrieve
   - Knows how to link to parent folder (SCF results)

3. **QeConverseParser** class:
   - Knows how to read qe-converse output
   - Extracts chemical shift values
   - Checks for errors/convergence

4. **verdi code create**:
   - Links the plugin (`qeconverse`) to the actual executable (`/path/to/qe-converse.x`)
   - Now AiiDA can run calculations!

5. **Your workflow**:
   - Uses `CalculationFactory('qeconverse')` to get the plugin
   - Submits calculations using the plugin
   - Plugin handles all the details

## Alternative: Using the Plugin Without Installation

If you can't install or want to test quickly, you can import directly:

```python
import sys
sys.path.insert(0, '/path/to/aiida-qe-converse')

from aiida_qe_converse.calculations.qeconverse import QeConverseCalculation

# Use directly in workflow
running = self.submit(QeConverseCalculation, **inputs)
```

But this is **NOT recommended** because:
- Not portable
- No automatic discovery
- Harder to maintain
- Won't work with `verdi code` defaults

## Summary

**Before plugin installation:**
- AiiDA knows qe-converse.x exists (the executable)
- AiiDA doesn't know HOW to use it

**After plugin installation:**
- AiiDA knows WHERE qe-converse.x is (the code)
- AiiDA knows HOW to use it (the plugin)
- You can submit calculations!

The plugin is the bridge between AiiDA and your code.
