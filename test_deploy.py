#!/usr/bin/env python3
"""
Quick test script for /git_pull deployment route.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Get deploy key from env
deploy_key = os.environ.get('DEPLOY_KEY', '')

if not deploy_key:
    print("Error: DEPLOY_KEY not set in .env file")
    print("Please add: DEPLOY_KEY=your-key to .env")
    sys.exit(1)

print(f"Testing /git_pull with DEPLOY_KEY from .env")
print(f"Key: {deploy_key[:4]}...{deploy_key[-4:] if len(deploy_key) > 8 else deploy_key}")

# Start Flask app in background
import subprocess
import time

print("\nStarting Flask app...")
flask_process = subprocess.Popen(
    ['python', 'app.py'],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    preexec_fn=os.setsid
)

time.sleep(3)

# Test the deploy route
import requests
try:
    url = 'http://127.0.0.1:5000/git_pull'
    params = {'key': deploy_key}
    response = requests.get(url, params=params, timeout=10)

    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 200 and 'success' in response.json():
        print("✓ Deployment route works correctly!")
    elif response.status_code == 403:
        print("✗ Invalid deploy key")
    elif response.status_code == 500:
        print("✗ Server error - check server logs")

except requests.exceptions.ConnectionError:
    print("✗ Could not connect to Flask app")
    print("Make sure app is running on port 5000")
except Exception as e:
    print(f"✗ Error: {e}")

# Cleanup
flask_process.terminate()
print("\nFlask app stopped")
