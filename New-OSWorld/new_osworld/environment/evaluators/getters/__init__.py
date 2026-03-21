"""Getter functions that extract actual/expected state from the environment.

Each getter is imported as ``get_<type>`` and selected dynamically by the
evaluator config (e.g. ``{"type": "file"}`` -> ``get_file``).
"""

import os
import sys

_OLD_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "OSWorld-SFT"))
if os.path.isdir(_OLD_REPO) and _OLD_REPO not in sys.path:
    sys.path.insert(0, _OLD_REPO)

try:
    from desktop_env.evaluators.getters import *  # noqa: F401,F403
except ImportError:
    pass
