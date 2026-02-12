"""Backward-compatible shim for experimentation workflow helpers.

Prefer importing from `experimentation.unified_experiment`.
Deprecated on 2026-02-12; planned removal after 2026-04-30.
"""

import sys as _sys
from experimentation import unified_experiment as _impl

_sys.modules[__name__] = _impl
