from __future__ import annotations

import os

from dataquality import storage

DB_PATH = os.environ.get("DATAQUALITY_DB_PATH", storage.DEFAULT_DB_PATH)


def ensure_db() -> None:
    storage.init_db(DB_PATH)
