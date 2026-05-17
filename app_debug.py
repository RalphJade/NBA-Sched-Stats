import streamlit as st
import pandas as pd
import requests
import schedule as sched
import playerstats as ps
import playerprop as pp
from datetime import datetime, timedelta
from dateutil import tz


st.set_page_config(page_title="NBA Stats & Schedule", page_icon="🏀", layout="wide")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


# ============================================================================
# MAIN APP
# ============================================================================

st.title("🏀 NBA Stats & Schedule Hub")

tab1, tab2, tab3 = st.tabs(["📅 Upcoming Games", "📊 Player Stats", "🎯 Player Props"])

# ============================================================================
# TAB 1: UPCOMING GAMES (NEXT 7 DAYS)
# ============================================================================

with tab1:
    st.header("NBA Upcoming Games (Manila Time)")
    
    # Radio button to select number of days
    days_range = st.radio(
        "Show games for:",
        options=[3, 7, 14],
        format_func=lambda x: f"Next {x} days",
        horizontal=True
    )
    
    try:
        with st.spinner(f"Fetching schedule for the next {days_range} days..."):
            start_date, end_date, games_df, team_ids = sched.fetch_upcoming_games_espn(days_ahead=days_range)
        
        st.write(f"**Date Range (Asia/Manila):** {start_date} to {end_date}")
        
        if not games_df.empty:
            # Add some formatting
            st.dataframe(games_df, hide_index=True, width='stretch')
            st.success(f"📊 Found {len(games_df)} games")
        else:
            st.info(f"ℹ️ No games scheduled in the next {days_range} days (Asia/Manila time).")
    except Exception as e:
        st.error(f"Could not load schedule. Error: {str(e)}")
        st.info("Try refreshing the page or check if the ESPN API is available.")

# ============================================================================
# TAB 2: PLAYER STATS — NOW ALL 30 TEAMS
# ============================================================================

with tab2:
    st.header("Player Stats - Last 10 Games")
    st.info("ℹ️ Select any NBA team and player to view their last 10 game logs.")

    # Step 1: Load ALL NBA teams
    with st.spinner("Loading all NBA team rosters... This may take a moment."):
        all_team_ids = ps.fetch_all_nba_teams()
        all_players = ps.fetch_rosters_for_teams(all_team_ids)

    total_players = sum(len(v) for v in all_players.values())
    st.caption(f"✅ Loaded {total_players} players across {len(all_players)} teams")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Select Team")
        teams_with_players = [t for t in sorted(all_players.keys()) if all_players[t]]
        if not teams_with_players:
            st.error("No players loaded. ESPN API may be unavailable.")
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
            team_id = all_team_ids[selected_team]
            recent_game_ids, game_fetch_debug = ps.fetch_recent_games_for_team(team_id)
            
            # Show debug info about game fetching
            with st.expander("🔍 Game Fetching Debug Info"):
                for debug_line in game_fetch_debug:
                    st.write(debug_line)
            
            if len(recent_game_ids) == 0:
                st.warning(f"⚠️ No recent completed games found for {selected_team}")
                st.info("This may happen if no games have been completed recently. Try again after a game finishes.")
                recent_game_ids = []
            else:
                st.caption(f"✅ Found {len(recent_game_ids)} recent completed games")

            if recent_game_ids:
                with st.spinner(f"Searching for {selected_player} in boxscores..."):
                    boxscore_player_ids, debug_log = ps.find_correct_player_ids_in_boxscores(
                        recent_game_ids,
                        selected_player,
                        selected_team
                    )

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
                        "They may not have played in the last completed games or the API data may be incomplete."
                    )
                    stats = []
                else:
                    st.caption(f"✅ Found player in boxscores with ID(s): {', '.join(boxscore_player_ids)}")

                    with st.expander("ℹ️ Player ID Mapping"):
                        st.write(f"**Roster API ID:** `{player_id}`")
                        st.write(f"**Boxscore ID(s):** {', '.join([f'`{bid}`' for bid in boxscore_player_ids])}")
                        if player_id != boxscore_player_ids[0]:
                            st.info("✓ Successfully matched player by name and found correct boxscore ID")

                    raw_stats = ps.fetch_boxscore_stats(recent_game_ids, boxscore_player_ids)
                    all_stats = []
                    for pid in boxscore_player_ids:
                        all_stats.extend(raw_stats.get(pid, []))
                    stats = ps._standardize_stats(all_stats)
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

