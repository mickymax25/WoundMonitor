"""Rend le paquet `factory` importable quel que soit le rootdir pytest."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
