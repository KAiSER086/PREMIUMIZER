import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import aiosqlite

import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH

    async def init_db(self):
        """Initializes tables and indexes in SQLite database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE,
                    user_id INTEGER NOT NULL,
                    user_name TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    source_url TEXT DEFAULT '',
                    uploader TEXT DEFAULT '',
                    download_url TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    duration_seconds REAL DEFAULT 0.0,
                    error_message TEXT DEFAULT '',
                    timestamp INTEGER NOT NULL
                )
            """)
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON downloads(user_id)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON downloads(timestamp)")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_status ON downloads(status)")
            await db.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def record_download(
        self,
        task_id: str,
        user_id: int,
        user_name: str,
        file_name: str,
        file_size: int,
        source_url: str,
        uploader: str,
        download_url: str,
        status: str,
        duration_seconds: float = 0.0,
        error_message: str = ""
    ):
        """Inserts or updates a download record."""
        now_ts = int(time.time())
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO downloads (
                        task_id, user_id, user_name, file_name, file_size,
                        source_url, uploader, download_url, status,
                        duration_seconds, error_message, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(task_id) DO UPDATE SET
                        file_name=excluded.file_name,
                        file_size=excluded.file_size,
                        uploader=excluded.uploader,
                        download_url=excluded.download_url,
                        status=excluded.status,
                        duration_seconds=excluded.duration_seconds,
                        error_message=excluded.error_message,
                        timestamp=excluded.timestamp
                """, (
                    task_id, user_id, user_name, file_name, file_size,
                    source_url, uploader, download_url, status,
                    duration_seconds, error_message, now_ts
                ))
                await db.commit()
        except Exception as e:
            logger.error(f"Failed to record download in DB: {e}", exc_info=True)

    async def get_user_history(self, user_id: int, limit: int = 8) -> List[Dict[str, Any]]:
        """Fetches the last N downloads for a specific user."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT task_id, user_id, user_name, file_name, file_size, uploader, download_url, status, duration_seconds, timestamp
                    FROM downloads
                    WHERE user_id = ? AND status IN ('COMPLETED', 'UNRESTRICTED')
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (user_id, limit)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch history for user {user_id}: {e}")
            return []

    async def get_all_history(self, limit: int = 8) -> List[Dict[str, Any]]:
        """Fetches the last N downloads across all users (Admin view)."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute("""
                    SELECT task_id, user_id, user_name, file_name, file_size, uploader, download_url, status, duration_seconds, timestamp
                    FROM downloads
                    WHERE status IN ('COMPLETED', 'UNRESTRICTED')
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to fetch global history: {e}")
            return []

    async def get_global_stats(self) -> Dict[str, Any]:
        """Calculates global download numbers, transferred bytes, and active user stats."""
        stats = {
            "total_downloads": 0,
            "total_bytes": 0,
            "unique_users": 0,
            "uploader_counts": {},
            "past_24h_downloads": 0,
            "past_24h_bytes": 0,
            "avg_duration": 0.0
        }
        now_ts = int(time.time())
        day_ago = now_ts - 86400

        try:
            async with aiosqlite.connect(self.db_path) as db:
                # 1. Total completed downloads & bytes & users
                async with db.execute("""
                    SELECT COUNT(*), COALESCE(SUM(file_size), 0), COUNT(DISTINCT user_id), COALESCE(AVG(duration_seconds), 0)
                    FROM downloads
                    WHERE status IN ('COMPLETED', 'UNRESTRICTED')
                """) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        stats["total_downloads"] = row[0]
                        stats["total_bytes"] = row[1]
                        stats["unique_users"] = row[2]
                        stats["avg_duration"] = row[3]

                # 2. Past 24h
                async with db.execute("""
                    SELECT COUNT(*), COALESCE(SUM(file_size), 0)
                    FROM downloads
                    WHERE status IN ('COMPLETED', 'UNRESTRICTED') AND timestamp >= ?
                """, (day_ago,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        stats["past_24h_downloads"] = row[0]
                        stats["past_24h_bytes"] = row[1]

                # 3. Uploader Breakdown
                async with db.execute("""
                    SELECT uploader, COUNT(*)
                    FROM downloads
                    WHERE status IN ('COMPLETED', 'UNRESTRICTED') AND uploader != ''
                    GROUP BY uploader
                    ORDER BY COUNT(*) DESC
                """) as cursor:
                    rows = await cursor.fetchall()
                    for u_name, count in rows:
                        stats["uploader_counts"][u_name] = count

        except Exception as e:
            logger.error(f"Failed to calculate global stats: {e}", exc_info=True)

        return stats

    async def prune_old_records(self, retention_days: int = 90) -> int:
        """Removes historical download records older than retention_days and runs VACUUM."""
        cutoff_ts = int(time.time()) - (retention_days * 86400)
        deleted_count = 0
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("DELETE FROM downloads WHERE timestamp < ?", (cutoff_ts,))
                deleted_count = cursor.rowcount
                await db.commit()
                await db.execute("VACUUM")
                logger.info(f"Database maintenance: Pruned {deleted_count} records older than {retention_days} days.")
        except Exception as e:
            logger.error(f"Failed to prune old database records: {e}")
        return deleted_count
