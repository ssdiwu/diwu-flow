"""pytest conftest: ensure hooks/scripts/ is on sys.path for imports."""
import os
import sys

_scripts_dir = os.path.join(os.path.dirname(__file__), "hooks", "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
