"""
Cost Center Cache Manager

Provides caching functionality for team→cost center mappings to improve performance
by avoiding redundant API calls to check existing cost centers.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional


class CostCenterCache:
    """Manages persistent cache of cost center mappings to improve performance."""
    
    def __init__(self, cache_file: str = ".cache/cost_centers.json", cache_ttl_hours: int = 24):
        """
        Initialize the cost center cache.
        
        Args:
            cache_file: Path to the cache file
            cache_ttl_hours: Time-to-live for cache entries in hours
        """
        self.logger = logging.getLogger(__name__)
        self.cache_file = Path(cache_file)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        
        # Ensure cache directory exists
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing cache
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Load cache from file."""
        if not self.cache_file.exists():
            self.logger.debug(f"Cache file {self.cache_file} doesn't exist, starting with empty cache")
            return {"version": "1.0", "last_updated": None, "cost_centers": {}}
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            # Validate cache structure
            if not isinstance(cache_data, dict) or "cost_centers" not in cache_data:
                self.logger.warning(f"Invalid cache format in {self.cache_file}, resetting cache")
                return {"version": "1.0", "last_updated": None, "cost_centers": {}}
                
            self.logger.debug(f"Loaded cache with {len(cache_data.get('cost_centers', {}))} entries")
            return cache_data
            
        except (json.JSONDecodeError, IOError) as e:
            self.logger.warning(f"Failed to load cache from {self.cache_file}: {e}, starting fresh")
            return {"version": "1.0", "last_updated": None, "cost_centers": {}}
    
    def _save_cache(self) -> None:
        """Save cache to file."""
        try:
            # Update timestamp
            self.cache["last_updated"] = datetime.utcnow().isoformat()
            
            # Write to temporary file first, then atomic rename
            temp_file = self.cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, sort_keys=True)
            
            # Atomic rename
            temp_file.replace(self.cache_file)
            
            self.logger.debug(f"Cache saved to {self.cache_file}")
            
        except IOError as e:
            self.logger.error(f"Failed to save cache to {self.cache_file}: {e}")
    
    def get_cost_center_id(self, cost_center_name: str) -> Optional[str]:
        """
        Get cost center ID from cache.
        
        Args:
            cost_center_name: Name of the cost center
            
        Returns:
            Cost center ID if found and not expired, None otherwise
        """
        cost_centers = self.cache.get("cost_centers", {})
        
        if cost_center_name not in cost_centers:
            return None
            
        entry = cost_centers[cost_center_name]
        
        # Check if entry has expired
        if "timestamp" in entry:
            try:
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if datetime.utcnow() - entry_time > self.cache_ttl:
                    self.logger.debug(f"Cache entry for '{cost_center_name}' has expired")
                    return None
            except ValueError:
                self.logger.warning(f"Invalid timestamp in cache entry for '{cost_center_name}'")
                return None
        
        cost_center_id = entry.get("id")
        if cost_center_id:
            self.logger.debug(f"Cache hit: '{cost_center_name}' → {cost_center_id}")
            return cost_center_id
            
        return None
    
    def set_cost_center_id(self, cost_center_name: str, cost_center_id: str) -> None:
        """
        Cache a cost center ID.
        
        Args:
            cost_center_name: Name of the cost center
            cost_center_id: ID of the cost center
        """
        if "cost_centers" not in self.cache:
            self.cache["cost_centers"] = {}
            
        self.cache["cost_centers"][cost_center_name] = {
            "id": cost_center_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.logger.debug(f"Cached: '{cost_center_name}' → {cost_center_id}")
        
        # Save cache after each update to persist changes
        self._save_cache()
    
    def has_cost_center(self, cost_center_name: str) -> bool:
        """Check if cost center exists in cache and is not expired."""
        return self.get_cost_center_id(cost_center_name) is not None
    
    def clear_cache(self) -> None:
        """Clear all cached entries."""
        self.cache = {"version": "1.0", "last_updated": None, "cost_centers": {}}
        self._save_cache()
        self.logger.info("Cache cleared")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        cost_centers = self.cache.get("cost_centers", {})
        
        # Count valid (non-expired) entries
        valid_entries = 0
        expired_entries = 0
        
        for entry in cost_centers.values():
            if "timestamp" in entry:
                try:
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if datetime.utcnow() - entry_time <= self.cache_ttl:
                        valid_entries += 1
                    else:
                        expired_entries += 1
                except ValueError:
                    expired_entries += 1
            else:
                expired_entries += 1
        
        return {
            "total_entries": len(cost_centers),
            "valid_entries": valid_entries,
            "expired_entries": expired_entries,
            "last_updated": self.cache.get("last_updated"),
            "cache_file": str(self.cache_file),
            "ttl_hours": self.cache_ttl.total_seconds() / 3600
        }
    
    def cleanup_expired_entries(self) -> int:
        """Remove expired entries from cache."""
        cost_centers = self.cache.get("cost_centers", {})
        expired_keys = []
        
        for name, entry in cost_centers.items():
            if "timestamp" in entry:
                try:
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    if datetime.utcnow() - entry_time > self.cache_ttl:
                        expired_keys.append(name)
                except ValueError:
                    expired_keys.append(name)
            else:
                expired_keys.append(name)
        
        # Remove expired entries
        for key in expired_keys:
            del cost_centers[key]
        
        if expired_keys:
            self._save_cache()
            self.logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)