# ============================================================================
# TAB 3: PLAYER PROPS — TOMORROW'S GAMES
# ============================================================================

with tab3:
    st.header("🎯 Player Prop Recommendations")
    st.info("Select a player playing tomorrow to see high-probability prop recommendations based on their last 10 games.")
    
    try:
        # Get tomorrow's games
        teams_tomorrow, team_ids, games_info = pp.get_tomorrow_games_info()
        
        if not teams_tomorrow:
            st.warning("⚠️ No games scheduled for tomorrow. Check back later!")
        else:
            # Display tomorrow's games
            with st.expander("📅 Tomorrow's Games (Manila Time)", expanded=True):
                for game in games_info:
                    st.write(f"🏀 **{game['Away']}** @ **{game['Home']}** | {game['Time']} ({game['Date']})")
            
            st.write("---")
            
            # Load rosters
            with st.spinner("Loading team rosters..."):
                all_team_ids = ps.fetch_all_nba_teams()
                all_players = ps.fetch_rosters_for_teams(all_team_ids)
            
            # Get players from tomorrow's teams
            players_tomorrow = {}
            for team in teams_tomorrow:
                if team in all_players:
                    players_tomorrow[team] = all_players[team]
            
            # Player selection
            col1, col2 = st.columns(2)
            
            with col1:
                teams_with_players = [t for t in sorted(teams_tomorrow) if t in players_tomorrow and players_tomorrow[t]]
                if teams_with_players:
                    selected_team = st.selectbox(
                        "Team Playing Tomorrow:",
                        teams_with_players,
                        key="prop_team_select"
                    )
                else:
                    st.error("No players found for tomorrow's teams.")
                    st.stop()
            
            with col2:
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
            
            # Fetch and analyze player
            if selected_player and selected_team:
                with st.spinner(f"Analyzing {selected_player}'s last 10 games..."):
                    team_id = all_team_ids[selected_team]
                    recent_game_ids, game_fetch_debug = ps.fetch_recent_games_for_team(team_id)
                    
                    if not recent_game_ids:
                        st.warning(f"No recent completed games found for {selected_team}.")
                        st.stop()
                    
                    # Find player
                    boxscore_player_ids, debug_log = ps.find_correct_player_ids_in_boxscores(
                        recent_game_ids,
                        selected_player,
                        selected_team
                    )
                    
                    if not boxscore_player_ids:
                        st.warning(f"Could not find {selected_player} in recent boxscores.")
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
                    
                    stats_df = pd.DataFrame(stats)
                    
                    # Display last 10 games
                    with st.expander("📊 Last 10 Games Form", expanded=False):
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
                                if not pd.isna(avg):
                                    metric_col.metric(f"Avg {col}", f"{avg:.1f}")
                    
                    # Calculate recommendations
                    st.write("---")
                    st.subheader("🔥 High-Probability Props (70%+ Hit Rate)")
                    
                    recommendations_df = pp.calculate_prop_recommendations(stats_df, selected_player)
                    
                    if recommendations_df is not None and not recommendations_df.empty:
                        st.success(f"✅ Found {len(recommendations_df)} high-confidence recommendations!")
                        
                        for stat in recommendations_df['Stat'].unique():
                            stat_recs = recommendations_df[recommendations_df['Stat'] == stat].sort_values(
                                'Hit Rate %', ascending=False
                            )
                            
                            with st.container(border=True):
                                st.markdown(f"### 📈 {stat}")
                                
                                for _, rec in stat_recs.iterrows():
                                    col1, col2, col3 = st.columns([2, 1, 1])
                                    
                                    with col1:
                                        emoji = "🟢" if rec['Type'] == "OVER" else "🔴"
                                        st.write(f"{emoji} **{rec['Prop Line']}**")
                                        st.write(f"*Hit in {rec['Games Hit']}*")
                                    
                                    with col2:
                                        st.metric("Hit Rate", f"{rec['Hit Rate %']:.0f}%")
                                    
                                    with col3:
                                        confidence = rec['Hit Rate %']
                                        if confidence >= 90:
                                            st.write("🔥 Very High")
                                        elif confidence >= 80:
                                            st.write("🌟 High")
                                        else:
                                            st.write("✓ Good")
                    else:
                        st.info(
                            f"ℹ️ No high-probability props found for {selected_player}. "
                            "The player's recent stats don't show a clear 70%+ trend for any betting lines."
                        )
    
    except Exception as e:
        st.error(f"Error loading player props: {str(e)}")
        st.info("Please check if tomorrow's games are available or try again later.")