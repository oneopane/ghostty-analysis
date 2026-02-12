"""Backward-compatible shim for marimo helper components.

Prefer importing from `experimentation.marimo_components`.
"""

import sys as _sys
from experimentation import marimo_components as _impl

_sys.modules[__name__] = _impl
