"""
LOCAL DISK CACHING MANAGER
==========================
Manages persistent caching of API data to disk for fast retrieval
Cache files expire after 24 hours and auto-refresh
"""

import os
import json
import pickle
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


class CacheManager:
    """Manages local disk caching with automatic expiration"""
    
    def __init__(self, cache_dir='./cache'):
        """Initialize cache manager with cache directory"""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl_hours = 24  # Time to live: 24 hours
    
    def _get_cache_path(self, key):
        """Get the full path for a cache file"""
        return self.cache_dir / f"{key}.cache"
    
    def _is_cache_valid(self, cache_path):
        """Check if cache file exists and is not expired"""
        if not cache_path.exists():
            return False
        
        file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return file_age < timedelta(hours=self.ttl_hours)
    
    def get(self, key):
        """
        Get value from cache if valid.
        Returns None if cache doesn't exist or is expired.
        """
        cache_path = self._get_cache_path(key)
        
        if not self._is_cache_valid(cache_path):
            return None
        
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Cache read error for {key}: {e}")
            return None
    
    def set(self, key, value):
        """Save value to cache"""
        cache_path = self._get_cache_path(key)
        
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(value, f)
            return True
        except Exception as e:
            print(f"Cache write error for {key}: {e}")
            return False
    
    def clear_all(self):
        """Clear all cache files"""
        try:
            for cache_file in self.cache_dir.glob('*.cache'):
                cache_file.unlink()
            print("✅ All cache cleared")
            return True
        except Exception as e:
            print(f"Cache clear error: {e}")
            return False
    
    def get_cache_info(self):
        """Get information about all cached files"""
        info = {}
        for cache_file in self.cache_dir.glob('*.cache'):
            key = cache_file.stem
            age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            size_kb = cache_file.stat().st_size / 1024
            is_valid = age < timedelta(hours=self.ttl_hours)
            
            info[key] = {
                'age_hours': round(age.total_seconds() / 3600, 1),
                'size_kb': round(size_kb, 2),
                'valid': is_valid,
                'expires_in_hours': round((timedelta(hours=self.ttl_hours) - age).total_seconds() / 3600, 1)
            }
        
        return info
    
    def print_cache_status(self):
        """Print cache status for debugging"""
        info = self.get_cache_info()
        if not info:
            print("📦 Cache is empty")
            return
        
        print("\n" + "="*60)
        print("📦 CACHE STATUS")
        print("="*60)
        for key, details in info.items():
            status = "✅ FRESH" if details['valid'] else "⏰ EXPIRED"
            print(f"\n{key}:")
            print(f"  Status: {status}")
            print(f"  Age: {details['age_hours']} hours")
            print(f"  Size: {details['size_kb']} KB")
            if details['valid']:
                print(f"  Expires in: {details['expires_in_hours']} hours")
        print("\n" + "="*60)


# Global cache instance
_cache_manager = CacheManager()


def get_cache_manager():
    """Get the global cache manager instance"""
    return _cache_manager
