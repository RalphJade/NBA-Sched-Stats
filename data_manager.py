"""
DATA MANAGER
============
Fast in-memory CSV-based data access layer.
Replaces API calls with local CSV reads for blazing-fast app performance.

The app calls these functions instead of playerstats.py/schedule.py functions.
Data is pre-fetched daily via data_refresh.py.
"""

import pandas as pd
import json
from datetime import datetime
from pathlib import Path


DATA_DIR = Path('./data')
METADATA_FILE = DATA_DIR / 'refresh_log.json'


def _check_data_available():
    """Verify all required CSV files exist."""
    required_files = ['teams.csv', 'rosters.csv', 'recent_games.csv', 'player_stats.csv']
    missing = [f for f in required_files if not (DATA_DIR / f).exists()]
    
    if missing:
        raise FileNotFoundError(
            f"Missing data files: {', '.join(missing)}\n"
            f"Run: python data_refresh.py"
        )


def get_last_refresh_time():
    """Get timestamp of last data refresh."""
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, 'r') as f:
                metadata = json.load(f)
                if 'last_refresh' in metadata:
                    return datetime.fromisoformat(metadata['last_refresh'])
        except:
            pass
    return None


def is_data_stale(max_age_hours=24):
    """Check if data is older than max_age_hours."""
    last_refresh = get_last_refresh_time()
    if last_refresh is None:
        return True  # No data = stale
    
    age_hours = (datetime.now() - last_refresh).total_seconds() / 3600
    return age_hours >= max_age_hours


def get_refresh_info():
    """Get data age and metadata."""
    _check_data_available()
    
    last_refresh = get_last_refresh_time()
    if last_refresh is None:
        return {'fresh': False, 'age_hours': None, 'last_refresh': 'Never'}
    
    age_hours = (datetime.now() - last_refresh).total_seconds() / 3600
    return {
        'fresh': age_hours < 24,
        'age_hours': age_hours,
        'last_refresh': last_refresh.strftime('%Y-%m-%d %I:%M %p'),
        'needs_refresh': age_hours >= 24
    }


# ============================================================================
# TEAMS
# ============================================================================

def get_all_teams():
    """Get all NBA teams from teams.csv."""
    _check_data_available()
    return pd.read_csv(DATA_DIR / 'teams.csv')


def get_team_id(team_name):
    """Get ESPN team ID for a team name."""
    teams = get_all_teams()
    match = teams[teams['Display Name'].str.contains(team_name, case=False, na=False)]
    if not match.empty:
        return match.iloc[0]['ID']
    return None


# ============================================================================
# ROSTERS
# ============================================================================

def get_all_rosters():
    """Get all players and their teams from rosters.csv."""
    _check_data_available()
    return pd.read_csv(DATA_DIR / 'rosters.csv')


def get_team_roster(team_name):
    """Get roster for specific team."""
    rosters = get_all_rosters()
    team_roster = rosters[rosters['Team'] == team_name].copy()
    return team_roster


def get_player_info(player_name):
    """Get player info from rosters."""
    rosters = get_all_rosters()
    player_info = rosters[rosters['Player Name'].str.contains(player_name, case=False, na=False)]
    if not player_info.empty:
        return player_info.iloc[0].to_dict()
    return None


# ============================================================================
# GAMES
# ============================================================================

def get_recent_games_for_team(team_name):
    """Get recent game IDs for a team."""
    _check_data_available()
    
    teams = get_all_teams()
    team_id = get_team_id(team_name)
    
    if team_id is None:
        return []
    
    games = pd.read_csv(DATA_DIR / 'recent_games.csv')
    team_games = games[games['Team ID'] == str(team_id)]
    return team_games['Game ID'].unique().tolist()


# ============================================================================
# PLAYER STATS
# ============================================================================

def get_player_stats(player_name=None, team_name=None):
    """Get player stats from player_stats.csv.
    
    Args:
        player_name: Filter to specific player (optional)
        team_name: Filter to specific team (optional)
    """
    _check_data_available()
    stats = pd.read_csv(DATA_DIR / 'player_stats.csv')
    
    if player_name:
        stats = stats[stats['Player Name'].str.contains(player_name, case=False, na=False)]
    
    if team_name:
        stats = stats[stats['Team'] == team_name]
    
    return stats


def get_player_recent_stats(player_name, team_name=None):
    """Get recent game stats for a specific player (replacement for fetch_boxscore_stats).
    
    Note: If player_stats.csv is empty (fresh refresh), returns empty DataFrame.
    The app will gracefully handle this with a "No stats found" message.
    
    Returns DataFrame with standardized columns suitable for display.
    """
    try:
        _check_data_available()
        stats = pd.read_csv(DATA_DIR / 'player_stats.csv')
    except:
        return pd.DataFrame()
    
    # If CSV is empty (fresh refresh), return empty
    if stats.empty:
        return pd.DataFrame()
    
    # Filter by player name
    player_stats = stats[stats['Player Name'].str.contains(player_name, case=False, na=False)]
    
    if team_name:
        player_stats = player_stats[player_stats['Team'] == team_name]
    
    if player_stats.empty:
        return pd.DataFrame()
    
    # Sort by date (most recent first) and return last 10 games
    if 'Date' in player_stats.columns:
        player_stats = player_stats.sort_values('Date', ascending=False).head(10)
    else:
        player_stats = player_stats.head(10)
    
    return player_stats


def get_team_player_stats(team_name):
    """Get season stats for all players on a team."""
    stats = get_player_stats(team_name=team_name)
    
    # Aggregate by player (sum stats across games)
    if not stats.empty:
        numeric_cols = stats.select_dtypes(include=['number']).columns
        aggregated = stats.groupby('Player Name')[numeric_cols].sum().reset_index()
        aggregated['Games'] = stats.groupby('Player Name').size().reset_index()[0]
        
        # Calculate per-game averages
        for col in numeric_cols:
            if col not in ['FGM', 'FGA', 'FTM', 'FTA']:  # Skip counting stats
                aggregated[f'{col}_avg'] = aggregated[col] / aggregated['Games']
        
        return aggregated
    
    return pd.DataFrame()


def get_stats_summary():
    """Get summary statistics from player_stats.csv."""
    _check_data_available()
    stats = pd.read_csv(DATA_DIR / 'player_stats.csv')
    
    return {
        'total_records': len(stats),
        'unique_players': stats['Player Name'].nunique(),
        'unique_teams': stats['Team'].nunique(),
        'unique_games': stats.get('Game ID', pd.Series()).nunique() if 'Game ID' in stats else 0,
    }


# ============================================================================
# UTILITY
# ============================================================================

def print_data_status():
    """Print data age and availability status."""
    try:
        _check_data_available()
        info = get_refresh_info()
        
        print("\n📊 DATA STATUS")
        print("="*50)
        print(f"Last Refresh: {info['last_refresh']}")
        print(f"Age: {info['age_hours']:.1f} hours")
        
        if info['fresh']:
            print(f"Status: ✅ FRESH (< 24 hours)")
        else:
            print(f"Status: ⚠️  STALE (> 24 hours)")
            print(f"Action: Run 'python data_refresh.py'")
        
        # Summary stats
        summary = get_stats_summary()
        print(f"\nData Size:")
        print(f"  Players: {summary['unique_players']}")
        print(f"  Teams: {summary['unique_teams']}")
        print(f"  Stats Records: {summary['total_records']}")
        print("="*50 + "\n")
        
    except FileNotFoundError as e:
        print(f"\n❌ DATA NOT AVAILABLE: {e}\n")


if __name__ == '__main__':
    print_data_status()
