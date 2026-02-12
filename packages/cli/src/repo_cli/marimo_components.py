"""Backward-compatible shim for marimo helper components.

Prefer importing from `experimentation.marimo_components`.
Deprecated on 2026-02-12; planned removal after 2026-04-30.
"""

import sys as _sys
from experimentation import marimo_components as _impl

_sys.modules[__name__] = _impl
