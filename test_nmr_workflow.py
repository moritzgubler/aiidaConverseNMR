"""
Simplified test script for the NMR converse workflow.

This script is useful for:
- Testing your AiiDA setup
- Debugging individual components
- Quick validation before running full calculations

Usage:
    verdi run test_nmr_workflow.py
"""

from aiida import orm, load_profile
from aiida.engine import run_get_node, submit
import sys

# Load AiiDA profile
load_profile()


def test_aiida_setup():
    """Test basic AiiDA configuration."""
    print("="*60)
    print("Testing AiiDA Setup")
    print("="*60)
    
    # Test profile
    try:
        profile = orm.Profile.get_profile()
        print(f"✓ Active profile: {profile.name}")
    except Exception as e:
        print(f"✗ Profile error: {e}")
        return False
    
    # Test daemon
    from aiida.engine.daemon.client import get_daemon_client
    client = get_daemon_client()
    if client.is_daemon_running:
        print(f"✓ Daemon is running")
    else:
        print(f"⚠ Daemon is not running. Start with: verdi daemon start")
    
    return True


def test_codes():
    """Test if required codes are available."""
    print("\n" + "="*60)
    print("Testing Codes")
    print("="*60)
    
    codes_ok = True
    
    # Test pw.x code
    try:
        pw_code = orm.load_code('qe-7.2@merlin')
        print(f"✓ pw.x code found: {pw_code.label}@{pw_code.computer.label}")
    except Exception as e:
        print(f"✗ pw.x code not found: {e}")
        print("  Set up with: verdi code create core.code.installed ...")
        codes_ok = False
    
    # Test qe-converse code
    try:
        conv_code = orm.load_code('qe-converse@merlin')
        print(f"✓ qe-converse code found: {conv_code.label}@{conv_code.computer.label}")
    except Exception as e:
        print(f"✗ qe-converse code not found: {e}")
        print("  Set up with: verdi code create core.code.installed ...")
        codes_ok = False
    
    return codes_ok


def test_pseudopotentials():
    """Test if pseudopotentials are available."""
    print("\n" + "="*60)
    print("Testing Pseudopotentials")
    print("="*60)
    
    from aiida.plugins import DataFactory
    UpfData = DataFactory('core.upf')
    
    # List available families
    from aiida.orm import QueryBuilder
    qb = QueryBuilder()
    qb.append(orm.Group, filters={'type_string': 'core.upf'})
    families = qb.all()
    
    if families:
        print(f"✓ Found {len(families)} pseudopotential families:")
        for (family,) in families[:5]:  # Show first 5
            print(f"  - {family.label}")
    else:
        print("✗ No pseudopotential families found")
        print("  Install with: aiida-pseudo install sssp")
        return False
    
    return True


