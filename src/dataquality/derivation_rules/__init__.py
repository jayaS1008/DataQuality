"""Versioned derivation logic for impact analysis.

Each module here exposes `compute(record: ProductRecord) -> Any` for one
attribute-derivation version. A logic change is a new file reviewed like any
other code change - not a string a PM types into a text box - so the impact
subgraph can safely import and run it against the whole catalog.
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Callable

from dataquality.catalog import ProductRecord

ComputeFn = Callable[[ProductRecord], object]


def load_logic(module_name: str) -> ComputeFn:
    module = importlib.import_module(f"dataquality.derivation_rules.{module_name}")
    if not hasattr(module, "compute"):
        raise AttributeError(f"{module_name} does not define compute(record)")
    return module.compute


def list_available() -> list[str]:
    return sorted(
        name
        for _, name, is_pkg in pkgutil.iter_modules(__path__)
        if not is_pkg and name != "__init__"
    )
