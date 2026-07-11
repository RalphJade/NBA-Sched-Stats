#!/usr/bin/env python3
"""
QUICK START - CSV-Based Architecture
=====================================
This script will help you set up the new data architecture.
Run this once to create the initial CSV database.
"""

import subprocess
import sys
from pathlib import Path

def main():
    print("\n" + "="*70)
    print("[QUICKSTART] NBA APP - CSV ARCHITECTURE SETUP")
    print("="*70)
    
    # Step 1: Verify Python packages
    print("\n[Step 1] Checking Python packages...")
    required = ['pandas', 'requests', 'streamlit']
    
    for pkg in required:
        try:
            __import__(pkg)
            print(f"  [OK] {pkg}")
        except ImportError:
            print(f"  [FAIL] {pkg} missing! Run: pip install {pkg}")
            return False
    
    # Step 2: Create data directory
    print("\n[Step 2] Setting up data folder...")
    data_dir = Path('./data')
    data_dir.mkdir(exist_ok=True)
    print(f"  [OK] {data_dir} ready")
    
    # Step 3: Run initial refresh
    print("\n[Step 3] Fetching initial data from ESPN...")
    print("  (This may take 2-3 minutes...)")
    
    try:
        result = subprocess.run([sys.executable, 'data_refresh.py'], 
                              capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print("  [OK] Data refresh successful!")
            print("\n" + result.stdout)
        else:
            print(f"  [FAIL] Refresh failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("  [FAIL] Refresh timed out (> 5 minutes)")
        return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False
    
    # Step 4: Check data files
    print("\n[Step 4] Verifying data files...")
    required_files = ['teams.csv', 'rosters.csv', 'recent_games.csv', 'player_stats.csv', 'refresh_log.json']
    
    missing = []
    for fname in required_files:
        fpath = data_dir / fname
        if fpath.exists():
            size_kb = fpath.stat().st_size / 1024
            print(f"  [OK] {fname} ({size_kb:.1f} KB)")
        else:
            missing.append(fname)
            print(f"  [FAIL] {fname}")
    
    if missing:
        print(f"\n  Missing files: {', '.join(missing)}")
        print("  Try running: python data_refresh.py --force")
        return False
    
    # Step 5: Success!
    print("\n" + "="*70)
    print("[SUCCESS] SETUP COMPLETE!")
    print("="*70)
    print("\n[NEXT STEPS]")
    print("  1. Run app: streamlit run app.py")
    print("  2. Check sidebar for data status + refresh button")
    print("  3. All data loads from CSVs (no API delays!)")
    print("\n[DAILY REFRESH]")
    print("  * Manual: python data_refresh.py")
    print("  * Scheduled: See CSV_ARCHITECTURE.md for Task Scheduler setup")
    print("\n[DOCUMENTATION] See CSV_ARCHITECTURE.md for full details")
    print("\n")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
