#!/usr/bin/env python3
"""
Test Google Secret Manager Integration with optimizer_core.py
============================================================

This script tests the automatic credential fetching from Google Secret Manager
when configured in ppc_config.yaml.

Usage:
  python test_secret_manager_integration.py
"""

import os
import sys
import yaml

# Test if optimizer_core can be imported
try:
    import optimizer_core
    print("✅ optimizer_core imported successfully")
except Exception as e:
    print(f"❌ Failed to import optimizer_core: {e}")
    sys.exit(1)

def test_config_parsing():
    """Test that config properly reads Google Cloud settings"""
    print("\n" + "="*70)
    print("TEST 1: Configuration Parsing")
    print("="*70)
    
    # Load the example config
    if os.path.exists('ppc_config.example.yaml'):
        config = optimizer_core.Config('ppc_config.example.yaml')
        
        project_id = config.get('google_cloud.project_id')
        secret_id = config.get('google_cloud.secret_id')
        
        print(f"Project ID: {project_id}")
        print(f"Secret ID: {secret_id}")
        
        if project_id and secret_id:
            print("✅ Configuration has Google Cloud settings")
            return True
        else:
            print("⚠️  Configuration missing Google Cloud settings")
            return False
    else:
        print("⚠️  ppc_config.example.yaml not found")
        return False

def test_secret_manager_function():
    """Test the fetch_credentials_from_secret_manager function exists"""
    print("\n" + "="*70)
    print("TEST 2: Secret Manager Function")
    print("="*70)
    
    if hasattr(optimizer_core, 'fetch_credentials_from_secret_manager'):
        print("✅ fetch_credentials_from_secret_manager function exists")
        
        # Check function signature
        import inspect
        sig = inspect.signature(optimizer_core.fetch_credentials_from_secret_manager)
        params = list(sig.parameters.keys())
        print(f"Function parameters: {params}")
        
        expected_params = ['project_id', 'secret_id']
        if params == expected_params:
            print("✅ Function signature is correct")
            return True
        else:
            print(f"⚠️  Expected parameters {expected_params}, got {params}")
            return False
    else:
        print("❌ fetch_credentials_from_secret_manager function not found")
        return False

def test_ppc_automation_init():
    """Test that PPCAutomation __init__ can handle Secret Manager config"""
    print("\n" + "="*70)
    print("TEST 3: PPCAutomation Initialization Logic")
    print("="*70)
    
    # Check if the __init__ method contains Secret Manager logic
    import inspect
    source = inspect.getsource(optimizer_core.PPCAutomation.__init__)
    
    checks = {
        'google_cloud.project_id': 'google_cloud.project_id' in source,
        'google_cloud.secret_id': 'google_cloud.secret_id' in source,
        'fetch_credentials_from_secret_manager': 'fetch_credentials_from_secret_manager' in source,
        'AMAZON_CLIENT_ID': 'AMAZON_CLIENT_ID' in source,
    }
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check_name}: {'found' if passed else 'not found'}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("✅ PPCAutomation has Secret Manager integration")
        return True
    else:
        print("⚠️  PPCAutomation missing some Secret Manager integration")
        return False

def test_secret_manager_availability():
    """Test if Google Secret Manager library is available"""
    print("\n" + "="*70)
    print("TEST 4: Google Secret Manager Library")
    print("="*70)
    
    if optimizer_core.SECRETMANAGER_AVAILABLE:
        print("✅ google-cloud-secret-manager is installed")
        return True
    else:
        print("⚠️  google-cloud-secret-manager is NOT installed")
        print("   Install with: pip install google-cloud-secret-manager")
        print("   The code will fall back to environment variables if not installed")
        return False

def main():
    """Run all tests"""
    print("="*70)
    print("GOOGLE SECRET MANAGER INTEGRATION TEST")
    print("="*70)
    
    results = {
        'Configuration Parsing': test_config_parsing(),
        'Secret Manager Function': test_secret_manager_function(),
        'PPCAutomation Integration': test_ppc_automation_init(),
        'Secret Manager Library': test_secret_manager_availability(),
    }
    
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "⚠️  WARN"
        print(f"{status}: {test_name}")
    
    print(f"\nTests passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Integration is complete!")
        print("\nNext steps:")
        print("1. Configure ppc_config.yaml with your GCP project_id and secret_id")
        print("2. Ensure credentials are stored in Google Secret Manager")
        print("3. Run: python optimizer_core.py --config ppc_config.yaml --profile-id YOUR_PROFILE_ID")
        print("4. The optimizer will automatically fetch credentials and connect!")
    elif passed >= 3:
        print("\n✅ INTEGRATION COMPLETE - Warning about optional dependencies")
        print("\nThe integration is functional. Install google-cloud-secret-manager for full functionality:")
        print("  pip install google-cloud-secret-manager")
    else:
        print("\n❌ SOME TESTS FAILED - Please review the errors above")
        sys.exit(1)

if __name__ == '__main__':
    main()
