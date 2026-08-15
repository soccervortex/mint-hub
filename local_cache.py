"""SQLite local cache for offline browsing and installed-state tracking."""

import json
import sqlite3
import threading
from pathlib import Path

from constants import DB_PATH, CACHE_DIR
from enhancement import Enhancement


class LocalCache:
    def __init__(self, db_path: Path = DB_PATH):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._local = threading.local()
        self._init_schema()

    @property
    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS enhancements (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT DEFAULT '1.0.0',
                author TEXT DEFAULT '',
                category TEXT NOT NULL,
                summary TEXT DEFAULT '',
                description TEXT DEFAULT '',
                thumbnail_url TEXT DEFAULT '',
                thumbnail_local TEXT DEFAULT '',
                download_url TEXT DEFAULT '',
                file_size INTEGER DEFAULT 0,
                install_path TEXT DEFAULT '',
                apply_command TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                screenshots TEXT DEFAULT '[]',
                downloads INTEGER DEFAULT 0,
                avg_rating REAL DEFAULT 0.0,
                num_reviews INTEGER DEFAULT 0,
                score REAL DEFAULT 0.0,
                featured INTEGER DEFAULT 0,
                license TEXT DEFAULT '',
                status TEXT DEFAULT 'published',
                created_at TEXT DEFAULT '',
                updated_at TEXT DEFAULT '',
                installed INTEGER DEFAULT 0,
                installed_version TEXT DEFAULT '',
                source TEXT DEFAULT 'remote',
                writable INTEGER DEFAULT 1
            );
            CREATE INDEX IF NOT EXISTS idx_lc_category ON enhancements(category);
            CREATE INDEX IF NOT EXISTS idx_lc_installed ON enhancements(installed);
            CREATE INDEX IF NOT EXISTS idx_lc_score ON enhancements(score DESC);

            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS enh_fts USING fts5(
                slug, name, summary, tags, content=enhancements, content_rowid=rowid
            );

            CREATE TABLE IF NOT EXISTS favorites (
                slug TEXT PRIMARY KEY,
                added_at TEXT DEFAULT (datetime('now'))
            );
        """)
        self._conn.commit()

    _UPSERT_SQL = """
        INSERT INTO enhancements (slug, name, version, author, category, summary,
            description, thumbnail_url, thumbnail_local, download_url, file_size,
            install_path, apply_command, tags, screenshots, downloads, avg_rating,
            num_reviews, score, featured, license, status, created_at, updated_at,
            installed, installed_version, source, writable)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(slug) DO UPDATE SET
            name=excluded.name, version=excluded.version, author=excluded.author,
            category=excluded.category, summary=excluded.summary,
            description=excluded.description, thumbnail_url=excluded.thumbnail_url,
            downloads=excluded.downloads, avg_rating=excluded.avg_rating,
            num_reviews=excluded.num_reviews, score=excluded.score,
            featured=excluded.featured, status=excluded.status,
            updated_at=excluded.updated_at,
            installed=CASE WHEN excluded.installed THEN 1 ELSE enhancements.installed END,
            installed_version=CASE WHEN excluded.installed THEN excluded.installed_version ELSE enhancements.installed_version END,
            source=CASE WHEN excluded.source='local' THEN 'local' ELSE enhancements.source END
    """

    def _enh_params(self, e: Enhancement):
        return (
            e.slug, e.name, e.version, e.author, e.category, e.summary,
            e.description, e.thumbnail_url, e.thumbnail_local, e.download_url,
            e.file_size, e.install_path, e.apply_command,
            json.dumps(e.tags), json.dumps(e.screenshots),
            e.downloads, e.avg_rating, e.num_reviews, e.score,
            1 if e.featured else 0, e.license, e.status, e.created_at,
            e.updated_at, 1 if e.installed else 0, e.installed_version,
            e.source, 1 if e.writable else 0,
        )

    def upsert(self, e: Enhancement):
        self._conn.execute(self._UPSERT_SQL, self._enh_params(e))
        self._conn.commit()

    def upsert_many(self, enhancements: list):
        conn = self._conn
        conn.execute("BEGIN")
        try:
            for e in enhancements:
                conn.execute(self._UPSERT_SQL, self._enh_params(e))
                conn.execute(
                    "INSERT OR REPLACE INTO enh_fts(rowid, slug, name, summary, tags) "
                    "SELECT rowid, slug, name, summary, tags FROM enhancements WHERE slug=?",
                    (e.slug,)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def mark_installed(self, slug: str, version: str, path: str):
        self._conn.execute(
            "UPDATE enhancements SET installed=1, installed_version=?, install_path=? WHERE slug=?",
            (version, path, slug),
        )
        self._conn.commit()

    def mark_uninstalled(self, slug: str):
        self._conn.execute("UPDATE enhancements SET installed=0, installed_version='' WHERE slug=?", (slug,))
        self._conn.commit()

    def get(self, slug: str) -> Enhancement | None:
        row = self._conn.execute("SELECT * FROM enhancements WHERE slug=?", (slug,)).fetchone()
        return self._row_to_enhancement(row) if row else None

    def get_all(self, category: str = None, installed: bool = None,
                sort: str = "score", limit: int = 200, offset: int = 0) -> list:
        clauses = ["status='published'"]
        params = []
        if category:
            clauses.append("category=?")
            params.append(category)
        if installed is not None:
            clauses.append(f"installed={'1' if installed else '0'}")
        where = " AND ".join(clauses)
        sort_col = {"score": "score DESC", "name": "name ASC", "downloads": "downloads DESC",
                     "rating": "avg_rating DESC", "new": "created_at DESC"}.get(sort, "score DESC")
        rows = self._conn.execute(
            f"SELECT * FROM enhancements WHERE {where} ORDER BY {sort_col} LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [self._row_to_enhancement(r) for r in rows]

    def search(self, query: str, category: str = None, limit: int = 50) -> list:
        try:
            fts_query = " OR ".join(f'"{w}"*' for w in query.split() if w)
            if category:
                rows = self._conn.execute(
                    "SELECT e.* FROM enhancements e "
                    "JOIN enh_fts f ON e.rowid = f.rowid "
                    "WHERE enh_fts MATCH ? AND e.category=? "
                    "ORDER BY e.score DESC LIMIT ?",
                    (fts_query, category, limit),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT e.* FROM enhancements e "
                    "JOIN enh_fts f ON e.rowid = f.rowid "
                    "WHERE enh_fts MATCH ? "
                    "ORDER BY e.score DESC LIMIT ?",
                    (fts_query, limit),
                ).fetchall()
            if rows:
                return [self._row_to_enhancement(r) for r in rows]
        except Exception:
            pass
        q = f"%{query}%"
        clauses = ["(name LIKE ? OR summary LIKE ? OR category LIKE ?)"]
        params = [q, q, q]
        if category:
            clauses.append("category=?")
            params.append(category)
        rows = self._conn.execute(
            f"SELECT * FROM enhancements WHERE {' AND '.join(clauses)} ORDER BY score DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [self._row_to_enhancement(r) for r in rows]

    def get_category_counts(self) -> dict:
        rows = self._conn.execute(
            "SELECT category, COUNT(*) as cnt FROM enhancements WHERE status='published' GROUP BY category"
        ).fetchall()
        return {r["category"]: r["cnt"] for r in rows}

    def get_installed_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM enhancements WHERE installed=1").fetchone()
        return row["cnt"] if row else 0

    def set_state(self, key: str, value: str):
        self._conn.execute("INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)", (key, value))
        self._conn.commit()

    def get_state(self, key: str, default: str = "") -> str:
        row = self._conn.execute("SELECT value FROM app_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def _row_to_enhancement(self, row) -> Enhancement:
        e = Enhancement()
        e.slug = row["slug"]
        e.name = row["name"]
        e.version = row["version"]
        e.author = row["author"]
        e.category = row["category"]
        e.summary = row["summary"]
        e.description = row["description"]
        e.thumbnail_url = row["thumbnail_url"]
        e.thumbnail_local = row["thumbnail_local"]
        e.download_url = row["download_url"]
        e.file_size = row["file_size"]
        e.install_path = row["install_path"]
        e.apply_command = row["apply_command"]
        e.tags = json.loads(row["tags"]) if row["tags"] else []
        e.screenshots = json.loads(row["screenshots"]) if row["screenshots"] else []
        e.downloads = row["downloads"]
        e.avg_rating = row["avg_rating"]
        e.num_reviews = row["num_reviews"]
        e.score = row["score"]
        e.featured = bool(row["featured"])
        e.license = row["license"]
        e.status = row["status"]
        e.created_at = row["created_at"]
        e.updated_at = row["updated_at"]
        e.installed = bool(row["installed"])
        e.installed_version = row["installed_version"]
        e.source = row["source"]
        e.writable = bool(row["writable"])
        return e

    def toggle_favorite(self, slug: str) -> bool:
        existing = self._conn.execute(
            "SELECT slug FROM favorites WHERE slug=?", (slug,)
        ).fetchone()
        if existing:
            self._conn.execute("DELETE FROM favorites WHERE slug=?", (slug,))
            self._conn.commit()
            return False
        else:
            self._conn.execute("INSERT INTO favorites (slug) VALUES (?)", (slug,))
            self._conn.commit()
            return True

    def is_favorite(self, slug: str) -> bool:
        row = self._conn.execute(
            "SELECT slug FROM favorites WHERE slug=?", (slug,)
        ).fetchone()
        return row is not None

    def get_favorites(self, limit: int = 100) -> list:
        rows = self._conn.execute(
            "SELECT e.* FROM enhancements e "
            "JOIN favorites f ON e.slug = f.slug "
            "ORDER BY f.added_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._row_to_enhancement(r) for r in rows]

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn:
            conn.close()
            self._local.conn = None
