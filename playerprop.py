import streamlit as st
import pandas as pd
import numpy as np
import schedule as sched
import playerstats as ps
from datetime import datetime, timedelta
from dateutil import tz


# ============================================================================
# HELPER FUNCTIONS FOR PROP RECOMMENDATIONS
# ============================================================================

def calculate_prop_recommendations(game_stats_df, player_name):
    """
    Calculate prop recommendations based on last 10 games stats.
    Returns recommendations with hit rates >= 70%
    """
    if game_stats_df.empty:
        return None
    
    # Map stat column names to readable labels
    stat_mapping = {
        'Points': ('PTS', 'Points'),
        'Rebounds': ('REB', 'Rebounds'),
        'Assists': ('AST', 'Assists'),
        'Steals': ('STL', 'Steals'),
        'Blocks': ('BLK', 'Blocks'),
    }
    
    recommendations = []
    
    for col_name, (stat_label, readable_name) in stat_mapping.items():
        if col_name not in game_stats_df.columns:
            continue
        
        # Get numeric values, filter out 'N/A'
        try:
            stats = pd.to_numeric(game_stats_df[col_name], errors='coerce')
            stats = stats.dropna()
            
            if stats.empty or len(stats) < 3:  # Need at least 3 games
                continue
            
            mean_val = stats.mean()
            std_val = stats.std()
            
            # Generate realistic prop lines around the average
            base_line = round(mean_val * 2) / 2  # Round to nearest 0.5
            lines_to_test = [base_line - 2.5, base_line - 1.5, base_line - 0.5, 
                            base_line, base_line + 0.5, base_line + 1.5, base_line + 2.5]
            
            for line in lines_to_test:
                games_over = (stats > line).sum()
                games_under = (stats < line).sum()
                
                hit_rate_over = (games_over / len(stats)) * 100
                hit_rate_under = (games_under / len(stats)) * 100
                
                # Only recommend high-confidence props (70%+)
                if hit_rate_over >= 70:
                    recommendations.append({
                        "Player": player_name,
                        "Stat": readable_name,
                        "Prop Line": f"OVER {line}",
                        "Hit Rate %": hit_rate_over,
                        "Type": "OVER",
                        "Games Hit": f"{int(games_over)}/10"
                    })
                
                if hit_rate_under >= 70:
                    recommendations.append({
                        "Player": player_name,
                        "Stat": readable_name,
                        "Prop Line": f"UNDER {line}",
                        "Hit Rate %": hit_rate_under,
                        "Type": "UNDER",
                        "Games Hit": f"{int(games_under)}/10"
                    })
        
        except Exception as e:
            continue
    
    if recommendations:
        return pd.DataFrame(recommendations).sort_values('Hit Rate %', ascending=False)
    return None


@st.cache_data(ttl=3600)
def get_tomorrow_games_info():
    """Get games for tomorrow and return home/away teams"""
    try:
        manila_zone = tz.gettz('Asia/Manila')
        now_manila = datetime.now(manila_zone)
        tomorrow_manila = (now_manila + timedelta(days=1)).date()
        
        _, games_df, team_ids = sched.fetch_tomorrow_games_espn()
        
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


# ============================================================================
# MAIN APP
# ============================================================================

st.title("🎯 NBA Player Prop Smart Recommender")
st.subheader("High-Probability Props for Players Playing Tomorrow")
st.write("Based on Last 10 Games Performance Analysis")
st.write("---")

# Fetch tomorrow's games and teams
teams_tomorrow, team_ids, games_info = get_tomorrow_games_info()

if not teams_tomorrow:
    st.warning("⚠️ No games scheduled for tomorrow. Check back later!")
    st.stop()

# Load all rosters
with st.spinner("Loading team rosters..."):
    all_team_ids = ps.fetch_all_nba_teams()
    all_players = ps.fetch_rosters_for_teams(all_team_ids)

# Display tomorrow's games
with st.expander("📅 Tomorrow's Games (Manila Time)", expanded=True):
    for game in games_info:
        st.write(f"**{game['Away']}** @ **{game['Home']}** | {game['Time']} ({game['Date']})")

# Get players from tomorrow's teams
st.write("---")
st.header("🎲 Prop Recommendations for Tomorrow's Matchups")

players_tomorrow = {}
for team in teams_tomorrow:
    if team in all_players:
        players_tomorrow[team] = all_players[team]

if not players_tomorrow:
    st.error("Could not load players for tomorrow's teams.")
    st.stop()

# Player selection with team context
st.subheader("Select Player")
col1, col2 = st.columns(2)

