"""Configuration pytest partagée.

Insère la racine du projet dans ``sys.path`` afin que les tests puissent importer
aussi bien ``rag.*`` que ``scripts.*`` (les scripts CLI ne sont pas un paquet installé).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
