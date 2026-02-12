"""Backward-compatible shim for experimentation workflow helpers.

Prefer importing from `experimentation.unified_experiment`.
"""

import sys as _sys
from experimentation import unified_experiment as _impl

_sys.modules[__name__] = _impl
