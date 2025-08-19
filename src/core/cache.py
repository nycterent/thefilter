"""
Content caching system for newsletter automation.

Implements intelligent caching using content hashes, ETags, and metadata tracking
to avoid regenerating AI summaries for unchanged articles.

Supports both local SQLite storage and Redis for Docker containers.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from pydantic import BaseModel

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from ..models.content import ContentItem

logger = logging.getLogger(__name__)


class CacheEntry(BaseModel):
    """Represents a cached content entry."""
    
    content_hash: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    source_url: str
    cached_summary: str
    cached_commentary: Optional[str] = None
    cached_at: datetime
    readwise_updated_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime


class ContentCache:
    """High-performance content caching system with GitHub Actions compatibility.
    
    Uses file-based storage that can be persisted via GitHub Cache action,
    artifacts, or cloud storage for short-lived containers.
    """
    
    def __init__(self, cache_dir: str = ".cache", max_age_days: int = 30, use_github_cache: bool = None):
        """Initialize the cache system.
        
        Args:
            cache_dir: Directory to store cache files
            max_age_days: Maximum age for cache entries before automatic cleanup  
            use_github_cache: Auto-detect GitHub Actions environment if None
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.db_path = self.cache_dir / "content_cache.db"
        self.export_path = self.cache_dir / "cache_export.json"
        self.max_age_days = max_age_days
        
        # Detect GitHub Actions environment
        self.is_github_actions = use_github_cache if use_github_cache is not None else bool(os.environ.get('GITHUB_ACTIONS'))
        
        self._init_database()
        
        # Try to import cache if we're in GitHub Actions
        if self.is_github_actions:
            self._import_cache_if_exists()
    
    def _init_database(self):
        """Initialize SQLite database for cache metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT UNIQUE NOT NULL,
                    etag TEXT,
                    last_modified TEXT,
                    source_url TEXT NOT NULL,
                    cached_summary TEXT NOT NULL,
                    cached_commentary TEXT,
                    cached_at TIMESTAMP NOT NULL,
                    readwise_updated_at TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP NOT NULL
                )
            """)
            
            # Create indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_content_hash ON cache_entries(content_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_source_url ON cache_entries(source_url)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cached_at ON cache_entries(cached_at)")
            conn.commit()
    
    def _generate_content_hash(self, item: ContentItem) -> str:
        """Generate deterministic hash for content item.
        
        Args:
            item: Content item to hash
            
        Returns:
            SHA256 hash of content, title, and metadata
        """
        # Include key fields that affect summary generation
        hash_data = {
            "title": item.title,
            "content": item.content,
            "author": item.author,
            "url": str(item.url) if item.url else "",
            "source": item.source,
            # Include relevant metadata but not timestamps
            "metadata_keys": sorted(item.metadata.keys()) if item.metadata else []
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(hash_string.encode('utf-8')).hexdigest()
    
    async def get_cached_summary(self, item: ContentItem) -> Optional[Tuple[str, Optional[str]]]:
        """Get cached summary and commentary for content item.
        
        Args:
            item: Content item to check cache for
            
        Returns:
            Tuple of (summary, commentary) if cached, None if not found or expired
        """
        content_hash = self._generate_content_hash(item)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM cache_entries 
                WHERE content_hash = ?
                ORDER BY cached_at DESC
                LIMIT 1
            """, (content_hash,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            # Check if cache entry is too old
            cached_at = datetime.fromisoformat(row['cached_at'])
            if datetime.now(timezone.utc) - cached_at > timedelta(days=self.max_age_days):
                # Clean up expired entry
                conn.execute("DELETE FROM cache_entries WHERE id = ?", (row['id'],))
                conn.commit()
                return None
            
            # Update access statistics
            conn.execute("""
                UPDATE cache_entries 
                SET access_count = access_count + 1, last_accessed = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), row['id']))
            conn.commit()
            
            return (row['cached_summary'], row['cached_commentary'])
    
    async def cache_summary(self, item: ContentItem, summary: str, commentary: Optional[str] = None, etag: Optional[str] = None, last_modified: Optional[str] = None):
        """Cache generated summary and commentary for content item.
        
        Args:
            item: Content item that was processed
            summary: Generated summary to cache
            commentary: Generated commentary to cache (optional)
            etag: ETag from source URL if available
            last_modified: Last-Modified header if available
        """
        content_hash = self._generate_content_hash(item)
        now = datetime.now(timezone.utc)
        
        # Extract Readwise updated timestamp if available
        readwise_updated_at = None
        if item.metadata and item.metadata.get('updated_at'):
            try:
                readwise_updated_at = datetime.fromisoformat(
                    item.metadata['updated_at'].replace('Z', '+00:00')
                )
            except (ValueError, TypeError):
                pass
        
        with sqlite3.connect(self.db_path) as conn:
            # Use INSERT OR REPLACE to handle updates
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries 
                (content_hash, etag, last_modified, source_url, cached_summary, 
                 cached_commentary, cached_at, readwise_updated_at, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                content_hash, etag, last_modified, str(item.url) if item.url else "",
                summary, commentary, now.isoformat(), 
                readwise_updated_at.isoformat() if readwise_updated_at else None,
                now.isoformat()
            ))
            conn.commit()
    
    async def check_url_freshness(self, url: str, cached_etag: Optional[str] = None, cached_last_modified: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """Check if URL content has changed using ETags and Last-Modified headers.
        
        Args:
            url: URL to check
            cached_etag: Previously cached ETag
            cached_last_modified: Previously cached Last-Modified header
            
        Returns:
            Tuple of (has_changed, new_etag, new_last_modified)
        """
        try:
            headers = {}
            if cached_etag:
                headers['If-None-Match'] = cached_etag
            if cached_last_modified:
                headers['If-Modified-Since'] = cached_last_modified
            
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.head(url, headers=headers, allow_redirects=True) as response:
                    new_etag = response.headers.get('ETag')
                    new_last_modified = response.headers.get('Last-Modified')
                    
                    # HTTP 304 means not modified
                    if response.status == 304:
                        return False, cached_etag, cached_last_modified
                    
                    # Check if ETags match
                    if cached_etag and new_etag and cached_etag == new_etag:
                        return False, new_etag, new_last_modified
                    
                    # Content has changed or we couldn't determine
                    return True, new_etag, new_last_modified
                    
        except Exception:
            # On error, assume content might have changed
            return True, None, None
    
    async def should_regenerate_summary(self, item: ContentItem) -> bool:
        """Determine if summary should be regenerated based on cache and freshness checks.
        
        Args:
            item: Content item to check
            
        Returns:
            True if summary should be regenerated, False if cached version is still valid
        """
        content_hash = self._generate_content_hash(item)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT etag, last_modified, source_url, cached_at, readwise_updated_at
                FROM cache_entries 
                WHERE content_hash = ?
                ORDER BY cached_at DESC
                LIMIT 1
            """, (content_hash,))
            
            row = cursor.fetchone()
            if not row:
                return True  # No cache entry, need to generate
            
            # Check age-based expiration
            cached_at = datetime.fromisoformat(row['cached_at'])
            if datetime.now(timezone.utc) - cached_at > timedelta(days=self.max_age_days):
                return True
            
            # Check if source URL has changed
            if item.url and row['source_url']:
                has_changed, _, _ = await self.check_url_freshness(
                    str(item.url), row['etag'], row['last_modified']
                )
                if has_changed:
                    return True
            
            # Check Readwise update timestamp
            if item.metadata and item.metadata.get('updated_at') and row['readwise_updated_at']:
                try:
                    current_updated = datetime.fromisoformat(
                        item.metadata['updated_at'].replace('Z', '+00:00')
                    )
                    cached_updated = datetime.fromisoformat(row['readwise_updated_at'])
                    if current_updated > cached_updated:
                        return True
                except (ValueError, TypeError):
                    pass
            
            return False  # Cache is still valid
    
    def cleanup_expired_entries(self):
        """Remove expired cache entries."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache_entries WHERE cached_at < ?", (cutoff_date.isoformat(),))
            deleted_count = cursor.rowcount
            conn.commit()
            
        return deleted_count
    
    def _import_cache_if_exists(self):
        """Import cache from export file if it exists (for GitHub Actions)."""
        if not self.export_path.exists():
            return
        
        try:
            with open(self.export_path, 'r') as f:
                cache_data = json.load(f)
            
            with sqlite3.connect(self.db_path) as conn:
                for entry in cache_data.get('entries', []):
                    conn.execute("""
                        INSERT OR REPLACE INTO cache_entries 
                        (content_hash, etag, last_modified, source_url, cached_summary, 
                         cached_commentary, cached_at, readwise_updated_at, access_count, last_accessed)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry['content_hash'], entry['etag'], entry['last_modified'],
                        entry['source_url'], entry['cached_summary'], entry['cached_commentary'],
                        entry['cached_at'], entry['readwise_updated_at'], 
                        entry['access_count'], entry['last_accessed']
                    ))
                conn.commit()
            
            logger.info(f"Imported {len(cache_data.get('entries', []))} cache entries from export")
            
        except Exception as e:
            logger.warning(f"Failed to import cache: {e}")
    
    def export_cache_for_github_actions(self):
        """Export cache to JSON file for GitHub Actions persistence."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM cache_entries")
                entries = [dict(row) for row in cursor.fetchall()]
            
            cache_data = {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_entries": len(entries),
                "entries": entries
            }
            
            with open(self.export_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            logger.info(f"Exported {len(entries)} cache entries for GitHub Actions")
            return self.export_path
            
        except Exception as e:
            logger.error(f"Failed to export cache: {e}")
            return None
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total_entries,
                    SUM(access_count) as total_accesses,
                    AVG(access_count) as avg_accesses,
                    MIN(cached_at) as oldest_entry,
                    MAX(cached_at) as newest_entry
                FROM cache_entries
            """)
            row = cursor.fetchone()
            
            # Calculate cache size
            cache_size = sum(f.stat().st_size for f in self.cache_dir.glob("*") if f.is_file())
            
            return {
                "total_entries": row[0] or 0,
                "total_accesses": row[1] or 0,
                "average_accesses": round(row[2] or 0, 2),
                "oldest_entry": row[3],
                "newest_entry": row[4],
                "cache_size_bytes": cache_size,
                "cache_dir": str(self.cache_dir),
                "github_actions": self.is_github_actions,
                "export_file": str(self.export_path) if self.export_path.exists() else None
            }