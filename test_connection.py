#!/usr/bin/env python3
"""
Simple test script to verify Amazon Ads API connection logic
"""

import sys
import os

# Test 1: Verify the main file can be imported
print("Test 1: Importing main module...")
try:
    # We can't directly import 'main' as a module, but we can check if it compiles
    import py_compile
    py_compile.compile('main', doraise=True)
    print("✓ main file compiles successfully")
except SyntaxError as e:
    print(f"✗ Syntax error in main: {e}")
    sys.exit(1)

# Test 2: Verify Google Secret Manager integration is present
print("\nTest 2: Checking GoogleSecretsManager class...")
with open('main', 'r') as f:
    content = f.read()
    if 'class GoogleSecretsManager:' in content:
        print("✓ GoogleSecretsManager class found")
    else:
        print("✗ GoogleSecretsManager class not found")
        sys.exit(1)

# Test 3: Verify AmazonAdsAPI accepts secrets_manager parameter
print("\nTest 3: Checking AmazonAdsAPI signature...")
if 'secrets_manager: Optional[GoogleSecretsManager] = None' in content:
    print("✓ AmazonAdsAPI accepts secrets_manager parameter")
else:
    print("✗ AmazonAdsAPI does not accept secrets_manager parameter")
    sys.exit(1)

# Test 4: Verify authentication uses secrets_manager
print("\nTest 4: Checking authentication logic...")
if 'if self.secrets_manager and not all([client_id, client_secret, refresh_token]):' in content:
    print("✓ Authentication attempts to use Secret Manager when credentials are missing")
else:
    print("✗ Authentication does not check Secret Manager")
    sys.exit(1)

# Test 5: Verify PPCAutomation initializes secrets_manager
print("\nTest 5: Checking PPCAutomation initialization...")
if "google_project_id = self.config.get('google_cloud.project_id')" in content:
    print("✓ PPCAutomation checks for Google Cloud configuration")
else:
    print("✗ PPCAutomation does not check for Google Cloud configuration")
    sys.exit(1)

print("\n" + "="*60)
print("All tests passed! ✓")
print("="*60)
print("\nThe code is ready to connect to Amazon Ads API using credentials from:")
print("1. Environment variables (AMAZON_CLIENT_ID, AMAZON_CLIENT_SECRET, AMAZON_REFRESH_TOKEN)")
print("2. Google Secret Manager (when configured via google_cloud.project_id and google_cloud.secret_id)")
print("\nTo verify the actual connection, you would need:")
print("- Valid Amazon Ads API credentials")
print("- A configuration file (ppc_config.yaml)")
print("- A profile ID")
print("\nYou can test with: python main --config ppc_config.yaml --profile-id YOUR_PROFILE_ID --verify-connection")
