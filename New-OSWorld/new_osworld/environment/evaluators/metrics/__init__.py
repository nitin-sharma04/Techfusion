"""Metric functions that compare actual vs. expected state and return a score.

Each metric is a callable ``(result, expected=None, **options) -> float``
returning a value in ``[0, 1]``.

Imports all metric functions from submodules so they can be resolved by name
via ``getattr(metrics, func_name)``.
"""

import importlib
import os
import sys

# Try to import metrics from the original OSWorld-SFT repo if available,
# falling back gracefully if not installed.
_OLD_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", "OSWorld-SFT"))
if os.path.isdir(_OLD_REPO) and _OLD_REPO not in sys.path:
    sys.path.insert(0, _OLD_REPO)

try:
    from desktop_env.evaluators.metrics import *  # noqa: F401,F403
except ImportError:
    pass
