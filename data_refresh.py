"""
DATA REFRESH SCRIPT
===================
Pre-fetches all NBA data into CSVs once per day.
Run manually or schedule with Windows Task Scheduler for 6 AM daily refresh.

Usage:
  python data_refresh.py              # Run full refresh
  python data_refresh.py --teams-only # Refresh only teams.csv
  python data_refresh.py --force      # Force refresh (skip staleness check)
"""

import sys
import json
import pandas as pd
from datetime import datetime
from pathlib import Path
import warnings

# Suppress Streamlit warnings when running in bare mode
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='.*No runtime found.*')
warnings.filterwarnings('ignore', message='.*missing ScriptRunContext.*')

# Suppress logging output
import logging
logging.getLogger('streamlit').setLevel(logging.ERROR)

import playerstats as ps
import schedule as sch

# Create data directory if it doesn't exist
DATA_DIR = Path('./data')
DATA_DIR.mkdir(exist_ok=True)

# Metadata file to track last refresh
METADATA_FILE = DATA_DIR / 'refresh_log.json'


def load_metadata():
    """Load last refresh timestamp."""
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_metadata(metadata):
    """Save refresh metadata."""
    with open(METADATA_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)


def is_data_fresh(max_age_hours=24):
    """Check if all data files are fresh (younger than max_age_hours)."""
    metadata = load_metadata()
    if not metadata.get('last_refresh'):
        return False
    
    last_refresh = datetime.fromisoformat(metadata['last_refresh'])
    age_hours = (datetime.now() - last_refresh).total_seconds() / 3600
    return age_hours < max_age_hours


def refresh_rosters(teams_dict=None):
    """Fetch and save rosters for all teams."""
    if teams_dict is None:
        print("\n[*] Fetching NBA teams (required for rosters)...")
        teams_dict = ps.fetch_all_nba_teams()
    
    print("\n[*] Fetching rosters for all teams...")
    all_rosters = ps.fetch_rosters_for_teams(teams_dict)
    
    # Flatten rosters dict into DataFrame
    roster_records = []
    for team_name, players_dict in all_rosters.items():
        for player_name, player_info in players_dict.items():
            record = {
                'Team': team_name,
                'Player Name': player_name,
                'Player ID': player_info.get('id', ''),
                'Image': player_info.get('image', ''),
                'Position': player_info.get('position', 'N/A'),
                'Jersey': player_info.get('jersey', 'N/A'),
                'Age': player_info.get('age', 'N/A'),
                'Height': player_info.get('height', 'N/A'),
                'Weight': player_info.get('weight', 'N/A'),
                'Experience': player_info.get('experience', 'N/A')
            }
            roster_records.append(record)
    
    rosters_df = pd.DataFrame(roster_records)
    rosters_df.to_csv(DATA_DIR / 'rosters.csv', index=False)
    print(f"[OK] Saved {len(rosters_df)} roster entries to rosters.csv")
    return rosters_df


def refresh_recent_games(teams_dict=None):
    """Fetch and save recent games for all teams."""
    if teams_dict is None:
        print("\n[*] Fetching NBA teams (required for games)...")
        teams_dict = ps.fetch_all_nba_teams()
    
    print("\n[*] Fetching recent games for all teams...")
    
    all_games = []
    for team_name, team_data in teams_dict.items():
        team_id = team_data.get('id', '')
        try:
            game_ids, debug_info = ps.fetch_recent_games_for_team(team_id)
            for game_id in game_ids:
                all_games.append({'Team ID': team_id, 'Game ID': game_id})
        except Exception as e:
            print(f"  [!] Error fetching games for team {team_name}: {e}")
            continue
    
    games_df = pd.DataFrame(all_games)
    games_df.to_csv(DATA_DIR / 'recent_games.csv', index=False)
    print(f"[OK] Saved {len(games_df)} game records to recent_games.csv")
    return games_df


def refresh_player_stats(rosters_df=None, games_df=None):
    """Create empty player stats CSV (app fetches live stats as needed).
    
    Full boxscore fetching is complex due to API rate limits.
    For now, we store empty structure and app can fetch live when needed.
    """
    print("\n[*] Preparing player stats structure...")
    
    # Create empty stats structure with correct columns
    # This allows app to fetch live stats on demand if needed
    empty_stats = pd.DataFrame(columns=[
        'Player Name', 'Player ID', 'Team', 'Date', 'Points', 'Rebounds', 
        'Assists', '3PM', 'FGM', 'FGA', 'FTM', 'FTA', 'Minutes', 'Opponent'
    ])
    
    empty_stats.to_csv(DATA_DIR / 'player_stats.csv', index=False)
    print(f"[OK] Created player stats template (0 records - will fetch live as needed)")
    return empty_stats


def main():
    """Run full data refresh pipeline."""
    force_refresh = '--force' in sys.argv
    teams_only = '--teams-only' in sys.argv
    
    # Check if refresh is needed (unless forced)
    if not force_refresh and not teams_only and is_data_fresh():
        print("\n[OK] Data is fresh (last refreshed within 24 hours)")
        print("     Use --force flag to refresh anyway")
        return
    
    print("\n" + "="*70)
    print("[REFRESH] NBA DATA REFRESH")
    print("="*70)
    
    try:
        # Step 0: Fetch teams dict
        print("\n[*] Fetching NBA teams...")
        teams_dict = ps.fetch_all_nba_teams()
        
        # Step 1: Save teams to CSV
        teams_list = []
        for team_name, team_data in teams_dict.items():
            teams_list.append({
                'Display Name': team_name,
                'ID': team_data.get('id', ''),
                'Logo': team_data.get('logo', '')
            })
        teams_df = pd.DataFrame(teams_list)
        teams_df.to_csv(DATA_DIR / 'teams.csv', index=False)
        print(f"[OK] Saved {len(teams_df)} teams to teams.csv")
        
        if teams_only:
            print("\n[OK] Teams-only refresh complete!")
            metadata = load_metadata()
            metadata['last_refresh'] = datetime.now().isoformat()
            metadata['teams'] = len(teams_df)
            save_metadata(metadata)
            return
        
        # Step 2: Rosters
        rosters_df = refresh_rosters(teams_dict)
        
        # Step 3: Recent Games
        games_df = refresh_recent_games(teams_dict)
        
        # Step 4: Player Stats
        stats_df = refresh_player_stats(rosters_df, games_df)
        
        # Save metadata
        metadata = load_metadata()
        metadata['last_refresh'] = datetime.now().isoformat()
        metadata['teams'] = len(teams_df)
        metadata['rosters'] = len(rosters_df)
        metadata['games'] = len(games_df)
        metadata['player_stats'] = len(stats_df)
        save_metadata(metadata)
        
        print("\n" + "="*70)
        print("[SUCCESS] DATA REFRESH COMPLETE!")
        print("="*70)
        print(f"[SUMMARY]")
        print(f"  Teams: {len(teams_df)}")
        print(f"  Roster entries: {len(rosters_df)}")
        print(f"  Game records: {len(games_df)}")
        print(f"  Player stats: {len(stats_df)}")
        print(f"  [TIMESTAMP] Last refresh: {metadata['last_refresh']}")
        print("\n[INFO] App will now run purely from CSV data until next refresh!\n")
        
    except Exception as e:
        print(f"\n[ERROR] REFRESH FAILED: {e}")
        print("        Please check your internet connection and API access")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
