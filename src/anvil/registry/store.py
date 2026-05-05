"""
SQLite-backed storage for RSQs (Relations, Systems, Quantities).

Each RSQ is a row with:
    name, type (R/S/Q), domain, version, description, author,
    source (Python code), metadata (JSON), tests (JSON),
    hash (SHA256), origin (local/public/url), timestamps.
"""

import sqlite3
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path.home() / ".anvil" / "registry.db"


class Store:
    """SQLite store for RSQs."""

    def __init__(self, db_path=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = None
        self._ensure_schema()

    def _get_conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS rsq (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL,
                type        TEXT NOT NULL CHECK(type IN ('R', 'S', 'Q')),
                domain      TEXT DEFAULT '',
                version     TEXT DEFAULT '0.0.1',
                description TEXT DEFAULT '',
                author      TEXT DEFAULT '',
                source      TEXT NOT NULL,
                metadata    TEXT DEFAULT '{}',
                tests       TEXT DEFAULT '{}',
                hash        TEXT NOT NULL,
                origin      TEXT DEFAULT 'local',
                created_at  TEXT DEFAULT (datetime('now')),
                updated_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(name, origin)
            );

            CREATE TABLE IF NOT EXISTS tags (
                rsq_id  INTEGER NOT NULL REFERENCES rsq(id) ON DELETE CASCADE,
                tag     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dependencies (
                rsq_id      INTEGER NOT NULL REFERENCES rsq(id) ON DELETE CASCADE,
                depends_on  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_rsq_name ON rsq(name);
            CREATE INDEX IF NOT EXISTS idx_rsq_type ON rsq(type);
            CREATE INDEX IF NOT EXISTS idx_rsq_domain ON rsq(domain);
            CREATE INDEX IF NOT EXISTS idx_rsq_origin ON rsq(origin);
            CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
        """)
        conn.commit()

    # === CRUD ===

    def put(self, name, rsq_type, source, domain="", version="0.0.1",
            description="", author="", metadata=None, tests=None,
            tags=None, depends=None, origin="local"):
        """Insert or update an RSQ."""
        conn = self._get_conn()
        h = hashlib.sha256(source.encode()).hexdigest()
        meta_json = json.dumps(metadata or {})
        tests_json = json.dumps(tests or {})

        # Check if exists
        existing = conn.execute(
            "SELECT id FROM rsq WHERE name=? AND origin=?", (name, origin)
        ).fetchone()

        if existing:
            rsq_id = existing["id"]
            conn.execute("""
                UPDATE rsq SET type=?, domain=?, version=?, description=?,
                    author=?, source=?, metadata=?, tests=?, hash=?,
                    updated_at=datetime('now')
                WHERE id=?
            """, (rsq_type, domain, version, description, author,
                  source, meta_json, tests_json, h, rsq_id))
        else:
            cur = conn.execute("""
                INSERT INTO rsq (name, type, domain, version, description,
                    author, source, metadata, tests, hash, origin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, rsq_type, domain, version, description, author,
                  source, meta_json, tests_json, h, origin))
            rsq_id = cur.lastrowid

        # Update tags
        conn.execute("DELETE FROM tags WHERE rsq_id=?", (rsq_id,))
        if tags:
            conn.executemany(
                "INSERT INTO tags (rsq_id, tag) VALUES (?, ?)",
                [(rsq_id, t) for t in tags]
            )

        # Update dependencies
        conn.execute("DELETE FROM dependencies WHERE rsq_id=?", (rsq_id,))
        if depends:
            conn.executemany(
                "INSERT INTO dependencies (rsq_id, depends_on) VALUES (?, ?)",
                [(rsq_id, d) for d in depends]
            )

        conn.commit()
        return rsq_id

    def get(self, name):
        """
        Get an RSQ by name. Local origin takes priority over public.
        Returns dict or None.
        """
        conn = self._get_conn()
        # Local first
        row = conn.execute(
            "SELECT * FROM rsq WHERE name=? ORDER BY "
            "CASE origin WHEN 'local' THEN 0 ELSE 1 END LIMIT 1",
            (name,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    def get_all(self, rsq_type=None, domain=None, origin=None, tag=None):
        """List RSQs with optional filters."""
        conn = self._get_conn()
        query = "SELECT DISTINCT rsq.* FROM rsq"
        conditions = []
        params = []

        if tag:
            query += " JOIN tags ON tags.rsq_id = rsq.id"
            conditions.append("tags.tag = ?")
            params.append(tag)

        if rsq_type:
            conditions.append("rsq.type = ?")
            params.append(rsq_type)
        if domain:
            conditions.append("(rsq.domain = ? OR rsq.domain LIKE ?)")
            params.extend([domain, f"{domain}.%"])
        if origin:
            conditions.append("rsq.origin = ?")
            params.append(origin)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY rsq.domain, rsq.name"
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def search(self, keyword):
        """Fuzzy search across name, description, domain, and tags."""
        conn = self._get_conn()
        kw = f"%{keyword}%"
        rows = conn.execute("""
            SELECT DISTINCT rsq.* FROM rsq
            LEFT JOIN tags ON tags.rsq_id = rsq.id
            WHERE rsq.name LIKE ? OR rsq.description LIKE ?
                OR rsq.domain LIKE ? OR tags.tag LIKE ?
            ORDER BY rsq.type, rsq.domain, rsq.name
        """, (kw, kw, kw, kw)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def remove(self, name, origin=None):
        """Remove an RSQ."""
        conn = self._get_conn()
        if origin:
            conn.execute("DELETE FROM rsq WHERE name=? AND origin=?", (name, origin))
        else:
            conn.execute("DELETE FROM rsq WHERE name=?", (name,))
        conn.commit()

    def get_hash(self, name, origin="public"):
        """Get the hash of an RSQ (for version checking during fetch)."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT hash FROM rsq WHERE name=? AND origin=?", (name, origin)
        ).fetchone()
        return row["hash"] if row else None

    def get_tags(self, rsq_id):
        """Get tags for an RSQ."""
        conn = self._get_conn()
        rows = conn.execute("SELECT tag FROM tags WHERE rsq_id=?", (rsq_id,)).fetchall()
        return [r["tag"] for r in rows]

    def get_dependencies(self, rsq_id):
        """Get dependencies for an RSQ."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT depends_on FROM dependencies WHERE rsq_id=?", (rsq_id,)
        ).fetchall()
        return [r["depends_on"] for r in rows]

    def _row_to_dict(self, row):
        d = dict(row)
        d["metadata"] = json.loads(d["metadata"])
        d["tests"] = json.loads(d["tests"])
        d["tags"] = self.get_tags(d["id"])
        d["depends"] = self.get_dependencies(d["id"])
        return d

    def count(self, rsq_type=None):
        conn = self._get_conn()
        if rsq_type:
            row = conn.execute("SELECT COUNT(*) as n FROM rsq WHERE type=?", (rsq_type,)).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) as n FROM rsq").fetchone()
        return row["n"]

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
