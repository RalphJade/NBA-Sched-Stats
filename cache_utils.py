"""
CACHE UTILITY SCRIPT
====================
Run this script to inspect and manage the local cache system.
Usage: python cache_utils.py [command]

Commands:
  status     - Show cache status and age of cached files
  clear      - Clear all cache files
  rebuild    - Force refresh all cache (deletes and allows rebuild on next run)
"""

import sys
from cache_manager import get_cache_manager


def main():
    cache = get_cache_manager()
    
    if len(sys.argv) < 2:
        command = 'status'
    else:
        command = sys.argv[1].lower()
    
    if command == 'status':
        print("\n" + "="*70)
        print("📦 CACHE STATUS REPORT")
        print("="*70)
        cache.print_cache_status()
        
    elif command == 'clear':
        print("\nClearing all cache files...")
        cache.clear_all()
        print("✅ Cache cleared successfully!")
        
    elif command == 'rebuild':
        print("\nRebuild mode: Deleting all cache to force refresh on next run...")
        cache.clear_all()
        print("✅ Next app run will fetch fresh data and rebuild cache!")
        
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


if __name__ == '__main__':
    main()
