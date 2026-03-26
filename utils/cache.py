"""SQLite-based cache for avoiding duplicate crawling.

Features:
- URL-based caching with content hash
- Configurable TTL (time-to-live)
- Automatic cache cleanup
- Thread-safe operations
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Cache configuration."""
    db_path: str = "mcpsearch_cache.db"
    ttl_seconds: int = 3600  # 1 hour default
    max_entries: int = 10000
    auto_cleanup: bool = True


class CrawlCache:
    """SQLite-based cache for crawled content.

    Usage:
        cache = CrawlCache()
        
        # Check if URL is cached
        if cache.is_cached("https://example.com"):
            content = cache.get("https://example.com")
        
        # Store crawled content
        cache.set("https://example.com", html_content)
        
        # Get cache stats
        stats = cache.get_stats()
    """

    def __init__(self, config: CacheConfig | None = None):
        self.config = config or CacheConfig()
        self._db_path = Path(self.config.db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_cache (
                url TEXT PRIMARY KEY,
                url_hash TEXT NOT NULL,
                content TEXT,
                content_hash TEXT,
                created_at REAL,
                accessed_at REAL,
                access_count INTEGER DEFAULT 0,
                ttl_seconds INTEGER,
                metadata TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url_hash ON crawl_cache(url_hash)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON crawl_cache(created_at)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Cache initialized at {self._db_path}")

    def _hash_url(self, url: str) -> str:
        """Create hash of URL for indexing."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _hash_content(self, content: str) -> str:
        """Create hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()

    def is_cached(self, url: str, check_ttl: bool = True) -> bool:
        """Check if URL is cached and optionally if it's still valid."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        url_hash = self._hash_url(url)
        
        if check_ttl:
            cursor.execute("""
                SELECT created_at, ttl_seconds FROM crawl_cache
                WHERE url_hash = ?
            """, (url_hash,))
        else:
            cursor.execute("""
                SELECT 1 FROM crawl_cache
                WHERE url_hash = ?
            """, (url_hash,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return False
        
        if check_ttl:
            created_at, ttl = row
            if ttl and (time.time() - created_at) > ttl:
                self.delete(url)
                return False
        
        return True

    def get(self, url: str) -> dict[str, Any] | None:
        """Get cached content for URL."""
        if not self.is_cached(url):
            return None
        
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        url_hash = self._hash_url(url)
        cursor.execute("""
            SELECT content, content_hash, metadata, created_at
            FROM crawl_cache
            WHERE url_hash = ?
        """, (url_hash,))
        
        row = cursor.fetchone()
        
        if row is None:
            conn.close()
            return None
        
        content, content_hash, metadata_json, created_at = row
        
        # Update access stats
        cursor.execute("""
            UPDATE crawl_cache
            SET accessed_at = ?, access_count = access_count + 1
            WHERE url_hash = ?
        """, (time.time(), url_hash))
        
        conn.commit()
        conn.close()
        
        metadata = json.loads(metadata_json) if metadata_json else {}
        
        return {
            "url": url,
            "content": content,
            "content_hash": content_hash,
            "metadata": metadata,
            "created_at": created_at,
            "age_seconds": time.time() - created_at,
        }

    def set(
        self,
        url: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store content in cache."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        url_hash = self._hash_url(url)
        content_hash = self._hash_content(content)
        now = time.time()
        ttl = ttl_seconds or self.config.ttl_seconds
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Upsert (insert or update)
        cursor.execute("""
            INSERT INTO crawl_cache 
            (url, url_hash, content, content_hash, created_at, accessed_at, access_count, ttl_seconds, metadata)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                content = excluded.content,
                content_hash = excluded.content_hash,
                created_at = excluded.created_at,
                accessed_at = excluded.accessed_at,
                access_count = crawl_cache.access_count + 1,
                ttl_seconds = excluded.ttl_seconds,
                metadata = excluded.metadata
        """, (url, url_hash, content, content_hash, now, now, ttl, metadata_json))
        
        conn.commit()
        conn.close()
        
        # Auto cleanup if enabled
        if self.config.auto_cleanup:
            self._cleanup_if_needed()

    def delete(self, url: str) -> bool:
        """Delete cached entry for URL."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        url_hash = self._hash_url(url)
        cursor.execute("DELETE FROM crawl_cache WHERE url_hash = ?", (url_hash,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted

    def clear(self) -> int:
        """Clear all cached entries. Returns number of entries deleted."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM crawl_cache")
        count = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM crawl_cache")
        
        conn.commit()
        conn.close()
        
        logger.info(f"Cache cleared: {count} entries removed")
        return count

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        now = time.time()
        cursor.execute("""
            DELETE FROM crawl_cache
            WHERE (created_at + ttl_seconds) < ?
        """, (now,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if deleted > 0:
            logger.info(f"Cache cleanup: removed {deleted} expired entries")
        
        return deleted

    def _cleanup_if_needed(self) -> None:
        """Cleanup if cache exceeds max entries."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM crawl_cache")
        count = cursor.fetchone()[0]
        
        if count > self.config.max_entries:
            # Remove oldest entries
            to_remove = count - self.config.max_entries
            cursor.execute("""
                DELETE FROM crawl_cache
                WHERE url_hash IN (
                    SELECT url_hash FROM crawl_cache
                    ORDER BY accessed_at ASC
                    LIMIT ?
                )
            """, (to_remove,))
            
            conn.commit()
            logger.info(f"Cache cleanup: removed {to_remove} old entries")
        
        conn.close()

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM crawl_cache")
        total = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM crawl_cache
            WHERE (created_at + ttl_seconds) < ?
        """, (time.time(),))
        expired = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT SUM(access_count) FROM crawl_cache
        """)
        total_accesses = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT AVG(access_count) FROM crawl_cache
        """)
        avg_accesses = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_entries": total,
            "expired_entries": expired,
            "valid_entries": total - expired,
            "total_accesses": total_accesses,
            "avg_accesses_per_entry": round(avg_accesses, 2),
            "db_path": str(self._db_path),
            "db_size_mb": round(self._db_path.stat().st_size / (1024 * 1024), 2) if self._db_path.exists() else 0,
        }

    def get_cached_urls(self) -> list[str]:
        """Get list of all cached URLs."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT url FROM crawl_cache ORDER BY accessed_at DESC")
        urls = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return urls


# Global cache instance
crawl_cache = CrawlCache()
