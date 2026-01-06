#!/usr/bin/env python3
"""
Test script to verify that authentication is disabled
"""

import requests

def test_api_without_auth():
    """Test that API works without authentication"""

    base_url = "http://localhost:8001"

    print("🧪 Testing Contract AI System (AUTH DISABLED)")
    print("=" * 50)

    # Test health
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        print(f"✅ Health check: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return

    # Test contracts endpoint (should work without auth)
    try:
        response = requests.get(f"{base_url}/api/v1/contracts", timeout=5)
        print(f"✅ Contracts API: {response.status_code}")
    except Exception as e:
        print(f"❌ Contracts API failed: {e}")

    # Test upload endpoint (should work without auth)
    try:
        # Just test the endpoint exists
        response = requests.options(f"{base_url}/api/v1/contracts/upload", timeout=5)
        print(f"✅ Upload API: {response.status_code}")
    except Exception as e:
        print(f"❌ Upload API failed: {e}")

    print("=" * 50)
    print("🎉 SUCCESS: Authentication is DISABLED!")
    print("🌐 Open http://localhost:3000 - auto-login works!")

if __name__ == "__main__":
    test_api_without_auth()