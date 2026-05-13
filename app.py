import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from dateutil import tz

st.set_page_config(page_title="NBA Stats & Schedule", page_icon="🏀", layout="wide")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

@st.cache_data(ttl=3600)
def fetch_tomorrow_games_espn():
    """Fetch tomorrow's games and return (date_str, games_df, team_ids_dict)."""
    manila_zone = tz.gettz('Asia/Manila')
    now_manila = datetime.now(manila_zone)
    tomorrow_manila = (now_manila + timedelta(days=1)).date()

    dates_to_query = [
        (now_manila - timedelta(days=1)).strftime('%Y%m%d'),
        now_manila.strftime('%Y%m%d'),
        tomorrow_manila.strftime('%Y%m%d'),
        (now_manila + timedelta(days=2)).strftime('%Y%m%d'),
    ]

    games_list = []
    team_ids = {}  # team_name -> team_id for teams playing tomorrow
    seen_game_ids = set()

    for date_str in dates_to_query:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date_str}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if 'events' not in data:
                continue

            for event in data['events']:
                game_id = event['id']
                if game_id in seen_game_ids:
                    continue
                try:
                    utc_time_str = event['date']
                    try:
                        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=tz.gettz('UTC'))
                    except ValueError:
                        utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%MZ").replace(tzinfo=tz.gettz('UTC'))

                    manila_time = utc_time.astimezone(manila_zone)
                    manila_date = manila_time.date()

                    if manila_date == tomorrow_manila:
                        teams = event['competitions'][0]['competitors']
                        home_team = next((t['team']['displayName'] for t in teams if t['homeAway'] == 'home'), 'Unknown')
                        away_team = next((t['team']['displayName'] for t in teams if t['homeAway'] == 'away'), 'Unknown')
                        home_id = next((t['team']['id'] for t in teams if t['homeAway'] == 'home'), None)
                        away_id = next((t['team']['id'] for t in teams if t['homeAway'] == 'away'), None)
                        status = event['status']['type']['detail']

                        games_list.append({
                            "Game ID": game_id,
                            "Date (Manila)": manila_time.strftime("%Y-%m-%d"),
                            "Time (Manila)": manila_time.strftime("%I:%M %p"),
                            "Home Team": home_team,
                            "Visitor Team": away_team,
                            "Status": status,
                        })
                        if home_id and home_team != 'Unknown':
                            team_ids[home_team] = str(home_id)
                        if away_id and away_team != 'Unknown':
                            team_ids[away_team] = str(away_id)
                        seen_game_ids.add(game_id)
                except (KeyError, StopIteration, ValueError):
                    continue
        except requests.exceptions.RequestException as e:
            st.error(f"Network error fetching schedule: {e}")
            continue

    df = pd.DataFrame(games_list).drop(columns=["Game ID"]) if games_list else pd.DataFrame()
    return tomorrow_manila.strftime("%Y-%m-%d"), df, team_ids


@st.cache_data(ttl=3600)
def fetch_rosters_for_teams(team_ids):
    """Fetch rosters for only the teams playing tomorrow."""
    players_dict = {}
    for team_name, team_id in team_ids.items():
        try:
            roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
            resp = requests.get(roster_url, timeout=10)
            if resp.status_code != 200:
                st.warning(f"Roster API returned {resp.status_code} for {team_name}")
                players_dict[team_name] = {}
                continue
            roster_data = resp.json()
            athletes = roster_data.get('team', {}).get('athletes', []) or roster_data.get('athletes', [])
            players_dict[team_name] = {}
            for athlete in athletes:
                name = athlete.get('displayName') or athlete.get('fullName')
                pid = athlete.get('id')
                if name and pid:
                    players_dict[team_name][name] = str(pid)
        except requests.exceptions.RequestException as e:
            st.warning(f"Network error fetching roster for {team_name}: {e}")
            players_dict[team_name] = {}
        except Exception as e:
            st.warning(f"Error parsing roster for {team_name}: {e}")
            players_dict[team_name] = {}
    return players_dict


