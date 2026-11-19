"""Read-only SQLite database access.

The Hermes state database is opened strictly read-only. Two independent
mechanisms guarantee no write can ever occur:

1. The SQLite URI is opened with ``mode=ro``, so the OS-level file handle is
   read-only and any write attempt raises ``sqlite3.OperationalError``.
2. ``PRAGMA query_only = ON`` is set on the connection, which makes SQLite
   reject every INSERT/UPDATE/DELETE/CREATE/DROP/ALTER statement at runtime.

Only SELECT statements are permitted. This plugin never modifies
``~/.hermes/state.db`` and never locks the running Hermes gateway.
"""

from __future__ import annotations

import os
import sqlite3
from typing import Any


def open_db(db_path: str) -> sqlite3.Connection:
    """Open state.db read-only so the running Hermes gateway is never locked or modified.

    Two safety layers:

    * URI ``mode=ro`` — the file descriptor itself is read-only; SQLite cannot
      write even if it wanted to.
    * ``PRAGMA query_only = ON`` — SQLite rejects any mutating statement at
      runtime (INSERT/UPDATE/DELETE/CREATE/DROP/ALTER).

    Raises:
        sqlite3.OperationalError: if the file is missing or not readable.
        sqlite3.DatabaseError: if any write is attempted on the connection.
    """
    expanded = os.path.expanduser(db_path)
    uri = f"file:{expanded}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row

    # Defense-in-depth: reject any mutating SQL at runtime.
    conn.execute("PRAGMA query_only = ON")

    return conn


def is_read_only(conn: sqlite3.Connection) -> bool:
    """Return True if ``query_only`` is enabled on the connection."""
    row = conn.execute("PRAGMA query_only").fetchone()
    return bool(row[0]) if row else False
