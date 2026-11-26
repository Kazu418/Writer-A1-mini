# Historical printer transport: enabled only on the owner machine.
import os as _writer_owner_os
if _writer_owner_os.environ.get("WRITER_A1_MINI_OWNER_CONTROL") != "1":
    raise RuntimeError("Owner-only hardware control. Friends use scripts/prepare_handoff.py; see docs/OWNER_OPERATIONS.md")

"""Run the user-authorized ONE LINE contact test, at most once."""
from send_air_only import main

if __name__ == '__main__':
    raise SystemExit(main(writing=True))