@st.cache_data(ttl=3600)
def fetch_recent_games_for_team(team_id, days_back=20):
    """Fetch recent completed game IDs for a team."""
    end_date = datetime.now().strftime('%Y%m%d')
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%d')
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={start_date}-{end_date}&limit=50"
    game_ids = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        for event in data.get('events', []):
            competitors = event.get('competitions', [{}])[0].get('competitors', [])
            for comp in competitors:
                if str(comp.get('team', {}).get('id')) == str(team_id):
                    status = event.get('status', {}).get('type', {}).get('state', '')
                    if status == 'post':
                        game_ids.append(event['id'])
                    break
    except Exception:
        pass
    return game_ids[-10:]


@st.cache_data(ttl=3600)
def fetch_boxscore_stats(game_ids, target_player_ids):
    """Fetch boxscores for recent games and extract stats for target players."""
    player_stats = {pid: [] for pid in target_player_ids}
    target_set = set(target_player_ids)

    for game_id in game_ids:
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()

            header = data.get('header', {})
            competitions = header.get('competitions', [{}])
            competitors = competitions[0].get('competitors', []) if competitions else []
            game_date = competitions[0].get('date', 'N/A')[:10] if competitions else 'N/A'

            team_names = {}
            for comp in competitors:
                team_names[comp.get('team', {}).get('id')] = comp.get('team', {}).get('displayName', 'N/A')

            boxscore = data.get('boxscore', {})
            players_teams = boxscore.get('players', [])  # These are team entries with statistics
            
            for team_entry in players_teams:
                if not isinstance(team_entry, dict):
                    continue
                
                team_info = team_entry.get('team', {})
                team_id = team_info.get('id')
                opponent = next((t for tid, t in team_names.items() if str(tid) != str(team_id)), 'N/A')
                
                statistics = team_entry.get('statistics', [])
                for stat_group in statistics:
                    athletes = stat_group.get('athletes', [])
                    stat_names = stat_group.get('names', [])
                    
                    for athlete in athletes:
                        if not isinstance(athlete, dict):
                            continue
                        
                        # Handle nested athlete structure
                        athlete_data = athlete.get('athlete', athlete)
                        if not isinstance(athlete_data, dict):
                            continue
                        
                        player_id = str(athlete_data.get('id', ''))
                        if not player_id or player_id not in target_set:
                            continue

                        stats = athlete.get('stats', [])
                        if not stats:
                            continue
                        
                        stat_dict = {'Date': game_date, 'Opponent': opponent}
                        for i, name in enumerate(stat_names):
                            if i < len(stats):
                                val = stats[i]
                                if isinstance(val, str):
                                    try:
                                        val = float(val)
                                    except ValueError:
                                        pass
                                stat_dict[name] = val
                        
                        # Only add if we have actual stats beyond Date and Opponent
                        if len(stat_dict) > 2:
                            player_stats[player_id].append(stat_dict)
                    
        except Exception as e:
            continue

    return player_stats


def _standardize_stats(raw_stats_list):
    """Convert raw boxscore stats to standardized column names."""
    if not raw_stats_list:
        return []
    result = []
    for game in raw_stats_list:
        def get_val(names, default='N/A'):
            for name in names:
                if name in game:
                    return game[name]
            return default
        result.append({
            'Date': game.get('Date', 'N/A'),
            'Opponent': game.get('Opponent', 'N/A'),
            'Minutes': get_val(['MIN', 'minutes', 'Minutes', 'MINUTES']),
            'Points': get_val(['PTS', 'points', 'Points', 'POINTS']),
            'Rebounds': get_val(['REB', 'rebounds', 'Rebounds', 'REBOUNDS', 'Total Rebounds']),
            'Assists': get_val(['AST', 'assists', 'Assists', 'ASSISTS']),
            'Steals': get_val(['STL', 'steals', 'Steals', 'STEALS']),
            'Blocks': get_val(['BLK', 'blocks', 'Blocks', 'BLOCKS']),
            'FG%': get_val(['FG%', 'fieldGoalPct', 'FG Pct', 'FG']),
            '3P%': get_val(['3P%', 'threePointPct', '3PT Pct', '3P', '3PT']),
            'FT%': get_val(['FT%', 'freeThrowPct', 'FT Pct', 'FT']),
        })
    return result


# ============================================================================
# DEBUG FUNCTIONS
# ============================================================================

