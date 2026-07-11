import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from dateutil import tz
from cache_manager import get_cache_manager

@st.cache_data(ttl=3600)
def fetch_upcoming_games_espn(days_ahead=7):
    """
    Fetch upcoming games for the next N days and return (start_date, end_date, games_df, team_ids_dict).
    Uses local disk caching for improved performance.
    """
    cache = get_cache_manager()
    cache_key = f"upcoming_games_{days_ahead}"
    
    # Try to get from local cache first
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        st.caption(f"📦 Using cached upcoming games (updates daily)")
        return cached_data
    
    manila_zone = tz.gettz('Asia/Manila')
    now_manila = datetime.now(manila_zone)
    start_date_manila = now_manila.date()
    end_date_manila = (now_manila + timedelta(days=days_ahead)).date()

    # Query a range of dates to catch all games
    dates_to_query = []
    current = now_manila - timedelta(days=1)
    end = now_manila + timedelta(days=days_ahead + 1)
    
    while current <= end:
        dates_to_query.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)

    games_list = []
    team_ids = {}  # team_name -> team_id for teams playing in the range
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

                    # Include games from start_date to end_date
                    if start_date_manila <= manila_date <= end_date_manila:
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

    # Sort games by date and time
    if games_list:
        df = pd.DataFrame(games_list)
        df['Date (Manila)'] = pd.to_datetime(df['Date (Manila)'])
        df = df.sort_values('Date (Manila)').drop(columns=["Game ID"])
        df['Date (Manila)'] = df['Date (Manila)'].dt.strftime("%Y-%m-%d")
    else:
        df = pd.DataFrame()

    result = (start_date_manila.strftime("%Y-%m-%d"), end_date_manila.strftime("%Y-%m-%d"), df, team_ids)
    cache.set(cache_key, result)
    st.caption(f"🔄 Fetched fresh upcoming games (cached for 24 hours)")
    return result


@st.cache_data(ttl=3600)
def fetch_tomorrow_games_espn():
    """
    Fetch tomorrow's games and return (date_str, games_df, team_ids_dict).
    For backward compatibility with existing code.
    Uses local disk caching for improved performance.
    """
    cache = get_cache_manager()
    cache_key = "tomorrow_games"
    
    # Try to get from local cache first
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        st.caption("📦 Using cached tomorrow's games (updates daily)")
        return cached_data
    
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
    result = (tomorrow_manila.strftime("%Y-%m-%d"), df, team_ids)
    cache.set(cache_key, result)
    st.caption("🔄 Fetched fresh tomorrow's games (cached for 24 hours)")
    return result


@st.cache_data(ttl=3600)
def get_tomorrow_games_info():
    """Get games for tomorrow and return home/away teams"""
    try:
        manila_zone = tz.gettz('Asia/Manila')
        now_manila = datetime.now(manila_zone)
        tomorrow_manila = (now_manila + timedelta(days=1)).date()
        
        _, games_df, team_ids = fetch_tomorrow_games_espn()
        
        if games_df.empty:
            return None, None, None
        
        # Extract teams playing tomorrow
        teams_playing = set()
        games_info = []
        
        for _, row in games_df.iterrows():
            home_team = row['Home Team']
            away_team = row['Visitor Team']
            teams_playing.add(home_team)
            teams_playing.add(away_team)
            games_info.append({
                'Date': row['Date (Manila)'],
                'Time': row['Time (Manila)'],
                'Home': home_team,
                'Away': away_team
            })
        
        return list(teams_playing), team_ids, games_info    
    except Exception as e:
        return None, None, None
    
def get_tomorrow_opponent(selected_team: str, games_info: list) -> str:
        """Find who the selected team plays tomorrow"""
        for game in games_info:
            if game['Home'] == selected_team:
                return game['Away']
            elif game['Away'] == selected_team:
                return game['Home']
        return None