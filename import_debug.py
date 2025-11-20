try:
    import backend.app
    print("backend.app imported OK")
except Exception:
    import traceback, sys
    traceback.print_exc()
    sys.exit(1)