@st.cache_data(ttl=600)
def find_player_id_by_name(game_id, player_name, team_name=None):
    """Try to find player ID in boxscore by matching name."""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        boxscore = data.get('boxscore', {})
        player_name_lower = player_name.lower()
        
        for team_entry in boxscore.get('teams', []):
            team_info = team_entry.get('team', {})
            current_team = team_info.get('displayName', 'Unknown')
            
            # If team_name specified, skip other teams
            if team_name and team_name.lower() not in current_team.lower():
                continue
            
            statistics = team_entry.get('statistics', [])
            for stat_group in statistics:
                athletes = stat_group.get('athletes', [])
                for athlete in athletes:
                    if isinstance(athlete, dict):
                        if 'athlete' in athlete and isinstance(athlete['athlete'], dict):
                            athlete_data = athlete['athlete']
                        else:
                            athlete_data = athlete
                        
                        name = athlete_data.get('displayName', '').lower()
                        pid = str(athlete_data.get('id', ''))
                        
                        # Check for name match (handle partial matches)
                        if player_name_lower in name or name in player_name_lower:
                            return {
                                "player_id": pid,
                                "player_name": athlete_data.get('displayName', ''),
                                "team": current_team,
                                "has_stats": bool(athlete.get('stats'))
                            }
        
        return None
    except Exception as e:
        return None


def find_correct_player_ids_in_boxscores(game_ids, player_name, team_name=None):
    """
    Search for a player by name across multiple recent games and return boxscore IDs.
    Returns a tuple of (matching_player_ids, debug_log).
    """
    found_ids = []
    player_name_lower = player_name.lower()
    debug_log = []
    
    for game_idx, game_id in enumerate(game_ids):
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                debug_log.append(f"❌ Game {game_id[:8]}: Status {resp.status_code}")
                continue
            
            data = resp.json()
            boxscore = data.get('boxscore', {})
            
            if not boxscore:
                debug_log.append(f"⚠️ Game {game_id[:8]}: No boxscore data")
                continue
            
            # The structure is: boxscore.players[] -> each has a statistics[] array -> each has athletes[]
            players_teams = boxscore.get('players', [])  # These are actually team summary entries
            
            if not players_teams:
                debug_log.append(f"⚠️ Game {game_id[:8]}: No team entries in boxscore")
                continue
            
            debug_log.append(f"📋 Game {game_idx} ({game_id[:8]}): {len(players_teams)} team entries")
            
            for team_entry in players_teams:
                if not isinstance(team_entry, dict):
                    continue
                
                team_info = team_entry.get('team', {})
                current_team = team_info.get('displayName', 'Unknown')
                
                if team_name and team_name.lower() not in current_team.lower():
                    continue
                
                statistics = team_entry.get('statistics', [])
                
                if not statistics:
                    debug_log.append(f"  ⚠️ {current_team}: No statistics groups")
                    continue
                
                # Show structure on first game
                if game_idx == 0:
                    first_stat = statistics[0]
                    debug_log.append(f"  First stat group keys: {list(first_stat.keys())[:5] if isinstance(first_stat, dict) else 'N/A'}")
                
                # Each statistics entry has athletes
                total_athletes = 0
                for stat_idx, stat_group in enumerate(statistics):
                    athletes = stat_group.get('athletes', [])
                    total_athletes += len(athletes)
                    
                    if game_idx == 0 and stat_idx == 0:
                        if athletes:
                            sample_names = []
                            for a in athletes[:3]:
                                if isinstance(a, dict):
                                    athlete_data = a.get('athlete', a)
                                    name = athlete_data.get('displayName', '') if isinstance(athlete_data, dict) else ''
                                    if name:
                                        sample_names.append(name)
                            if sample_names:
                                debug_log.append(f"    {current_team} samples: {', '.join(sample_names)}")
                    
                    for athlete in athletes:
                        if not isinstance(athlete, dict):
                            continue
                        
                        # Handle nested athlete structure
                        athlete_data = athlete.get('athlete', athlete)
                        if not isinstance(athlete_data, dict):
                            continue
                        
                        name = athlete_data.get('displayName', '')
                        pid = str(athlete_data.get('id', ''))
                        
                        if not name or not pid:
                            continue
                        
                        name_lower = name.lower()
                        is_match = (player_name_lower == name_lower or 
                                   player_name_lower in name_lower or 
                                   name_lower in player_name_lower)
                        
                        if is_match and pid not in found_ids:
                            found_ids.append(pid)
                            debug_log.append(f"    ✅ MATCH: {name} ({current_team}) - ID: {pid}")
                
                if game_idx == 0:
                    debug_log.append(f"  {current_team}: {total_athletes} total athletes")
                    
        except Exception as e:
            debug_log.append(f"❌ Game {game_id[:8]}: Error - {str(e)}")
            continue
    
    if found_ids:
        debug_log.append(f"\n✅ Found {len(found_ids)} player ID(s): {', '.join(found_ids)}")
    else:
        debug_log.append(f"\n⚠️ Could not find '{player_name}' in any boxscores")
    
    return found_ids, debug_log


