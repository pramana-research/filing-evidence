# The benchmark is a folder of scripts that import each other by name (checker, ixbrl, paths, ...).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