with col1:
    # Select team
    teams_with_players = [t for t in sorted(teams_tomorrow) if t in players_tomorrow and players_tomorrow[t]]
    if not teams_with_players:
        st.error("No players loaded for tomorrow's teams.")
        st.stop()
    
    selected_team = st.selectbox(
        "Team Playing Tomorrow:",
        teams_with_players,
        key="prop_team_select"
    )

with col2:
    # Select player from that team
    roster = players_tomorrow.get(selected_team, {})
    if roster:
        selected_player = st.selectbox(
            "Choose Player:",
            sorted(roster.keys()),
            key="prop_player_select"
        )
    else:
        st.warning(f"No players found for {selected_team}.")
        st.stop()

st.write("---")

# Fetch player's last 10 games
if selected_player and selected_team:
    with st.spinner(f"Fetching {selected_player}'s last 10 games..."):
        # Get team ID
        team_id = all_team_ids[selected_team]
        
        # Get recent games
        recent_game_ids, game_fetch_debug = ps.fetch_recent_games_for_team(team_id)
        
        if not recent_game_ids:
            st.warning(f"No recent completed games found for {selected_team}.")
            st.info("Props can only be generated for players with recent game data.")
            st.stop()
        
        # Find player in boxscores
        boxscore_player_ids, debug_log = ps.find_correct_player_ids_in_boxscores(
            recent_game_ids,
            selected_player,
            selected_team
        )
        
        if not boxscore_player_ids:
            st.warning(f"Could not find {selected_player} in recent boxscores.")
            st.info("The player may not have played recently or the API data is incomplete.")
            st.stop()
        
        # Get stats
        raw_stats = ps.fetch_boxscore_stats(recent_game_ids, boxscore_player_ids)
        all_stats = []
        for pid in boxscore_player_ids:
            all_stats.extend(raw_stats.get(pid, []))
        
        stats = ps._standardize_stats(all_stats)
        
        if not stats:
            st.error("Could not load stats for this player.")
            st.stop()
        
        # Create DataFrame
        stats_df = pd.DataFrame(stats)
        
        # Display last 10 games
        with st.expander("📊 Last 10 Games Form", expanded=False):
            # Select key stats to display
            display_cols = ['Date', 'Opponent', 'Points', 'Rebounds', 'Assists', 'Steals', 'Blocks']
            available_cols = [col for col in display_cols if col in stats_df.columns]
            st.dataframe(stats_df[available_cols], hide_index=True, use_container_width=True)
            
            # Show averages
            st.markdown("#### Last 10 Averages:")
            metric_cols = st.columns(5)
            
            for idx, (col, metric_col) in enumerate([
                ('Points', metric_cols[0]),
                ('Rebounds', metric_cols[1]),
                ('Assists', metric_cols[2]),
                ('Steals', metric_cols[3]),
                ('Blocks', metric_cols[4])
            ]):
                if col in stats_df.columns:
                    numeric_vals = pd.to_numeric(stats_df[col], errors='coerce')
                    avg = numeric_vals.mean()
                    if not np.isnan(avg):
                        metric_col.metric(f"Avg {col}", f"{avg:.1f}")
        
        # Calculate and display recommendations
        st.write("---")
        st.subheader("🔥 High-Probability Props (70%+ Hit Rate)")
        
        recommendations_df = calculate_prop_recommendations(stats_df, selected_player)
        
        if recommendations_df is not None and not recommendations_df.empty:
            st.success(f"✅ Found {len(recommendations_df)} high-confidence prop recommendations!")
            
            # Group recommendations by stat type
            for stat in recommendations_df['Stat'].unique():
                stat_recs = recommendations_df[recommendations_df['Stat'] == stat].sort_values(
                    'Hit Rate %', ascending=False
                )
                
                with st.container(border=True):
                    st.markdown(f"### 📈 {stat}")
                    
                    # Create columns for each recommendation
                    for _, rec in stat_recs.iterrows():
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            # Color code: Green for OVER, Red for UNDER
                            emoji = "🟢" if rec['Type'] == "OVER" else "🔴"
                            st.write(f"{emoji} **{rec['Prop Line']}**")
                            st.write(f"*Hit in {rec['Games Hit']}*")
                        
                        with col2:
                            st.metric("Hit Rate", f"{rec['Hit Rate %']:.0f}%")
                        
                        with col3:
                            # Confidence level
                            confidence = rec['Hit Rate %']
                            if confidence >= 90:
                                st.write("🔥 Very High")
                            elif confidence >= 80:
                                st.write("🌟 High")
                            else:
                                st.write("✓ Good")
        
        else:
            st.info(
                f"ℹ️ No high-probability props found for {selected_player} based on the last 10 games. "
                "This player's recent stats don't show a clear 70%+ trend for any standard betting lines."
            )