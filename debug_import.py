#!/usr/bin/env python3
import traceback
import sys

print("=" * 60)
print("Attempting to import backend.app...")
print("=" * 60)

try:
    from backend.app import application
    print("\n✅ SUCCESS: backend.app imported successfully")
    print(f"Application: {application}")
except Exception as e:
    print("\n❌ ERROR: Failed to import backend.app")
    print(f"\nException: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("If you see this, import was successful.")
print("=" * 60)