def test_structure_creation():
    """Test creating a simple structure."""
    print("\n" + "="*60)
    print("Testing Structure Creation")
    print("="*60)
    
    try:
        # Create a simple test structure (single Na atom in a box)
        structure = orm.StructureData(cell=[
            [5.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
            [0.0, 0.0, 5.0]
        ])
        structure.append_atom(position=(0, 0, 0), symbols='Na')
        
        print(f"✓ Test structure created: {structure.get_formula()}")
        print(f"  Cell: {structure.cell}")
        print(f"  Atoms: {len(structure.sites)}")
        
        return structure
    except Exception as e:
        print(f"✗ Error creating structure: {e}")
        return None


def test_scf_inputs():
    """Test creating SCF input parameters."""
    print("\n" + "="*60)
    print("Testing SCF Input Parameters")
    print("="*60)
    
    try:
        parameters = {
            'CONTROL': {
                'calculation': 'scf',
                'prefix': 'test',
                'verbosity': 'high',
            },
            'SYSTEM': {
                'ecutwfc': 30.0,
                'ecutrho': 240.0,
                'nosym': True,
                'noinv': True,
            },
            'ELECTRONS': {
                'conv_thr': 1.0e-6,
            },
        }
        
        scf_params = orm.Dict(dict=parameters)
        print("✓ SCF parameters created successfully")
        print(f"  nosym: {parameters['SYSTEM']['nosym']} (must be True for NMR)")
        print(f"  noinv: {parameters['SYSTEM']['noinv']} (must be True for NMR)")
        
        return scf_params
    except Exception as e:
        print(f"✗ Error creating parameters: {e}")
        return None


def test_converse_inputs():
    """Test creating converse input parameters."""
    print("\n" + "="*60)
    print("Testing Converse Input Parameters")
    print("="*60)
    
    try:
        parameters = {
            'prefix': 'test',
            'q_gipaw': 0.01,
            'dudk_method': 'covariant',
            'mixing_beta': 0.5,
            'verbosity': 'high',
            'm_0': [1.0, 0.0, 0.0],  # x-direction
            'm_0_atom': 1,
        }
        
        conv_params = orm.Dict(dict={'input_qeconverse': parameters})
        print("✓ Converse parameters created successfully")
        print(f"  m_0: {parameters['m_0']}")
        print(f"  m_0_atom: {parameters['m_0_atom']}")
        
        return conv_params
    except Exception as e:
        print(f"✗ Error creating parameters: {e}")
        return None


def run_minimal_test():
    """
    Run a minimal test to verify the workflow structure.
    This doesn't actually submit calculations.
    """
    print("\n" + "="*60)
    print("Testing Workflow Structure")
    print("="*60)
    
    try:
        from nmr_converse_workchain import NmrConverseWorkChain
        print("✓ WorkChain imported successfully")
        
        # Check if all required inputs are defined
        spec = NmrConverseWorkChain.spec()
        required_inputs = [name for name, port in spec.inputs.items() 
                          if port.required]
        print(f"✓ Required inputs: {', '.join(required_inputs)}")
        
        # Check if outputs are defined
        output_names = list(spec.outputs.keys())
        print(f"✓ Expected outputs: {', '.join(output_names)}")
        
        return True
    except Exception as e:
        print(f"✗ Error testing workflow: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_minimal_inputs():
    """
    Create minimal valid inputs for the workflow.
    Useful for dry-run testing.
    """
    print("\n" + "="*60)
    print("Creating Minimal Inputs")
    print("="*60)
    
    try:
        # Codes
        pw_code = orm.load_code('qe-7.2@merlin')
        conv_code = orm.load_code('qe-converse@merlin')
        
        # Structure
        structure = orm.StructureData(cell=[
            [5.0, 0.0, 0.0],
            [0.0, 5.0, 0.0],
            [0.0, 0.0, 5.0]
        ])
        structure.append_atom(position=(0, 0, 0), symbols='Na')
        
        # Parameters
        scf_params = orm.Dict(dict={
            'CONTROL': {'calculation': 'scf', 'prefix': 'test'},
            'SYSTEM': {'ecutwfc': 30.0, 'nosym': True, 'noinv': True},
            'ELECTRONS': {'conv_thr': 1.0e-6},
        })
        
        conv_params = orm.Dict(dict={})
        
        # Pseudos (you need to have at least Na pseudo)
        # This will fail if you don't have pseudos - that's expected
        try:
            from aiida_quantumespresso.data.pseudopotential import get_pseudos_from_structure
            pseudos = get_pseudos_from_structure(structure, 'SSSP/1.3/PBE/efficiency')
            pseudos = orm.Dict(dict=pseudos)
        except ImportError:
            # Try newer API
            try:
                from aiida_pseudo.data.pseudo import get_pseudos_from_structure
                pseudos_dict = get_pseudos_from_structure(structure, 'SSSP/1.3/PBE/efficiency')
                pseudos = orm.Dict(dict={k: v.pk for k, v in pseudos_dict.items()})
            except:
                print("⚠ Could not load pseudopotentials - using dummy")
                pseudos = orm.Dict(dict={'Na': None})
        except:
            print("⚠ Could not load pseudopotentials - using dummy")
            pseudos = orm.Dict(dict={'Na': None})
        
        # Other inputs
        target_atoms = orm.List(list=[0])
        options = orm.Dict(dict={
            'resources': {'num_machines': 1, 'num_mpiprocs_per_machine': 1},
            'max_wallclock_seconds': 600,
        })
        
        inputs = {
            'structure': structure,
            'pw_code': pw_code,
            'converse_code': conv_code,
            'scf_parameters': scf_params,
            'converse_parameters': conv_params,
            'pseudos': pseudos,
            'target_atoms': target_atoms,
            'options': options,
        }
        
        print("✓ Minimal inputs created successfully")
        return inputs
        
    except Exception as e:
        print(f"✗ Error creating inputs: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print(" NMR Converse Workflow - Test Suite")
    print("="*70)
    
    all_ok = True
    
    # Run tests
    all_ok &= test_aiida_setup()
    all_ok &= test_codes()
    all_ok &= test_pseudopotentials()
    
    structure = test_structure_creation()
    all_ok &= (structure is not None)
    
    scf_params = test_scf_inputs()
    all_ok &= (scf_params is not None)
    
    conv_params = test_converse_inputs()
    all_ok &= (conv_params is not None)
    
    all_ok &= run_minimal_test()
    
    # Summary
    print("\n" + "="*70)
    print(" Test Summary")
    print("="*70)
    
    if all_ok:
        print("✓ All tests passed!")
        print("\nYou can now try:")
        print("  1. Create a real structure")
        print("  2. Adjust parameters in run_nmr_workchain.py")
        print("  3. Submit with: verdi run run_nmr_workchain.py")
    else:
        print("✗ Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  - Set up codes: verdi code create core.code.installed ...")
        print("  - Install pseudos: aiida-pseudo install sssp")
        print("  - Start daemon: verdi daemon start")
    
    print("\n" + "="*70)
    
    # Optional: Try to create inputs (will show if something is missing)
    print("\nAttempting to create minimal workflow inputs...")
    inputs = create_minimal_inputs()
    
    if inputs:
        print("\n✓ Minimal inputs created successfully!")
        print("  You can submit a test calculation with these inputs")
        print("  (though it may fail without proper pseudopotentials)")


if __name__ == '__main__':
    main()
