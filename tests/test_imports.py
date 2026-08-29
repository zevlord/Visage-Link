"""Test script to check if the server module imports correctly."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from server.server import app
    print("Import OK - server module loads correctly")
except Exception as e:
    print(f"Import ERROR: {e}")
    import traceback
    traceback.print_exc()