@st.cache_data(ttl=600)
def debug_fetch_single_game(game_id, target_player_ids):
    """Debug function to inspect what's in a single game's boxscore."""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return {"error": f"Status code {resp.status_code}"}
        
        data = resp.json()
        debug_info = {
            "game_id": game_id,
            "has_header": "header" in data,
            "has_boxscore": "boxscore" in data,
            "target_player_ids": target_player_ids,
            "teams": []
        }
        
        boxscore = data.get('boxscore', {})
        for team_entry in boxscore.get('teams', []):
            team_info = team_entry.get('team', {})
            team_name = team_info.get('displayName', 'Unknown')
            statistics = team_entry.get('statistics', [])
            
            team_debug = {
                "team": team_name,
                "stat_groups": len(statistics),
                "players_found": [],
                "all_player_ids": []  # NEW: Show ALL player IDs in boxscore
            }
            
            for stat_group in statistics:
                athletes = stat_group.get('athletes', [])
                for athlete in athletes:
                    if isinstance(athlete, dict):
                        # Handle both nested and direct athlete structures
                        if 'athlete' in athlete and isinstance(athlete['athlete'], dict):
                            athlete_data = athlete['athlete']
                        else:
                            athlete_data = athlete
                        
                        player_id = str(athlete_data.get('id', ''))
                        player_name = athlete_data.get('displayName', 'Unknown')
                        
                        # Add to ALL players list (for comparison)
                        if player_id not in team_debug["all_player_ids"]:
                            team_debug["all_player_ids"].append({
                                "name": player_name,
                                "id": player_id,
                                "has_stats": bool(athlete.get('stats'))
                            })
                        
                        # Check if it matches target
                        if player_id in target_player_ids:
                            team_debug["players_found"].append({
                                "name": player_name,
                                "id": player_id,
                                "has_stats": bool(athlete.get('stats'))
                            })
            
            debug_info["teams"].append(team_debug)
        
        return debug_info
    except Exception as e:
        return {"error": str(e)}


# ============================================================================
# MAIN APP
# ============================================================================

st.title("🏀 NBA Stats & Schedule Hub")

tab1, tab2 = st.tabs(["🎮 Games Tomorrow", "📊 Player Stats"])

# ============================================================================
# TAB 1: GAMES TOMORROW
# ============================================================================

with tab1:
    st.header("NBA Games Tomorrow (Manila Time)")
    with st.spinner("Fetching schedule from ESPN..."):
        tomorrow_date, games_df, team_ids = fetch_tomorrow_games_espn()
    st.write(f"**Date (Asia/Manila):** {tomorrow_date}")
    if not games_df.empty:
        st.dataframe(games_df, hide_index=True, width='stretch')
    else:
        st.info("No games scheduled for tomorrow (Asia/Manila time).")

# ============================================================================
# TAB 2: PLAYER STATS
# ============================================================================

