"""Expose the digit-prefixed skill package under an importable alias.

Python disallows ``from SKILLS.24_trend_analyzer.foo import bar`` because
``24_trend_analyzer`` isn't a valid identifier. We use :mod:`importlib`
to load the package dynamically and register it in :data:`sys.modules`
as ``trend_analyzer`` so test files can use normal ``from`` syntax.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_PKG = importlib.import_module("SKILLS.24_trend_analyzer")
sys.modules.setdefault("trend_analyzer", _PKG)

for _sub in (
    "schemas",
    "cost_tracker",
    "cache",
    "service",
    "llm",
    "normalize",
    "normalize.text",
    "normalize.url",
    "normalize.image",
    "providers",
    "providers.google_trends",
):
    _mod = importlib.import_module(f"SKILLS.24_trend_analyzer.{_sub}")
    sys.modules.setdefault(f"trend_analyzer.{_sub}", _mod)
