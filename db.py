"""Database access for the token-usage plugin."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def open_db(db_path: str) -> sqlite3.Connection:
    """Open state.db read-only (uri mode=ro) so the running gateway is never locked."""
    expanded = os.path.expanduser(db_path)
    uri = f"file:{expanded}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
