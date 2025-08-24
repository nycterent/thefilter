"""
Readwise API response caching to handle rate limiting.
Caches 'twiar-tagged' documents for 1 hour to avoid repeated API calls.
"""

import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReadwiseCache:
    """Cache for Readwise API responses to handle rate limiting."""
    
    def __init__(self, cache_dir: str = ".cache"):
        """Initialize Readwise cache.
        
        Args:
            cache_dir: Directory to store cache database
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.db_path = self.cache_dir / "readwise_cache.db"
        self._init_database()
    
    def _init_database(self):
        """Initialize cache database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS readwise_documents (
                    cache_key TEXT PRIMARY KEY,
                    documents TEXT NOT NULL,
                    cached_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at ON readwise_documents(expires_at)
            """)
            conn.commit()
    
    def _get_cache_key(self, days: int = 30) -> str:
        """Generate cache key for documents query.
        
        Args:
            days: Number of days back to fetch (affects cache key)
            
        Returns:
            Cache key string
        """
        return f"twiar_documents_{days}d"
    
    def get_cached_documents(self, days: int = 30) -> Optional[List[Dict[str, Any]]]:
        """Get cached Readwise documents if available and not expired.
        
        Args:
            days: Number of days back to fetch
            
        Returns:
            List of cached documents or None if not cached/expired
        """
        cache_key = self._get_cache_key(days)
        current_time = datetime.now()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT documents, cached_at, expires_at FROM readwise_documents WHERE cache_key = ?",
                    (cache_key,)
                )
                row = cursor.fetchone()
                
                if not row:
                    logger.debug(f"No cached documents found for key: {cache_key}")
                    return None
                
                expires_at = datetime.fromisoformat(row['expires_at'])
                if current_time > expires_at:
                    logger.debug(f"Cached documents expired at {expires_at}")
                    # Clean up expired entry
                    conn.execute("DELETE FROM readwise_documents WHERE cache_key = ?", (cache_key,))
                    conn.commit()
                    return None
                
                cached_at = datetime.fromisoformat(row['cached_at'])
                documents = json.loads(row['documents'])
                
                logger.info(f"✅ Using cached Readwise documents from {cached_at} ({len(documents)} documents)")
                return documents
                
        except Exception as e:
            logger.error(f"Error retrieving cached documents: {e}")
            return None
    
    def cache_documents(self, documents: List[Dict[str, Any]], days: int = 30, cache_hours: float = 1.0):
        """Cache Readwise documents for specified duration.
        
        Args:
            documents: List of document dictionaries to cache
            days: Number of days back query (affects cache key)
            cache_hours: Hours to cache documents (default 1 hour)
        """
        cache_key = self._get_cache_key(days)
        current_time = datetime.now()
        expires_at = current_time + timedelta(hours=cache_hours)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Replace existing cache entry
                conn.execute("""
                    INSERT OR REPLACE INTO readwise_documents 
                    (cache_key, documents, cached_at, expires_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    cache_key,
                    json.dumps(documents, ensure_ascii=False),
                    current_time.isoformat(),
                    expires_at.isoformat()
                ))
                conn.commit()
                
                logger.info(f"✅ Cached {len(documents)} Readwise documents until {expires_at}")
                
        except Exception as e:
            logger.error(f"Error caching documents: {e}")
    
    def clear_expired_cache(self):
        """Remove expired cache entries."""
        current_time = datetime.now()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM readwise_documents WHERE expires_at <= ?",
                    (current_time.isoformat(),)
                )
                expired_count = cursor.fetchone()[0]
                
                if expired_count > 0:
                    conn.execute(
                        "DELETE FROM readwise_documents WHERE expires_at <= ?",
                        (current_time.isoformat(),)
                    )
                    conn.commit()
                    logger.info(f"Cleaned up {expired_count} expired cache entries")
                    
        except Exception as e:
            logger.error(f"Error clearing expired cache: {e}")
    
    def get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Count total entries
                cursor = conn.execute("SELECT COUNT(*) as total FROM readwise_documents")
                total = cursor.fetchone()['total']
                
                # Count valid entries
                current_time = datetime.now()
                cursor = conn.execute(
                    "SELECT COUNT(*) as valid FROM readwise_documents WHERE expires_at > ?",
                    (current_time.isoformat(),)
                )
                valid = cursor.fetchone()['valid']
                
                # Get next expiry
                cursor = conn.execute(
                    "SELECT MIN(expires_at) as next_expiry FROM readwise_documents WHERE expires_at > ?",
                    (current_time.isoformat(),)
                )
                row = cursor.fetchone()
                next_expiry = row['next_expiry'] if row['next_expiry'] else None
                
                return {
                    'total_entries': total,
                    'valid_entries': valid,
                    'expired_entries': total - valid,
                    'next_expiry': next_expiry,
                    'cache_file': str(self.db_path)
                }
                
        except Exception as e:
            logger.error(f"Error getting cache status: {e}")
            return {'error': str(e)}


# Global cache instance
_readwise_cache: Optional[ReadwiseCache] = None


def get_readwise_cache(cache_dir: str = ".cache") -> ReadwiseCache:
    """Get global Readwise cache instance.
    
    Args:
        cache_dir: Cache directory path
        
    Returns:
        ReadwiseCache instance
    """
    global _readwise_cache
    if _readwise_cache is None:
        _readwise_cache = ReadwiseCache(cache_dir)
    return _readwise_cache