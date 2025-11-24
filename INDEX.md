# START HERE - AiiDA NMR Converse Workflow

Welcome! This package converts your bash script for NMR chemical shift calculations into a professional AiiDA workflow.

## 📋 What You Have

Your original bash script did:
1. Run SCF calculation with Quantum ESPRESSO
2. Loop over atoms and directions (x, y, z)
3. Run qe-converse for each atom/direction
4. Extract chemical shifts
5. Compute isotropic shielding

This package automates ALL of that with provenance tracking, error handling, and parallel execution.

## 🎯 Quick Start (5 Steps)

### Step 1: Read the Explanation
→ **[PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)** ← START HERE!

This answers your question: "How does AiiDA know how to use my code?"

### Step 2: Install the Plugin
→ **[PLUGIN_INSTALLATION.md](computer:///mnt/user-data/outputs/PLUGIN_INSTALLATION.md)**

Extract and install the plugin package:
```bash
tar -xzf aiida-qe-converse.tar.gz
cd aiida-qe-converse
pip install -e .
verdi daemon restart
```

### Step 3: Set Up Your Codes
→ **[QUICK_REFERENCE.md](computer:///mnt/user-data/outputs/QUICK_REFERENCE.md)**

Quick command reference for setting up codes and running the workflow.

### Step 4: Complete Setup
→ **[SETUP_GUIDE.md](computer:///mnt/user-data/outputs/SETUP_GUIDE.md)**

Comprehensive guide covering:
- AiiDA installation
- Computer configuration
- Pseudopotentials
- Troubleshooting

### Step 5: Run Your Workflow
→ **[README.md](computer:///mnt/user-data/outputs/README.md)**

Overview of the workflow and how to customize it for your needs.

## 📦 Files Included

### Essential Files
- **[aiida-qe-converse.tar.gz](computer:///mnt/user-data/outputs/aiida-qe-converse.tar.gz)** - Plugin package (MUST INSTALL FIRST!)
- **[nmr_converse_workchain.py](computer:///mnt/user-data/outputs/nmr_converse_workchain.py)** - Main workflow
- **[run_nmr_workchain.py](computer:///mnt/user-data/outputs/run_nmr_workchain.py)** - How to run it
- **[test_nmr_workflow.py](computer:///mnt/user-data/outputs/test_nmr_workflow.py)** - Test your setup

### Documentation
- **[PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)** - Understanding plugins (READ FIRST!)
- **[PLUGIN_INSTALLATION.md](computer:///mnt/user-data/outputs/PLUGIN_INSTALLATION.md)** - How to install
- **[QUICK_REFERENCE.md](computer:///mnt/user-data/outputs/QUICK_REFERENCE.md)** - Command cheatsheet
- **[SETUP_GUIDE.md](computer:///mnt/user-data/outputs/SETUP_GUIDE.md)** - Complete setup guide
- **[README.md](computer:///mnt/user-data/outputs/README.md)** - Project overview

### For Reference
- **[qe_converse_calcjob.py](computer:///mnt/user-data/outputs/qe_converse_calcjob.py)** - Plugin source (included in tarball)

## 🚀 Minimal Installation

If you just want to get started quickly:

```bash
# 1. Install AiiDA (if not already installed)
pip install aiida-core aiida-quantumespresso
verdi quicksetup
verdi daemon start

# 2. Extract and install the plugin
tar -xzf aiida-qe-converse.tar.gz
cd aiida-qe-converse
pip install -e .
verdi daemon restart

# 3. Set up your codes
verdi code create core.code.installed \
    --label pw \
    --computer localhost \
    --default-calc-job-plugin quantumespresso.pw \
    --filepath-executable /path/to/pw.x

verdi code create core.code.installed \
    --label qe-converse \
    --computer localhost \
    --default-calc-job-plugin qeconverse \
    --filepath-executable /path/to/qe-converse.x

# 4. Install pseudopotentials
aiida-pseudo install sssp -v 1.3 -x PBE -p efficiency

# 5. Test everything
verdi run test_nmr_workflow.py

# 6. Customize and run
# Edit run_nmr_workchain.py with your structure and parameters
verdi run run_nmr_workchain.py
```

## 🔑 Key Concepts

### The Plugin System (Most Important!)

AiiDA needs to know TWO things about qe-converse:

1. **WHERE** is it? → Code setup (`verdi code create`)
2. **HOW** to use it? → Plugin installation (`pip install`)

The plugin teaches AiiDA:
- How to write qe-converse input files
- How to parse qe-converse output files
- What inputs/outputs to expect

See **[PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)** for details!

### The Workflow

Your workflow now:
- ✓ Runs SCF automatically
- ✓ Submits ALL converse calculations in parallel
- ✓ Tracks full provenance
- ✓ Handles errors automatically
- ✓ Stores results in database
- ✓ Enables reproducibility

## 📊 Comparison

| Bash Script | AiiDA Workflow |
|-------------|----------------|
| Sequential execution | Parallel execution |
| Manual error checking | Automatic error handling |
| No provenance | Full provenance tracking |
| Hard to reproduce | Easily reproducible |
| Manual result collection | Automatic database storage |
| Local only | Works on HPC clusters |

## 🆘 Getting Help

**Problems installing?**
→ See [PLUGIN_INSTALLATION.md](computer:///mnt/user-data/outputs/PLUGIN_INSTALLATION.md) troubleshooting section

**Commands not working?**
→ See [QUICK_REFERENCE.md](computer:///mnt/user-data/outputs/QUICK_REFERENCE.md) for correct syntax

**Don't understand plugins?**
→ See [PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)

**Need complete setup?**
→ See [SETUP_GUIDE.md](computer:///mnt/user-data/outputs/SETUP_GUIDE.md)

## 📝 Recommended Reading Order

1. **[PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)** - Understand the core concept
2. **[PLUGIN_INSTALLATION.md](computer:///mnt/user-data/outputs/PLUGIN_INSTALLATION.md)** - Install the plugin
3. **[QUICK_REFERENCE.md](computer:///mnt/user-data/outputs/QUICK_REFERENCE.md)** - Quick commands
4. **[SETUP_GUIDE.md](computer:///mnt/user-data/outputs/SETUP_GUIDE.md)** - Complete setup (if needed)
5. **[README.md](computer:///mnt/user-data/outputs/README.md)** - Understand the workflow

## ✅ Checklist

Before running your workflow:

- [ ] Read PLUGIN_EXPLANATION.md (understand plugin system)
- [ ] Install plugin package (`pip install -e aiida-qe-converse/`)
- [ ] Verify plugin (`verdi plugin list aiida.calculations | grep qeconverse`)
- [ ] Restart daemon (`verdi daemon restart`)
- [ ] Set up pw.x code
- [ ] Set up qe-converse code with `--default-calc-job-plugin qeconverse`
- [ ] Install pseudopotentials
- [ ] Test setup (`verdi run test_nmr_workflow.py`)
- [ ] Customize run_nmr_workchain.py
- [ ] Submit! (`verdi run run_nmr_workchain.py`)

## 🎓 Learning Resources

- AiiDA docs: https://aiida.readthedocs.io
- AiiDA Quantum ESPRESSO: https://aiida-quantumespresso.readthedocs.io
- AiiDA tutorials: https://aiida-tutorials.readthedocs.io

## 💡 Pro Tips

1. **Always install the plugin BEFORE setting up the code**
2. **Restart the daemon after installing plugins**
3. **Use `verdi process status <PK>` to monitor workflows**
4. **Test on a small system first**
5. **Check `verdi daemon logshow` if something goes wrong**

## 🙋 Your Question Answered

> "If I set up my qe-converse code in aiida, how does your toolchain know that it can use the code?"

**Short answer:** You need to install the plugin package first. The plugin teaches AiiDA HOW to use qe-converse. The code setup tells AiiDA WHERE qe-converse is. Together, they let AiiDA run your calculations.

**Long answer:** Read [PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)!

---

**Ready to start? → [PLUGIN_EXPLANATION.md](computer:///mnt/user-data/outputs/PLUGIN_EXPLANATION.md)**

Good luck! 🚀