with tab2:
    st.header("Player Stats - Last 10 Games")
    st.info("ℹ️ Only showing players from teams playing tomorrow")

    # Step 1: Get tomorrow's games and team IDs
    with st.spinner("Loading tomorrow's matchups..."):
        tomorrow_date, games_df, team_ids = fetch_tomorrow_games_espn()

    if not team_ids:
        st.error("No games scheduled for tomorrow. No player data available.")
        st.stop()

    st.write(f"**Teams playing tomorrow:** {', '.join(sorted(team_ids.keys()))}")

    # Step 2: Fetch rosters for teams playing tomorrow
    with st.spinner("Loading team rosters..."):
        all_players = fetch_rosters_for_teams(team_ids)

    # Debug info
    total_players = sum(len(v) for v in all_players.values())
    st.caption(f"Loaded {total_players} players across {len(all_players)} teams")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Select Team")
        teams_with_players = [t for t in sorted(all_players.keys()) if all_players[t]]
        if not teams_with_players:
            st.error("No players loaded for any team. API may be unavailable.")
            st.stop()
        selected_team = st.selectbox("Choose a team:", teams_with_players, key="team_select")

    with col2:
        st.subheader("Select Player")
        roster = all_players.get(selected_team, {})
        if roster:
            selected_player = st.selectbox(
                "Choose a player:", sorted(roster.keys()), key="player_select"
            )
        else:
            st.warning(f"No players found for {selected_team}.")
            selected_player = None

    if selected_player and roster:
        player_id = roster[selected_player]

        st.subheader(f"{selected_player} - Last 10 Games")
        st.caption(f"Player ID (from Roster API): {player_id}")

        with st.spinner(f"Loading stats for {selected_player}..."):
            team_id = team_ids[selected_team]
            recent_game_ids = fetch_recent_games_for_team(team_id)
            st.caption(f"Found {len(recent_game_ids)} recent completed games")

            if recent_game_ids:
                # Find correct boxscore player IDs by searching for player by name
                with st.spinner(f"Searching for {selected_player} in boxscores..."):
                    boxscore_player_ids, debug_log = find_correct_player_ids_in_boxscores(
                        recent_game_ids,
                        selected_player,
                        selected_team
                    )
                
                # Show debug info immediately
                with st.expander("🔧 Debug Info - Player Search"):
                    st.write("**Search Results:**")
                    if debug_log:
                        for log_entry in debug_log:
                            st.write(f"{log_entry}")
                    else:
                        st.write("No search results recorded")
                
                if not boxscore_player_ids:
                    st.warning(
                        f"Could not find {selected_player} in any recent boxscores. "
                        "They may not have played in the last 10 games or the API data may be incomplete."
                    )
                    stats = []
                else:
                    st.caption(f"Found player in boxscores with ID(s): {', '.join(boxscore_player_ids)}")
                    
                    # Debug: Show ID mapping
                    with st.expander("ℹ️ Player ID Mapping"):
                        st.write(f"**Roster API ID:** `{player_id}`")
                        st.write(f"**Boxscore ID(s):** {', '.join([f'`{bid}`' for bid in boxscore_player_ids])}")
                        if player_id != boxscore_player_ids[0]:
                            st.info("✓ Successfully matched player by name and found correct boxscore ID")
                    
                    raw_stats = fetch_boxscore_stats(recent_game_ids, boxscore_player_ids)
                    # Combine stats from all matched IDs
                    all_stats = []
                    for pid in boxscore_player_ids:
                        all_stats.extend(raw_stats.get(pid, []))
                    stats = _standardize_stats(all_stats)
            else:
                stats = []

        if stats:
            stats_df = pd.DataFrame(stats)
            st.dataframe(stats_df, hide_index=True, width='stretch')

            st.subheader("Summary (Last 10 Games)")
            numeric_df = stats_df.select_dtypes(include=['number'])
            summary_cols = st.columns(5)
            if 'Points' in numeric_df.columns:
                summary_cols[0].metric("Avg Points", f"{numeric_df['Points'].mean():.1f}")
            if 'Rebounds' in numeric_df.columns:
                summary_cols[1].metric("Avg Rebounds", f"{numeric_df['Rebounds'].mean():.1f}")
            if 'Assists' in numeric_df.columns:
                summary_cols[2].metric("Avg Assists", f"{numeric_df['Assists'].mean():.1f}")
            if 'Steals' in numeric_df.columns:
                summary_cols[3].metric("Avg Steals", f"{numeric_df['Steals'].mean():.1f}")
            if 'Blocks' in numeric_df.columns:
                summary_cols[4].metric("Avg Blocks", f"{numeric_df['Blocks'].mean():.1f}")
        else:
            st.warning(
                f"Could not load detailed stats for {selected_player}. "
                "Expand the 'Debug Info - Player ID Matching' section above to diagnose the issue."
            )