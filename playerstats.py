import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from dateutil import tz


@st.cache_data(ttl=86400)
def fetch_all_nba_teams():
    """Fetch all 30 NBA teams for the season."""
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams?limit=50"
    fallback = {
        "Atlanta Hawks": "1", "Boston Celtics": "2", "Brooklyn Nets": "17",
        "Charlotte Hornets": "30", "Chicago Bulls": "4", "Cleveland Cavaliers": "5",
        "Dallas Mavericks": "6", "Denver Nuggets": "7", "Detroit Pistons": "8",
        "Golden State Warriors": "9", "Houston Rockets": "10", "Indiana Pacers": "11",
        "LA Clippers": "12", "Los Angeles Lakers": "13", "Memphis Grizzlies": "29",
        "Miami Heat": "14", "Milwaukee Bucks": "15", "Minnesota Timberwolves": "16",
        "New Orleans Pelicans": "3", "New York Knicks": "18", "Oklahoma City Thunder": "25",
        "Orlando Magic": "19", "Philadelphia 76ers": "20", "Phoenix Suns": "21",
        "Portland Trail Blazers": "22", "Sacramento Kings": "23", "San Antonio Spurs": "24",
        "Toronto Raptors": "28", "Utah Jazz": "26", "Washington Wizards": "27"
    }
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        teams = {}
        for entry in data.get('sports', [{}])[0].get('leagues', [{}])[0].get('teams', []):
            team = entry.get('team', {})
            name = team.get('displayName')
            tid = team.get('id')
            if name and tid:
                teams[name] = str(tid)
        return teams if teams else fallback
    except Exception:
        return fallback


@st.cache_data(ttl=3600)
def fetch_rosters_for_teams(team_ids):
    """Fetch rosters for the given teams."""
    players_dict = {}
    failed = []
    for team_name, team_id in team_ids.items():
        try:
            roster_url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"
            resp = requests.get(roster_url, timeout=10)
            if resp.status_code != 200:
                failed.append(team_name)
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
        except Exception:
            failed.append(team_name)
            players_dict[team_name] = {}
    
    if failed:
        st.caption(f"⚠️ Could not load rosters for {len(failed)} team(s).")
    return players_dict


def _is_game_completed(event):
    """
    Check if a game is completed using multiple criteria.
    Handles various ESPN API response formats.
    """
    try:
        # Method 1: Check status type state
        status_obj = event.get('status', {})
        status_type = status_obj.get('type', {})
        status_state = status_type.get('state', '')
        status_detail = status_type.get('detail', '')
        
        if status_state == 'post':
            return True
        
        # Method 2: Check if 'Final' is in the status detail
        if 'Final' in status_detail:
            return True
        
        # Method 3: Check if game has a score (competitions with scores = game completed)
        try:
            competitions = event.get('competitions', [{}])
            if competitions:
                comp = competitions[0]
                # If there are competitors with scores, game is done
                competitors = comp.get('competitors', [])
                for comp_entry in competitors:
                    if 'score' in comp_entry or comp_entry.get('score') is not None:
                        # Game has scores, it's completed
                        return True
        except:
            pass
        
        # Method 4: Check the full status name
        status_name = status_type.get('name', '')
        if 'Final' in status_name or 'Completed' in status_name:
            return True
            
        return False
    except:
        return False


