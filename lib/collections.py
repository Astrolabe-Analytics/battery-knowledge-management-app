"""
Collections database manager for organizing papers into named groups.
Papers can belong to multiple collections.
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = Path(__file__).parent.parent / "data" / "collections.db"


def _get_connection():
    """Get database connection and create tables if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row

    # Create collections table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            color TEXT,
            description TEXT,
            created_date TEXT NOT NULL,
            modified_date TEXT NOT NULL
        )
    """)

    # Create collection_items table (many-to-many)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS collection_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            added_date TEXT NOT NULL,
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
            UNIQUE(collection_id, filename)
        )
    """)

    # Create indexes for performance
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_collection_items_filename
        ON collection_items(filename)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_collection_items_collection_id
        ON collection_items(collection_id)
    """)

    conn.commit()
    return conn


def create_collection(name: str, color: Optional[str] = None, description: Optional[str] = None) -> Dict:
    """Create a new collection."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            "INSERT INTO collections (name, color, description, created_date, modified_date) VALUES (?, ?, ?, ?, ?)",
            (name, color or "#6c757d", description or "", now, now)
        )
        conn.commit()
        collection_id = cursor.lastrowid
        conn.close()

        return {"success": True, "message": f"Collection '{name}' created successfully", "id": collection_id}
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"Collection '{name}' already exists"}
    except Exception as e:
        return {"success": False, "message": f"Error creating collection: {str(e)}"}


def get_all_collections() -> List[Dict]:
    """Get all collections with paper counts."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                c.id,
                c.name,
                c.color,
                c.description,
                c.created_date,
                c.modified_date,
                COUNT(ci.id) as paper_count
            FROM collections c
            LEFT JOIN collection_items ci ON c.id = ci.collection_id
            GROUP BY c.id
            ORDER BY c.name
        """)

        collections = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return collections
    except Exception as e:
        print(f"Error getting collections: {e}")
        return []


def get_collection_by_id(collection_id: int) -> Optional[Dict]:
    """Get a collection by ID."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM collections WHERE id = ?",
            (collection_id,)
        )

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        print(f"Error getting collection: {e}")
        return None


def add_paper_to_collection(collection_id: int, filename: str) -> Dict:
    """Add a paper to a collection."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            "INSERT INTO collection_items (collection_id, filename, added_date) VALUES (?, ?, ?)",
            (collection_id, filename, now)
        )
        conn.commit()

        # Update collection modified_date
        cursor.execute(
            "UPDATE collections SET modified_date = ? WHERE id = ?",
            (now, collection_id)
        )
        conn.commit()
        conn.close()

        return {"success": True, "message": "Paper added to collection"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": "Paper already in this collection"}
    except Exception as e:
        return {"success": False, "message": f"Error adding paper: {str(e)}"}


def remove_paper_from_collection(collection_id: int, filename: str) -> Dict:
    """Remove a paper from a collection."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "DELETE FROM collection_items WHERE collection_id = ? AND filename = ?",
            (collection_id, filename)
        )
        rows_deleted = cursor.rowcount

        # Update collection modified_date
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE collections SET modified_date = ? WHERE id = ?",
            (now, collection_id)
        )

        conn.commit()
        conn.close()

        if rows_deleted > 0:
            return {"success": True, "message": "Paper removed from collection"}
        else:
            return {"success": False, "message": "Paper not found in collection"}
    except Exception as e:
        return {"success": False, "message": f"Error removing paper: {str(e)}"}


def get_paper_collections(filename: str) -> List[Dict]:
    """Get all collections that contain a specific paper."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT c.*, ci.added_date
            FROM collections c
            JOIN collection_items ci ON c.id = ci.collection_id
            WHERE ci.filename = ?
            ORDER BY c.name
        """, (filename,))

        collections = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return collections
    except Exception as e:
        print(f"Error getting paper collections: {e}")
        return []


def get_collection_papers(collection_id: int) -> List[str]:
    """Get all paper filenames in a collection."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT filename FROM collection_items WHERE collection_id = ? ORDER BY added_date DESC",
            (collection_id,)
        )

        filenames = [row['filename'] for row in cursor.fetchall()]
        conn.close()
        return filenames
    except Exception as e:
        print(f"Error getting collection papers: {e}")
        return []


def delete_collection(collection_id: int) -> Dict:
    """Delete a collection (cascade deletes items)."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()

        # Get collection name for message
        cursor.execute("SELECT name FROM collections WHERE id = ?", (collection_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "message": "Collection not found"}

        collection_name = row['name']

        # Delete collection (cascade deletes items)
        cursor.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        conn.commit()
        conn.close()

        return {"success": True, "message": f"Collection '{collection_name}' deleted"}
    except Exception as e:
        return {"success": False, "message": f"Error deleting collection: {str(e)}"}


def rename_collection(collection_id: int, new_name: str) -> Dict:
    """Rename a collection."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute(
            "UPDATE collections SET name = ?, modified_date = ? WHERE id = ?",
            (new_name, now, collection_id)
        )

        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return {"success": True, "message": f"Collection renamed to '{new_name}'"}
        else:
            conn.close()
            return {"success": False, "message": "Collection not found"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"Collection '{new_name}' already exists"}
    except Exception as e:
        return {"success": False, "message": f"Error renaming collection: {str(e)}"}


def update_collection(collection_id: int, name: Optional[str] = None,
                     color: Optional[str] = None, description: Optional[str] = None) -> Dict:
    """Update collection properties."""
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        updates = []
        params = []

        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if color is not None:
            updates.append("color = ?")
            params.append(color)
        if description is not None:
            updates.append("description = ?")
            params.append(description)

        if not updates:
            return {"success": False, "message": "No updates specified"}

        updates.append("modified_date = ?")
        params.append(now)
        params.append(collection_id)

        query = f"UPDATE collections SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)

        if cursor.rowcount > 0:
            conn.commit()
            conn.close()
            return {"success": True, "message": "Collection updated"}
        else:
            conn.close()
            return {"success": False, "message": "Collection not found"}
    except sqlite3.IntegrityError:
        return {"success": False, "message": f"Collection name already exists"}
    except Exception as e:
        return {"success": False, "message": f"Error updating collection: {str(e)}"}
