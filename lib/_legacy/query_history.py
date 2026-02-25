#!/usr/bin/env python3
"""
Query History Management
Stores and retrieves past RAG queries with answers and citations
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


DB_PATH = Path("data/query_history.db")


def init_db():
    """Initialize the query history database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            chunks TEXT NOT NULL,
            filters TEXT,
            is_starred INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


def save_query(
    question: str,
    answer: str,
    chunks: List[Dict],
    filters: Optional[Dict] = None
) -> int:
    """
    Save a query and its results to history.

    Args:
        question: The question asked
        answer: The answer from Claude
        chunks: List of retrieved chunks/sources
        filters: Dictionary of active filters (chemistry, topic, paper_type)

    Returns:
        The ID of the saved query
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = datetime.now().isoformat()
    chunks_json = json.dumps(chunks)
    filters_json = json.dumps(filters) if filters else None

    cursor.execute("""
        INSERT INTO query_history (timestamp, question, answer, chunks, filters)
        VALUES (?, ?, ?, ?, ?)
    """, (timestamp, question, answer, chunks_json, filters_json))

    query_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return query_id


def get_all_queries(limit: Optional[int] = None) -> List[Dict]:
    """
    Get all queries in reverse chronological order.

    Args:
        limit: Maximum number of queries to return (None = all)

    Returns:
        List of query dictionaries
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    query = """
        SELECT id, timestamp, question, answer, chunks, filters, is_starred
        FROM query_history
        ORDER BY created_at DESC
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    queries = []
    for row in rows:
        queries.append({
            'id': row[0],
            'timestamp': row[1],
            'question': row[2],
            'answer': row[3],
            'chunks': json.loads(row[4]),
            'filters': json.loads(row[5]) if row[5] else {},
            'is_starred': bool(row[6])
        })

    return queries


def get_query_by_id(query_id: int) -> Optional[Dict]:
    """Get a specific query by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, timestamp, question, answer, chunks, filters, is_starred
        FROM query_history
        WHERE id = ?
    """, (query_id,))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row[0],
            'timestamp': row[1],
            'question': row[2],
            'answer': row[3],
            'chunks': json.loads(row[4]),
            'filters': json.loads(row[5]) if row[5] else {},
            'is_starred': bool(row[6])
        }
    return None


def delete_query(query_id: int) -> bool:
    """
    Delete a query from history.

    Args:
        query_id: The ID of the query to delete

    Returns:
        True if deleted, False if not found
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM query_history WHERE id = ?", (query_id,))
    deleted = cursor.rowcount > 0

    conn.commit()
    conn.close()

    return deleted


def toggle_star(query_id: int) -> bool:
    """
    Toggle the starred status of a query.

    Args:
        query_id: The ID of the query

    Returns:
        The new starred status (True/False)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get current status
    cursor.execute("SELECT is_starred FROM query_history WHERE id = ?", (query_id,))
    row = cursor.fetchone()

    if row:
        new_status = 0 if row[0] else 1
        cursor.execute(
            "UPDATE query_history SET is_starred = ? WHERE id = ?",
            (new_status, query_id)
        )
        conn.commit()
        conn.close()
        return bool(new_status)

    conn.close()
    return False


def get_starred_queries() -> List[Dict]:
    """Get all starred queries."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, timestamp, question, answer, chunks, filters, is_starred
        FROM query_history
        WHERE is_starred = 1
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    queries = []
    for row in rows:
        queries.append({
            'id': row[0],
            'timestamp': row[1],
            'question': row[2],
            'answer': row[3],
            'chunks': json.loads(row[4]),
            'filters': json.loads(row[5]) if row[5] else {},
            'is_starred': bool(row[6])
        })

    return queries


def clear_all_history() -> int:
    """
    Clear all query history (use with caution).

    Returns:
        Number of queries deleted
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM query_history")
    count = cursor.fetchone()[0]

    cursor.execute("DELETE FROM query_history")
    conn.commit()
    conn.close()

    return count