@st.cache_data(ttl=1800)  # Shorter cache for games
def fetch_recent_games_for_team(team_id, max_games=10):
    """
    Fetch the last N completed game IDs for a specific team.
    Uses multiple fallback strategies to find completed games.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
    game_ids = []
    debug_info = []
    
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        events = data.get('events', [])
        debug_info.append(f"Total events in schedule: {len(events)}")
        
        if not events:
            debug_info.append("No events found in schedule")
            return game_ids, debug_info
        
        # Try to find completed games by checking from newest to oldest
        for idx, event in enumerate(reversed(events)):
            if _is_game_completed(event):
                game_ids.append(event['id'])
                try:
                    # Extract game info for debugging
                    comp = event.get('competitions', [{}])[0]
                    game_date = comp.get('date', 'N/A')
                    debug_info.append(f"✓ Completed game {len(game_ids)}: {event['id'][:8]} ({game_date})")
                except:
                    debug_info.append(f"✓ Found completed game: {event['id'][:8]}")
                
                if len(game_ids) >= max_games:
                    break
        
        if not game_ids:
            debug_info.append("No completed games found using standard status checks")
            debug_info.append("Checking first few events for format...")
            
            # Debug: Show what the first few events look like
            for i in range(min(3, len(events))):
                event = events[-(i+1)]  # Reverse
                try:
                    status = event.get('status', {}).get('type', {})
                    debug_info.append(f"Event {i}: state='{status.get('state')}', detail='{status.get('detail')}'")
                except:
                    pass
                    
    except Exception as e:
        debug_info.append(f"Error fetching schedule: {str(e)}")
    
    return game_ids, debug_info


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
            
            # FIX: ESPN uses 'players' array containing team dictionaries in the summary endpoint
            # Fallback to 'teams' if 'players' is empty or not formatted as expected
            players_teams = boxscore.get('players', [])
            if not players_teams:
                players_teams = boxscore.get('teams', [])

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

                        # Some API variants wrap athlete data deeper or flat
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
            'Minutes': get_val(['Minutes', 'MIN']),
            'Points': get_val(['Points', 'PTS']),
            'Rebounds': get_val(['Rebounds', 'REB', 'Total Rebounds']),
            'Assists': get_val(['Assists', 'AST']),
            'Steals': get_val(['Steals', 'STL']),
            'Blocks': get_val(['Blocks', 'BLK']),
            'FG%': get_val(['Field Goal %', 'FG%', 'FG']),
            '3P%': get_val(['3-Point %', '3P%', '3PT']),
            'FT%': get_val(['Free Throw %', 'FT%', 'FT']),
        })
    return result


def find_player_in_single_game(game_id, player_name, team_name=None):
    """Search for a player in a single game's boxscore."""
    try:
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return None

        data = resp.json()
        boxscore = data.get('boxscore', {})

        if not boxscore:
            return None

        players_teams = boxscore.get('players', [])
        if not players_teams:
            players_teams = boxscore.get('teams', [])

        if not players_teams:
            return None

        player_name_lower = player_name.lower()

        for team_entry in players_teams:
            if not isinstance(team_entry, dict):
                continue

            team_info = team_entry.get('team', {})
            current_team = team_info.get('displayName', 'Unknown')

            if team_name and team_name.lower() not in current_team.lower():
                continue

            statistics = team_entry.get('statistics', [])

            for stat_group in statistics:
                athletes = stat_group.get('athletes', [])
                for athlete in athletes:
                    if not isinstance(athlete, dict):
                        continue

                    athlete_data = athlete.get('athlete', athlete)
                    if not isinstance(athlete_data, dict):
                        continue

                    name = athlete_data.get('displayName', '')
                    pid = str(athlete_data.get('id', ''))

                    if not name or not pid:
                        continue

                    name_lower = name.lower()
                    if player_name_lower in name_lower or name_lower in player_name_lower:
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

            # FIX: Ensure this debug search also uses the fallback
            players_teams = boxscore.get('players', [])
            if not players_teams:
                players_teams = boxscore.get('teams', [])

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

                if game_idx == 0:
                    first_stat = statistics[0]
                    debug_log.append(f"  First stat group keys: {list(first_stat.keys())[:5] if isinstance(first_stat, dict) else 'N/A'}")

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
        
        # FIX: Ensure this debug inspection also uses the fallback
        players_teams = boxscore.get('players', [])
        if not players_teams:
            players_teams = boxscore.get('teams', [])
            
        for team_entry in players_teams:
            team_info = team_entry.get('team', {})
            team_name = team_info.get('displayName', 'Unknown')
            statistics = team_entry.get('statistics', [])

            team_debug = {
                "team": team_name,
                "stat_groups": len(statistics),
                "players_found": [],
                "all_player_ids": []
            }

            for stat_group in statistics:
                athletes = stat_group.get('athletes', [])
                for athlete in athletes:
                    if isinstance(athlete, dict):
                        if 'athlete' in athlete and isinstance(athlete['athlete'], dict):
                            athlete_data = athlete['athlete']
                        else:
                            athlete_data = athlete

                        player_id = str(athlete_data.get('id', ''))
                        player_name = athlete_data.get('displayName', 'Unknown')

                        if player_id not in team_debug["all_player_ids"]:
                            team_debug["all_player_ids"].append({
                                "name": player_name,
                                "id": player_id,
                                "has_stats": bool(athlete.get('stats'))
                            })

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