"""
Read/Unread Status Tracking Module

Manages read status for papers using SQLite database.
Provides persistent tracking of which papers have been read by the user.
"""

import sqlite3
from pathlib import Path
from typing import Set

DB_PATH = Path(__file__).parent.parent / "data" / "read_status.db"


def init_db():
    """Initialize read status database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS read_status (
            filename TEXT PRIMARY KEY,
            is_read INTEGER DEFAULT 0,
            marked_date TEXT
        )
    ''')
    conn.commit()
    conn.close()


def mark_as_read(filename: str):
    """Mark a paper as read."""
    from datetime import datetime
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO read_status (filename, is_read, marked_date) VALUES (?, 1, ?)",
        (filename, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def mark_as_unread(filename: str):
    """Mark a paper as unread."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO read_status (filename, is_read, marked_date) VALUES (?, 0, NULL)",
        (filename, 0, None)
    )
    conn.commit()
    conn.close()


def get_read_status(filenames: list[str]) -> dict[str, bool]:
    """Get read status for multiple papers."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(filenames))
    cursor.execute(
        f"SELECT filename, is_read FROM read_status WHERE filename IN ({placeholders})",
        filenames
    )
    results = {row[0]: bool(row[1]) for row in cursor.fetchall()}
    conn.close()

    # Default to unread for papers not in database
    return {filename: results.get(filename, False) for filename in filenames}


def toggle_read_status(filename: str) -> bool:
    """Toggle read status and return new state."""
    status = get_read_status([filename])
    is_read = status.get(filename, False)

    if is_read:
        mark_as_unread(filename)
        return False
    else:
        mark_as_read(filename)
        return True
