import streamlit as st
import pandas as pd
import requests
import numpy as np
import schedule as sched
import playerstats as ps
import playerprop as pp
import nba_prediction as pred  # NEW: Import prediction module
import game_simulation as gsim  # NEW: Import game simulation module
import data_manager as dm  # NEW: Import CSV-based data manager
from datetime import datetime, timedelta
import dateutil as tz
import time
import subprocess


st.set_page_config(page_title="NBA Stats & Schedule", page_icon="🏀", layout="wide")


# ============================================================================
# DATA STATUS SIDEBAR + REFRESH FUNCTIONALITY
# ============================================================================

with st.sidebar:
    st.header("📊 Data Status")
    
    try:
        info = dm.get_refresh_info()
        
        # Display data age
        if info['fresh']:
            st.success(f"✅ Data is fresh ({info['age_hours']:.1f}h old)")
        else:
            st.warning(f"⚠️ Data is stale ({info['age_hours']:.1f}h old)")
        
        st.caption(f"Last refresh: {info['last_refresh']}")
        
        # Refresh button
        if st.button("🔄 Refresh Data Now", use_container_width=True, help="Fetch fresh data from ESPN and update CSVs"):
            with st.spinner("🔄 Refreshing data... This may take 2-3 minutes..."):
                try:
                    result = subprocess.run(['python', 'data_refresh.py'], 
                                          capture_output=True, text=True, timeout=300)
                    if result.returncode == 0:
                        st.success("✅ Data refresh complete!")
                        st.rerun()
                    else:
                        st.error(f"❌ Refresh failed: {result.stderr}")
                except Exception as e:
                    st.error(f"❌ Error running refresh: {e}")
        
        st.divider()
        
    except FileNotFoundError:
        st.error("📦 No data found!")
        st.info("Run this command to fetch initial data:\n\n`python data_refresh.py`")
        st.stop()

# ============================================================================
# MAIN APP
# ============================================================================

st.title("🏀 NBA Stats & Schedule Hub")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📅 Upcoming Games", "📊 Player Stats", "🎯 Player Props", "🤖 Player Prediction","Prediction History", "🎮 Game Simulation"])

# ============================================================================
# LOAD DATA FROM CSVs
# ============================================================================
with st.spinner("Loading data from local storage..."):
    all_team_ids_df = dm.get_all_teams()
    all_rosters_df = dm.get_all_rosters()
    
    # Convert to dict format for backwards compatibility with existing code
    # all_team_ids[team_name] -> {"id": id, "logo": logo, "display_name": name}
    all_team_ids = {}
    for _, row in all_team_ids_df.iterrows():
        team_name = row['Display Name']
        all_team_ids[team_name] = {
            "id": str(row['ID']),
            "logo": row.get('Logo', ''),
            "display_name": team_name
        }
    
    # Convert rosters to nested dict: all_players[team_name][player_name] -> {player_info}
    all_players = {}
    for team_name in all_rosters_df['Team'].unique():
        team_roster = all_rosters_df[all_rosters_df['Team'] == team_name]
        all_players[team_name] = {}
        for _, player in team_roster.iterrows():
            player_name = player['Player Name']
            all_players[team_name][player_name] = {
                "id": str(player.get('Player ID', '')),
                "image": player.get('Image', ''),
                "position": player.get('Position', 'N/A'),
                "jersey": player.get('Jersey', 'N/A'),
                "age": player.get('Age', 'N/A'),
                "height": player.get('Height', 'N/A'),
                "weight": player.get('Weight', 'N/A'),
                "experience": player.get('Experience', 'N/A')
            }

# Get upcoming teams
upcoming_teams = set(all_team_ids.keys())

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

    total_players = sum(len(v) for v in all_players.values())
    st.caption(f"✅ Loaded {total_players} players across {len(all_players)} teams")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Select Team")
        teams_with_players = [t for t in sorted(all_players.keys()) if all_players[t] and (not upcoming_teams or t in upcoming_teams)]
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
        player_info = roster[selected_player]
        player_id = player_info["id"]
        player_image = player_info["image"]
        team_logo = all_team_ids[selected_team]["logo"]
        team_id = all_team_ids[selected_team]["id"]
        
        # Extract new bio info
        player_position = player_info.get("position", "N/A")
        player_jersey = player_info.get("jersey", "N/A")
        player_age = player_info.get("age", "N/A")
        player_height = player_info.get("height", "N/A")
        player_weight = player_info.get("weight", "N/A")
        player_experience = player_info.get("experience", "N/A")

        col_p1, col_p2 = st.columns([1, 5])
        with col_p1:
            if player_image: st.image(player_image, width=120)
        with col_p2:
            st.subheader(f"{selected_player}")
            st.image(team_logo, width=60)
            st.markdown(f"""
                **Team:** {selected_team} | **Position:** {player_position} | **Jersey:** #{player_jersey}  
                **Age:** {player_age} | **Height:** {player_height} | **Weight:** {player_weight} | **Experience:** {player_experience} yrs
            """)

        with st.spinner(f"Loading stats for {selected_player}..."):
            # Load player stats from pre-fetched CSV data (no API calls needed!)
            stats_df = dm.get_player_recent_stats(selected_player, selected_team)
            
            if stats_df.empty:
                st.warning(f"⚠️ No stats found for {selected_player} in {selected_team}")
                st.info("Data is pre-fetched daily. Check back after new games are completed.")
            else:
                st.caption(f"✅ Found {len(stats_df)} recent games")

        if not stats_df.empty:
            st.dataframe(stats_df, hide_index=True, width='stretch')

            st.subheader("Summary (Last 10 Games)")
            numeric_df = stats_df.select_dtypes(include=['number'])
            summary_cols = st.columns(5)
            
            # Try common stat column names
            pts_cols = [c for c in numeric_df.columns if 'pt' in c.lower() or 'point' in c.lower()]
            reb_cols = [c for c in numeric_df.columns if 'reb' in c.lower()]
            ast_cols = [c for c in numeric_df.columns if 'ast' in c.lower()]
            stl_cols = [c for c in numeric_df.columns if 'stl' in c.lower()]
            blk_cols = [c for c in numeric_df.columns if 'blk' in c.lower()]
            
            if pts_cols:
                summary_cols[0].metric("Avg Points", f"{numeric_df[pts_cols[0]].mean():.1f}")
            if reb_cols:
                summary_cols[1].metric("Avg Rebounds", f"{numeric_df[reb_cols[0]].mean():.1f}")
            if ast_cols:
                summary_cols[2].metric("Avg Assists", f"{numeric_df[ast_cols[0]].mean():.1f}")
            if stl_cols:
                summary_cols[3].metric("Avg Steals", f"{numeric_df[stl_cols[0]].mean():.1f}")
            if blk_cols:
                summary_cols[4].metric("Avg Blocks", f"{numeric_df[blk_cols[0]].mean():.1f}")

# ============================================================================
# TAB 3: PLAYER PROPS — WITH ML RECOMMENDATIONS
# ============================================================================

with tab3:
    st.header("🎯 Player Props - ML Predictions")
    st.info("ℹ️ Select a player to see ML-powered prop recommendations")

    # Team and player selection (reuse from tab 2)
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Select Team")
        teams_with_players = [t for t in sorted(all_players.keys()) if all_players[t] and (not upcoming_teams or t in upcoming_teams)]
        selected_team_props = st.selectbox("Choose a team:", teams_with_players, key="team_select_props")

    with col2:
        st.subheader("Select Player")
        roster_props = all_players.get(selected_team_props, {})
        if roster_props:
            selected_player_props = st.selectbox(
                "Choose a player:", sorted(roster_props.keys()), key="player_select_props"
            )
        else:
            st.warning(f"No players found for {selected_team_props}.")
            selected_player_props = None

    if selected_player_props and roster_props:
        player_info_props = roster_props[selected_player_props]
        player_id_props = player_info_props["id"]
        player_image_props = player_info_props["image"]
        team_logo_props = all_team_ids[selected_team_props]["logo"]
        team_id_props = all_team_ids[selected_team_props]["id"]
        
        # Extract new bio info
        player_position_props = player_info_props.get("position", "N/A")
        player_jersey_props = player_info_props.get("jersey", "N/A")
        player_age_props = player_info_props.get("age", "N/A")
        player_height_props = player_info_props.get("height", "N/A")
        player_weight_props = player_info_props.get("weight", "N/A")
        player_experience_props = player_info_props.get("experience", "N/A")

        # Get tomorrow's opponent
        tomorrow_opponent = None
        try:
            tomorrow_games, _, _, _ = sched.fetch_upcoming_games_espn(days_ahead=1)
            if not tomorrow_games.empty:
                # Filter for games where selected_team_props is either home or visitor
                team_games = tomorrow_games[
                    (tomorrow_games['Home Team'] == selected_team_props) |
                    (tomorrow_games['Visitor Team'] == selected_team_props)
                ]
                if not team_games.empty:
                    game = team_games.iloc[0]
                    tomorrow_opponent = game['Visitor Team'] if game['Home Team'] == selected_team_props else game['Home Team']
        except:
            pass

        with st.spinner(f"Loading data for {selected_player_props}..."):
            # Load player stats from pre-fetched CSV data (no API calls!)
            stats_df = dm.get_player_recent_stats(selected_player_props, selected_team_props)
            
            if stats_df.empty:
                st.warning(f"⚠️ No stats found for {selected_player_props}")
            else:
                # Ensure Date column is datetime
                if 'Date' in stats_df.columns:
                    stats_df['Date'] = pd.to_datetime(stats_df['Date'], errors='coerce')
                    stats_df = stats_df.sort_values('Date', ascending=False)

                # Display Player Header
                prop_head1, prop_head2 = st.columns([1, 5])
                with prop_head1:
                    if player_image_props: st.image(player_image_props, width=120)
                with prop_head2:
                    st.subheader(f"{selected_player_props}")
                    st.image(team_logo_props, width=60)
                    st.markdown(f"""
                        **Team:** {selected_team_props} | **Position:** {player_position_props} | **Jersey:** #{player_jersey_props}  
                        **Age:** {player_age_props} | **Height:** {player_height_props} | **Weight:** {player_weight_props} | **Experience:** {player_experience_props} yrs
                    """)

                # Compute combo stats for display
                stats_df = pp.compute_combo_stats(stats_df)

                display_df = stats_df.head(10)

                # Display last 10 games
                with st.expander("📊 Last 10 Games Performance", expanded=False):
                    display_cols = ['Date', 'Opponent', 'Minutes', 'Points', 'Rebounds', 'Assists', 
                                    'PRA', 'Points+Rebounds', 'Points+Assists', 'Rebounds+Assists',
                                    'Steals', 'Blocks', '3PM', 'FG%', '3P%', 'FT%']
                    available_cols = [col for col in display_cols if col in display_df.columns]
                    st.dataframe(display_df[available_cols], hide_index=True, width='stretch')

                    # Stats overview — Row 1: Base stats
                    games_in_display = len(display_df)
                    st.markdown(f"#### Last {games_in_display} Game{'s' if games_in_display != 1 else ''} Averages:")
                    metric_cols = st.columns(5)

                    for idx, (col, metric_col) in enumerate([
                        ('Points', metric_cols[0]),
                        ('Rebounds', metric_cols[1]),
                        ('Assists', metric_cols[2]),
                        ('Steals', metric_cols[3]),
                        ('Blocks', metric_cols[4])
                    ]):
                        if col in display_df.columns:
                            numeric_vals = pd.to_numeric(display_df[col], errors='coerce')
                            avg = numeric_vals.mean()
                            if not np.isnan(avg):
                                metric_col.metric(f"Avg {col}", f"{avg:.1f}")

                    # Row 2: Combo stats & 3PM
                    combo_metric_cols = st.columns(5)
                    combo_stats = [
                        ('PRA', combo_metric_cols[0]),
                        ('Points+Rebounds', combo_metric_cols[1]),
                        ('Points+Assists', combo_metric_cols[2]),
                        ('Rebounds+Assists', combo_metric_cols[3]),
                        ('3PM', combo_metric_cols[4])
                    ]

                    for col, metric_col in combo_stats:
                        if col in display_df.columns:
                            numeric_vals = pd.to_numeric(display_df[col], errors='coerce')
                            avg = numeric_vals.mean()
                            if not np.isnan(avg):
                                metric_col.metric(f"Avg {col}", f"{avg:.1f}")

                # ML-Powered Recommendations
                st.write("---")

                # Show opponent context
                if tomorrow_opponent:
                    opp_logo = all_team_ids.get(tomorrow_opponent, {}).get('logo', "")
                    col_match1, col_match2 = st.columns([1, 6])
                    with col_match1:
                        if opp_logo: st.image(opp_logo, width=80)
                    with col_match2:
                        st.info(f"🎯 **Matchup:** {selected_player_props} vs {tomorrow_opponent}")
                        st.write("*Props adjusted for opponent defensive strength*")

                st.subheader("🤖 ML Prop Recommendations (Probability-Weighted)")

                # Initialize recommender
                recommender = pp.AdvancedPropRecommender()

                # Calculate recommendations
                recommendations_df, n_analyzed = recommender.calculate_advanced_recommendations(
                    stats_df, 
                    selected_player_props, 
                    n_games=10,
                    tomorrow_opponent=tomorrow_opponent
                )

                if recommendations_df is not None and not recommendations_df.empty:
                    # Filter by probability threshold
                    high_prob_recs = recommendations_df[
                        recommendations_df['Probability'].str.rstrip('%').astype(float) >= 65
                    ]

                    if not high_prob_recs.empty:
                        st.success(f"✅ Found {len(high_prob_recs)} high-confidence recommendation{'s' if len(high_prob_recs) != 1 else ''} "
                                f"based on {n_analyzed} game{'s' if n_analyzed != 1 else ''}!")

                        # Group by stat type
                        for stat in high_prob_recs['Stat'].unique():
                            stat_recs = high_prob_recs[high_prob_recs['Stat'] == stat].sort_values(
                                'Probability', ascending=False, key=lambda x: x.str.rstrip('%').astype(float)
                            )

                            st.markdown(f"### 📈 {stat}")

                            # Display each recommendation
                            for _, rec in stat_recs.iterrows():
                                with st.container(border=True):
                                    col1, col2, col3 = st.columns([2, 1, 1])

                                    with col1:
                                        st.markdown(pp.style_recommendation(rec))

                                    with col2:
                                        prob_val = float(rec['Probability'].rstrip('%'))
                                        st.metric(
                                            "Win Probability",
                                            f"{rec['Probability']}",
                                            delta=f"{rec['Hit Rate %']:.0f}% hit"
                                        )

                                    with col3:
                                        hit_rate = float(rec['Hit Rate %'])
                                        if hit_rate >= 85:
                                            st.write("### 🔥 ELITE")
                                        elif hit_rate >= 75:
                                            st.write("### ⭐ STRONG")
                                        else:
                                            st.write("### ✓ SOLID")

                        # Advanced metrics summary
                        st.write("---")
                        with st.expander("📊 ML Model Details", expanded=False):
                            col1, col2, col3, col4 = st.columns(4)

                            avg_prob = recommendations_df['Probability'].str.rstrip('%').astype(float).mean()
                            avg_hit_rate = recommendations_df['Hit Rate %'].mean()
                            avg_confidence = recommendations_df['Confidence'].str.rstrip('%').astype(float).mean()

                            col1.metric("Avg ML Probability", f"{avg_prob:.0f}%")
                            col2.metric("Avg Hit Rate", f"{avg_hit_rate:.0f}%")
                            col3.metric("Avg Model Confidence", f"{avg_confidence:.0f}%")
                            col4.metric("Recommendations", len(high_prob_recs))

                            st.write("**Model Components:**")
                            st.write("- 🌳 XGBoost (gradient boosting)")
                            st.write("- 🎲 Random Forest ensemble")
                            st.write("- 📊 Ridge regression")
                            st.write("- 🎯 Opponent strength adjustment")
                            st.write("- 📈 Trend detection & momentum analysis")
                            st.write("- ⏰ Time-weighted recent form")
                            st.write("- 🔗 Combo stat correlation modeling (PRA, PR, PA, RA)")
                            st.write("- 🏀 3-Point volume trend tracking")

                    else:
                        st.info(
                            f"ℹ️ No high-probability props found (need ≥65% ML confidence). "
                            f"Analyzed last {n_analyzed} game{'s' if n_analyzed != 1 else ''}."
                        )

                else:
                    st.info(
                        f"ℹ️ ML analysis unable to generate confident recommendations. "
                        f"Ensure player has sufficient recent game data."
                    )


# ============================================================================
# TAB 4: PLAYER PREDICTION (NEW)
# ============================================================================

with tab4:
    st.header("🤖 Advanced Player Stats Prediction")
    st.info("ℹ️ Uses machine learning to predict a player's next game stats based on recent performance")
    
    # Layman's explanation
    with st.expander("📖 What is this prediction?", expanded=False):
        st.markdown("""
        **In Simple Terms:**
        
        This tool looks at how a player has performed in their last 10 games and uses AI to guess how many points, 
        rebounds, assists, and 3-pointers they might score in their next game.
        
        Think of it like this: If you always score around 25 points per game, then next game you'll probably score 
        around 25 points too. But the AI is smarter - it also considers:
        - Whether they played well or poorly recently
        - Who they're playing against (some teams have better defenses than others)
        - How rested the player is
        - How many minutes they usually play
        
        **The prediction is NOT 100% accurate** - it's just a smart guess based on patterns. Real players have 
        off-nights, injuries, or unexpected performances. But if the prediction says a player usually scores around 
        25 points, they'll probably score somewhere between 20-30 points most games.
        """)
    

    # Team and player selection
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Select Team")
        # Only show teams that have upcoming games scheduled
        teams_with_players = [t for t in sorted(all_players.keys()) if all_players[t] and (not upcoming_teams or t in upcoming_teams)]
        if not teams_with_players:
            teams_with_players = sorted(all_players.keys())
            
        selected_team_pred = st.selectbox("Choose a team:", teams_with_players, key="team_select_pred")

    with col2:
        st.subheader("Select Player")
        roster_pred = all_players.get(selected_team_pred, {})
        if roster_pred:
            selected_player_pred = st.selectbox(
                "Choose a player:", sorted(roster_pred.keys()), key="player_select_pred"
            )
        else:
            st.warning(f"No players found for {selected_team_pred}.")
            selected_player_pred = None

    if selected_player_pred and roster_pred:
        player_info_pred = roster_pred[selected_player_pred]
        player_id_pred = player_info_pred["id"]
        player_image_pred = player_info_pred["image"]
        team_logo_pred = all_team_ids[selected_team_pred]["logo"]
        team_id_pred = all_team_ids[selected_team_pred]["id"]
        
        # Extract new bio info
        player_position_pred = player_info_pred.get("position", "N/A")
        player_jersey_pred = player_info_pred.get("jersey", "N/A")
        player_age_pred = player_info_pred.get("age", "N/A")
        player_height_pred = player_info_pred.get("height", "N/A")
        player_weight_pred = player_info_pred.get("weight", "N/A")
        player_experience_pred = player_info_pred.get("experience", "N/A")

        # Ensure upcoming_games_df is available for opponent lookup
        if 'upcoming_games_df' not in locals() or upcoming_games_df.empty:
            _, _, upcoming_games_df, _ = sched.fetch_upcoming_games_espn(days_ahead=14)

        # Determine the next opponent for the selected team
        next_opponent = None
        if not upcoming_games_df.empty:
            team_match = upcoming_games_df[
                (upcoming_games_df['Home Team'] == selected_team_pred) | 
                (upcoming_games_df['Visitor Team'] == selected_team_pred)
            ]
            if not team_match.empty:
                game = team_match.iloc[0]
                next_opponent = game['Visitor Team'] if game['Home Team'] == selected_team_pred else game['Home Team']

        # Load stats
        with st.spinner(f"Loading prediction data for {selected_player_pred}..."):
            # Load player stats from pre-fetched CSV data (no API calls!)
            stats_df = dm.get_player_recent_stats(selected_player_pred, selected_team_pred)
            
            if stats_df.empty:
                st.warning(f"⚠️ No stats found for {selected_player_pred}")
            else:
                stats = stats_df.to_dict('records')
                
                if stats and len(stats) >= 3:
                    # Convert to standardized columns
                    stats_df = pd.DataFrame(stats)
                    
                    # STEP 1: Clean data - handle string formats like '10-22'
                    for col in stats_df.columns:
                        if col not in ['Date', 'OPP', 'Opponent']:
                            stats_df[col] = stats_df[col].astype(str).apply(
                                lambda x: x.split('-')[0].strip() if '-' in str(x) else x
                            )
                    
                    # STEP 2: Rename columns to match prediction model expectations
                    column_mapping = {
                        'Points': 'PTS',
                        'Rebounds': 'REB',
                        'Assists': 'AST',
                        '3PM': '3PM',
                        'Field Goals Made': 'FGM',
                        'Field Goals Attempted': 'FGA',
                        'Free Throws Made': 'FTM',
                        'Free Throws Attempted': 'FTA',
                        '3 Point Attempts': '3PA',
                        'Minutes': 'MIN',
                        'Turnovers': 'TO',
                        'Steals': 'STL',
                        'Opponent': 'OPP'
                    }
                    
                    for old_col, new_col in column_mapping.items():
                        if old_col in stats_df.columns and new_col not in stats_df.columns:
                            stats_df[new_col] = stats_df[old_col]
                    
                    # STEP 3: Convert to numeric
                    numeric_cols = ['PTS', 'AST', 'REB', '3PM', 'FGM', 'FGA', 'FTM', 'FTA', '3PA', 'MIN', 'TO', 'STL']
                    for col in numeric_cols:
                        if col in stats_df.columns:
                            stats_df[col] = pd.to_numeric(stats_df[col], errors='coerce')
                    
                    # Note: Opponent defensive metrics are now pre-calculated in data_refresh.py
                    # Using simplified prediction without live opponent analysis (can be enhanced later)
                    opp_def_stats = {}

                    # Engineer features (simplified version without live opponent fetching)
                    stats_df_engineered = pred.engineer_features(stats_df, name=selected_player_pred, opp_def_stats=opp_def_stats)
                    
                    if stats_df_engineered is not None and not stats_df_engineered.empty:
                        # Display Player Header
                        pred_head1, pred_head2 = st.columns([1, 5])
                        with pred_head1:
                            if player_image_pred: st.image(player_image_pred, width=120)
                        with pred_head2:
                            st.subheader(f"{selected_player_pred}")
                            st.image(team_logo_pred, width=60)
                        
                        # Display recent stats
                        st.subheader(f"📊 Recent Game History")
                        
                        display_cols = ['Date', 'OPP', 'PTS', 'REB', 'AST', '3PM', 'MIN']
                        available_cols = [col for col in display_cols if col in stats_df_engineered.columns]
                        
                        # Show last 10 games
                        st.dataframe(
                            stats_df_engineered[available_cols].head(10),
                            hide_index=True,
                            width='stretch'
                        )
                        
                        # Build and display predictions
                    st.subheader(f"🎯 Prediction vs {next_opponent if next_opponent else 'Unknown'}")
                
                    predictions_data = []
                    models_built = {}
                
                    for stat in ['PTS', 'AST', 'REB', '3PM']:
                        model, mae, r2, preds = pred.build_prediction_models(stats_df_engineered, stat=stat)
                    
                    if model is not None:
                        models_built[stat] = (model, mae, r2)
                        
                        # Get prediction for next game
                        # Pass upcoming opponent defensive stats to the model
                        next_opp_data = opp_def_stats.get(next_opponent)
                        next_prediction = pred.predict_next_game(model, stats_df_engineered, next_opp_data)
                        
                        # For the next game, we assume 1 day rest and not back-to-back
                        # This is a simplification. A more advanced approach would involve knowing the actual schedule.
                        # The predict_next_game function in nba_prediction.py handles this for the prediction input.

                        if next_prediction is not None:
                            # Get recent averages
                            recent_stat = stats_df_engineered[stat].tail(5).mean()
                            last_game_stat = stats_df_engineered[stat].iloc[-1] if len(stats_df_engineered) > 0 else None
                            
                            predictions_data.append({
                                'Stat': stat,
                                'Prediction': next_prediction,
                                'Last Game': last_game_stat,
                                'Last 5 Avg': recent_stat,
                                'Range': f"{max(0, next_prediction-2):.1f}-{next_prediction+2:.1f}",
                                'MAE': f"±{mae:.1f}",
                                'R² Score': f"{r2:.2f}"
                            })
                
                    if predictions_data:
                        pred_df = pd.DataFrame(predictions_data)
                    
                    # Display in columns
                    cols = st.columns(4)
                    for idx, stat in enumerate(['PTS', 'AST', 'REB', '3PM']):
                        with cols[idx]:
                            stat_data = pred_df[pred_df['Stat'] == stat]
                            if not stat_data.empty:
                                row = stat_data.iloc[0]
                                st.metric(
                                    f"{stat} Prediction",
                                    f"{row['Prediction']:.1f}",
                                    delta=f"Last: {row['Last Game']:.1f}"
                                )
                                st.caption(f"Range: {row['Range']}\nAccuracy: {row['MAE']}")
                    
                    # Button to record predictions
                    st.write("---")
                    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                    
                    with col_btn1:
                        if st.button("✅ Record Predictions", key="record_pred_button", help="Save these predictions to history"):
                            # Initialize session state for this player/date combo
                            session_key = f"{selected_player_pred}_{selected_team_pred}_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}"
                            
                            if session_key not in st.session_state:
                                st.session_state[session_key] = True
                                
                                # Record all predictions
                                for _, row in pred_df.iterrows():
                                    pred.record_prediction(
                                        selected_player_pred,
                                        selected_team_pred,
                                        row['Stat'],
                                        row['Prediction']
                                    )
                                
                                st.success(f"✅ Recorded 4 predictions for {selected_player_pred}!")
                            else:
                                st.warning("⚠️ These predictions have already been recorded.")
                    
                    with col_btn2:
                        if st.button("🔄 Clear Session", key="clear_session_button", help="Reset to allow re-recording"):
                            st.session_state.clear()
                            st.info("Session cleared. You can now re-record predictions if needed.")
                    
                    # Show detailed table
                    st.subheader("📋 Detailed Predictions")
                    st.dataframe(pred_df, hide_index=True, use_container_width=True)
                    
                    # Layman's explanation of the results
                    with st.expander("🤔 How to Read These Results", expanded=True):
                        st.markdown("""
                        **What each column means:**
                        
                        - **Prediction**: The AI's best guess for how many of this stat the player will get in the next game
                        - **Last Game**: How many they actually got in their most recent game
                        - **Last 5 Avg**: The average over their last 5 games (shows their typical performance)
                        - **Range**: A reasonable range for the prediction (e.g., if prediction is 25, range might be 23-27)
                        - **MAE (±)**: "Margin of Error" - How far off the predictions usually are. Lower is better. 
                          For example, ±3.5 means predictions are typically within 3-4 points of actual
                        - **R² Score**: How well the AI understands this player's patterns (0.0 = not accurate, 1.0 = perfect)
                          - 0.7 or higher = pretty good
                          - 0.5-0.7 = okay
                          - Below 0.5 = use with caution
                        
                        **Example:** If it predicts 25 PTS with ±2.5 accuracy, the player will probably score between 22-28 points.
                        """)
                    
                    # Feature importance
                    st.subheader("🔍 Feature Importance")
                    
                    # Use first model's features as example
                    first_stat = next(iter(models_built))
                    if models_built[first_stat][0] is not None:
                        importance_df = pred.get_feature_importance(
                            models_built[first_stat][0],
                            stats_df_engineered
                        )
                        
                        if importance_df is not None and not importance_df.empty:
                            st.write(f"**Top factors affecting {selected_player_pred}'s performance:**")
                            st.markdown("""
                            *The chart below shows which factors the AI thinks are most important for predicting 
                            this player's stats. Taller bars = more important factors.*
                            """)
                            
                            # Create bar chart
                            top_features = importance_df.head(10)
                            
                            import plotly.express as px
                            fig = px.bar(
                                top_features,
                                x='Importance',
                                y='Feature',
                                orientation='h',
                                title='Top 10 Feature Importance',
                                color='Importance',
                                color_continuous_scale='viridis'
                            )
                            fig.update_layout(height=400, showlegend=False)
                            st.plotly_chart(fig, width='stretch')
                    
                    # Model insights
                    st.subheader("📊 Model Insights")
                    st.markdown("*How has this player been performing lately?*")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    
                    if models_built:
                        stats_summary = pred.calculate_stats_summary(stats_df_engineered, games=5)
                        
                        if stats_summary:
                            if 'PTS' in stats_summary:
                                col1.metric(
                                    "Avg Points", 
                                    f"{stats_summary['PTS']['avg']:.1f}",
                                    help="Average points over last 5 games"
                                )
                            if 'AST' in stats_summary:
                                col2.metric(
                                    "Avg Assists", 
                                    f"{stats_summary['AST']['avg']:.1f}",
                                    help="Average assists over last 5 games"
                                )
                            if 'REB' in stats_summary:
                                col3.metric(
                                    "Avg Rebounds", 
                                    f"{stats_summary['REB']['avg']:.1f}",
                                    help="Average rebounds over last 5 games"
                                )
                            if '3PM' in stats_summary:
                                col4.metric(
                                    "Avg 3-Pointers", 
                                    f"{stats_summary['3PM']['avg']:.1f}",
                                    help="Average 3-pointers made over last 5 games"
                                )
                    
                    # Recommendations and Layman's Guide
                    with st.expander("✅ Understanding Model Accuracy", expanded=False):
                        st.markdown("""
                        **What's Good? What's Bad?**
                        
                        **R² Score Interpretation:**
                        - 🟢 **0.8 or higher** = Excellent! The model really understands this player
                        - 🟡 **0.6-0.8** = Good! You can trust these predictions
                        - 🟠 **0.4-0.6** = Okay - Use as a general guide, not exact
                        - 🔴 **Below 0.4** = Weak - Player is inconsistent or unpredictable
                        
                        **Margin of Error (MAE) Interpretation:**
                        - If MAE is ±2, most predictions will be within 2 points of actual
                        - If MAE is ±5, predictions might be way off sometimes
                        - Lower MAE = more trustworthy
                        
                        **Why Predictions Might Be Wrong:**
                        - Player is injured or not at full strength
                        - Player had a big argument with coach or team drama
                        - Coach changed their role (fewer minutes, different position)
                        - Opponent's defense is unusually strong or weak
                        - It's just a bad day for the player!
                        
                        **Tips for Better Predictions:**
                        - Use predictions for recent, active players (more data = better guesses)
                        - Don't rely solely on predictions - check injury news!
                        - Watch for trends: Is the player improving or declining?
                        - Compare to their "Last 5 Avg" - predictions usually stay close to recent averages
                        """)
                    
                    # Summary guidance
                    st.info(
                        "💡 **Quick Takeaway:**\n"
                        "These predictions are your AI assistant - helpful for betting, fantasy basketball, or curiosity, "
                        "but not crystal balls! Always combine with real-world knowledge (injuries, trades, etc.)."
                    )                   
                else:
                    st.warning("Could not build prediction models. Try a different player with more recent game data.")
            else:
                    st.warning("Could not engineer features from player stats.")
        else:
            st.warning(
                f"Not enough data for {selected_player_pred}. "
                f"Need at least 3 recent games to make predictions.\n\n"
                f"Games found: {len(stats) if stats else 0}"
            )



# ============================================================================
# TAB 6: GAME SIMULATION (NEW)
# ============================================================================

with tab6:
    st.header("🎮 NBA Game Simulator")
    st.info("ℹ️ Watch two teams battle it out! The simulation is based on player ratings calculated from recent performance.")
    
    # Team selection
    col1, col2 = st.columns(2)
    
    all_teams = sorted(all_players.keys())
    
    with col1:
        st.subheader("🏠 Home Team")
        home_team_sim = st.selectbox("Choose home team:", all_teams, key="sim_home_team")
    
    with col2:
        st.subheader("✈️ Away Team")
        away_teams = [t for t in all_teams if t != home_team_sim]
        away_team_sim = st.selectbox("Choose away team:", away_teams, key="sim_away_team")
    
    # Get rosters (need to be defined before columns so they persist)
    home_roster_sim = all_players.get(home_team_sim, {})
    away_roster_sim = all_players.get(away_team_sim, {})
    
    # Show player rosters and ratings
    st.write("---")
    st.subheader("📊 Team Ratings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"### {home_team_sim}")
        
        if home_roster_sim:
            home_roster_data = []
            for player_name in list(home_roster_sim.keys())[:8]:  # Top 8 players
                player_stats = home_roster_sim.get(player_name)
                
                if isinstance(player_stats, pd.DataFrame) and not player_stats.empty:
                    # Create player rating
                    player_rating = gsim.PlayerRating(player_stats, player_name)
                    rating_card = gsim.get_player_rating_card(player_rating)
                    
                    home_roster_data.append({
                        'Player': player_name,
                        'Overall': rating_card['Overall'],
                        '3-Pt': rating_card['3-Pt'],
                        'Playmaker': rating_card['Playmaker'],
                        'Rebounder': rating_card['Rebounder'],
                        'Defender': rating_card['Defender']
                    })
            
            if home_roster_data:
                st.dataframe(pd.DataFrame(home_roster_data), hide_index=True, use_container_width=True)
    
    with col2:
        st.markdown(f"### {away_team_sim}")
        
        if away_roster_sim:
            away_roster_data = []
            for player_name in list(away_roster_sim.keys())[:8]:  # Top 8 players
                player_stats = away_roster_sim.get(player_name)
                
                if isinstance(player_stats, pd.DataFrame) and not player_stats.empty:
                    # Create player rating
                    player_rating = gsim.PlayerRating(player_stats, player_name)
                    rating_card = gsim.get_player_rating_card(player_rating)
                    
                    away_roster_data.append({
                        'Player': player_name,
                        'Overall': rating_card['Overall'],
                        '3-Pt': rating_card['3-Pt'],
                        'Playmaker': rating_card['Playmaker'],
                        'Rebounder': rating_card['Rebounder'],
                        'Defender': rating_card['Defender']
                    })
            
            if away_roster_data:
                st.dataframe(pd.DataFrame(away_roster_data), hide_index=True, use_container_width=True)
    
    # Simulation controls
    st.write("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        speed = st.select_slider(
            "Simulation Speed",
            options=["🐢 Slow", "🏃 Normal", "⚡ Fast"],
            value="🏃 Normal",
            key="sim_speed"
        )
    
    speed_map = {"🐢 Slow": 0.5, "🏃 Normal": 0.2, "⚡ Fast": 0.05}
    delay = speed_map[speed]
    
    with col2:
        if st.button("🎬 START GAME", key="start_sim", use_container_width=True):
            st.session_state.simulation_running = True
    
    with col3:
        st.info("Click START GAME to begin the simulation!")
    
    # Run simulation
    if st.session_state.get('simulation_running', False):
        st.write("---")
        
        # Prepare player stats by loading from pre-fetched data
        home_roster_for_sim = {}
        away_roster_for_sim = {}
        
        with st.spinner("Loading player statistics for both teams..."):
            # Fetch home team stats from CSV
            home_stats_all = dm.get_player_stats(team_name=home_team_sim)
            if not home_stats_all.empty:
                for player_name in list(home_roster_sim.keys())[:12]:  # Top 12 players
                    try:
                        player_stats = home_stats_all[home_stats_all['Player Name'].str.contains(player_name, case=False, na=False)]
                        if not player_stats.empty:
                            home_roster_for_sim[player_name] = player_stats
                    except:
                        pass
            
            # Fetch away team stats from CSV
            away_stats_all = dm.get_player_stats(team_name=away_team_sim)
            if not away_stats_all.empty:
                for player_name in list(away_roster_sim.keys())[:12]:  # Top 12 players
                    try:
                        player_stats = away_stats_all[away_stats_all['Player Name'].str.contains(player_name, case=False, na=False)]
                        if not player_stats.empty:
                            away_roster_for_sim[player_name] = player_stats
                    except:
                        pass
        
        if home_roster_for_sim and away_roster_for_sim:
            # Create simulator
            import time
            simulator = gsim.NBAGameSimulator(
                home_team_sim,
                away_team_sim,
                home_roster_for_sim,
                away_roster_for_sim
            )
            
            # Simulate full game
            simulator.simulate_game()
            
            # ========== LIVE BROADCAST UI ==========
            
            # Score updates per quarter
            for q in range(1, 5):
                st.write("---")
                
                # Scoreboard
                col1, col2, col3 = st.columns([2, 1, 2])
                with col1:
                    st.markdown(f"# {home_team_sim}")
                with col2:
                    st.markdown(f"### Q{q}")
                with col3:
                    st.markdown(f"# {away_team_sim}", unsafe_allow_html=False)
                
                col1, col2, col3 = st.columns([2, 1, 2])
                with col1:
                    st.markdown(f"## {simulator.home_score}")
                with col2:
                    st.markdown("")
                with col3:
                    st.markdown(f"## {simulator.away_score}")
                
                # Play-by-play for quarter
                st.subheader(f"📹 Q{q} Play-by-Play ({simulator.possession_count} possessions)")
                quarter_plays = [p for p in simulator.play_log if p['quarter'] == q]
                
                play_cols = st.columns([0.5, 1, 6, 1.5])
                play_cols[0].write("**Q**")
                play_cols[1].write("**Time**")
                play_cols[2].write("**Play**")
                play_cols[3].write("**Score**")
                
                for play in quarter_plays:
                    if play['time'] == 'END':
                        st.success(f"**{play['description']}**")
                    else:
                        # Color coding
                        if play['color'] == 'green':
                            st.success(f"✅ {play['description']}")
                        elif play['color'] == 'red':
                            st.error(f"❌ {play['description']}")
                        elif play['color'] == 'yellow':
                            st.warning(f"⚠️ {play['description']}")
                        elif play['color'] == 'purple':
                            st.info(f"🔐 {play['description']}")
                        elif play['color'] == 'blue':
                            st.info(f"🏀 {play['description']}")
                        else:
                            st.write(play['description'])
            
            # ========== FINAL SCORE ==========
            st.write("---")
            st.markdown("# 🏁 FINAL SCORE")
            
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.markdown(f"### {home_team_sim}")
            with col2:
                st.markdown("")
            with col3:
                st.markdown(f"### {away_team_sim}")
            
            col1, col2, col3 = st.columns([2, 1, 2])
            with col1:
                st.markdown(f"# {simulator.home_score}")
            with col2:
                if simulator.home_score > simulator.away_score:
                    st.markdown(f"# 🏆")
                else:
                    st.markdown(f"# 🏆")
            with col3:
                st.markdown(f"# {simulator.away_score}")
            
            # ========== BOX SCORES (ONLY PLAYERS WHO PLAYED) ==========
            st.write("---")
            st.subheader("📊 Box Scores (Players Who Played)")
            
            tab_home, tab_away = st.tabs([f"🏠 {home_team_sim}", f"✈️ {away_team_sim}"])
            
            with tab_home:
                home_box = simulator.get_home_team_stats()
                if not home_box.empty:
                    # Format for display
                    display_cols = ['Player', 'PTS', 'REB', 'AST', '3PM', 'STL', 'BLK', 'TO', 'MIN', 'FGM', 'FGA', 'FTM', 'FTA']
                    display_cols = [c for c in display_cols if c in home_box.columns]
                    
                    st.dataframe(
                        home_box[display_cols].style.format(
                            {col: '{:.1f}' if col == 'MIN' else '{:.0f}' for col in display_cols if col != 'Player'}
                        ),
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No players in box score")
            
            with tab_away:
                away_box = simulator.get_away_team_stats()
                if not away_box.empty:
                    # Format for display
                    display_cols = ['Player', 'PTS', 'REB', 'AST', '3PM', 'STL', 'BLK', 'TO', 'MIN', 'FGM', 'FGA', 'FTM', 'FTA']
                    display_cols = [c for c in display_cols if c in away_box.columns]
                    
                    st.dataframe(
                        away_box[display_cols].style.format(
                            {col: '{:.1f}' if col == 'MIN' else '{:.0f}' for col in display_cols if col != 'Player'}
                        ),
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No players in box score")
            
            # ========== GAME STATISTICS ==========
            st.write("---")
            st.subheader("📈 Game Statistics")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"### {home_team_sim}")
                home_fgm = sum([p['FGM'] for p in simulator.box_score['home'].values()])
                home_fga = sum([p['FGA'] for p in simulator.box_score['home'].values()])
                home_ftm = sum([p['FTM'] for p in simulator.box_score['home'].values()])
                home_fta = sum([p['FTA'] for p in simulator.box_score['home'].values()])
                home_reb = sum([p['REB'] for p in simulator.box_score['home'].values()])
                home_ast = sum([p['AST'] for p in simulator.box_score['home'].values()])
                home_to = sum([p['TO'] for p in simulator.box_score['home'].values()])
                home_3pm = sum([p['3PM'] for p in simulator.box_score['home'].values()])
                
                c1, c2 = st.columns(2)
                c1.metric("FG", f"{home_fgm}-{home_fga}")
                c2.metric("FT", f"{home_ftm}-{home_fta}")
                c1.metric("3-Pointers", f"{home_3pm}")
                c2.metric("Rebounds", f"{home_reb}")
                c1.metric("Assists", f"{home_ast}")
                c2.metric("Turnovers", f"{home_to}")
            
            with col2:
                st.markdown(f"### {away_team_sim}")
                away_fgm = sum([p['FGM'] for p in simulator.box_score['away'].values()])
                away_fga = sum([p['FGA'] for p in simulator.box_score['away'].values()])
                away_ftm = sum([p['FTM'] for p in simulator.box_score['away'].values()])
                away_fta = sum([p['FTA'] for p in simulator.box_score['away'].values()])
                away_reb = sum([p['REB'] for p in simulator.box_score['away'].values()])
                away_ast = sum([p['AST'] for p in simulator.box_score['away'].values()])
                away_to = sum([p['TO'] for p in simulator.box_score['away'].values()])
                away_3pm = sum([p['3PM'] for p in simulator.box_score['away'].values()])
                
                c1, c2 = st.columns(2)
                c1.metric("FG", f"{away_fgm}-{away_fga}")
                c2.metric("FT", f"{away_ftm}-{away_fta}")
                c1.metric("3-Pointers", f"{away_3pm}")
                c2.metric("Rebounds", f"{away_reb}")
                c1.metric("Assists", f"{away_ast}")
                c2.metric("Turnovers", f"{away_to}")
            
            # ========== RESET BUTTON ==========
            st.write("---")
            if st.button("🔄 Run Another Simulation", key="run_another_sim"):
                st.session_state.simulation_running = False
                st.rerun()
        
        else:
            st.error(f"❌ Could not load player data for simulation.")
            st.info(f"Home roster: {len(home_roster_for_sim)} players | Away roster: {len(away_roster_for_sim)} players")

            

with tab5:                    
                    st.write("---")
                    st.subheader("📈 Prediction History & Performance")
                    
                    tab1, tab2, tab3 = st.tabs(["Recent Predictions", "Model Performance", "Track Results"])
                    
                    # TAB 1: Recent Predictions
                    with tab1:
                        st.markdown("**Last 10 Predictions for All Players**")
                        history = pred.initialize_prediction_history()
                        if not history.empty:
                            recent = history.tail(10)
                            st.dataframe(
                                recent[['Date', 'Player', 'Team', 'Stat', 'Prediction', 'Actual', 'Error']],
                                hide_index=True,
                                use_container_width=True
                            )
                        else:
                            st.info("No prediction history yet. Make some predictions to start tracking!")
                    
                    # TAB 2: Model Performance
                    with tab2:
                        st.markdown("**Overall Model Performance**")
                        performance = pred.get_model_performance_report()
                        
                        if performance['total_predictions_made'] > 0:
                            col1, col2, col3, col4 = st.columns(4)
                            
                            col1.metric(
                                "Total Predictions",
                                performance['total_predictions_made'],
                                help="Total number of predictions made"
                            )
                            col2.metric(
                                "With Results",
                                performance['predictions_with_results'],
                                help="Predictions where actual results are recorded"
                            )
                            col3.metric(
                                "Overall MAE",
                                f"±{performance['overall_mae']}",
                                help="Average prediction error across all stats"
                            )
                            col4.metric(
                                "Trend",
                                performance['improvement_trend'],
                                help="Is accuracy improving or stable?"
                            )
                            
                            # Accuracy by stat type
                            if performance['by_stat']:
                                st.markdown("**Accuracy by Stat Type:**")
                                stat_accuracy = []
                                for stat, metrics in performance['by_stat'].items():
                                    stat_accuracy.append({
                                        'Stat': stat,
                                        'MAE': f"±{metrics['mae']:.2f}",
                                        'Predictions': metrics['count'],
                                        'Best': f"{metrics['best']:.1f}",
                                        'Worst': f"{metrics['worst']:.1f}"
                                    })
                                st.dataframe(
                                    pd.DataFrame(stat_accuracy),
                                    hide_index=True,
                                    use_container_width=True
                                )
                        else:
                            st.info("No performance data available yet.")
                    
                    # TAB 3: Track Results
                    with tab3:
                        st.markdown("**Update Predictions with Actual Results**")
                        st.info("ℹ️ Use this section to record actual game results and track prediction accuracy")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            update_player = st.text_input(
                                "Player Name",
                                key="track_player",
                                placeholder="e.g., LeBron James"
                            )
                        
                        with col2:
                            update_stat = st.selectbox(
                                "Stat",
                                ["PTS", "AST", "REB", "3PM"],
                                key="track_stat"
                            )
                        
                        col3, col4 = st.columns(2)
                        
                        with col3:
                            actual_result = st.number_input(
                                "Actual Result",
                                min_value=0.0,
                                step=0.1,
                                key="track_result"
                            )
                        
                        with col4:
                            if st.button("Record Result", key="record_button"):
                                if update_player and update_stat and actual_result >= 0:
                                    # Find the most recent prediction for this player and stat
                                    pred_history = pred.initialize_prediction_history()
                                    matching = pred_history[
                                        (pred_history['Player'] == update_player) &
                                        (pred_history['Stat'] == update_stat)
                                    ]
                                    
                                    if not matching.empty:
                                        last_pred = matching.iloc[-1]['Prediction']
                                        last_team = matching.iloc[-1]['Team']
                                        error = abs(actual_result - last_pred)
                                        
                                        # Update prediction history with actual result
                                        pred_history.loc[
                                            (pred_history['Player'] == update_player) &
                                            (pred_history['Stat'] == update_stat) &
                                            (pred_history['Actual'].isna()),
                                            ['Actual', 'Error']
                                        ] = [actual_result, error]
                                        
                                        pred_history.to_csv('prediction_history.csv', index=False)
                                        
                                        st.success(
                                            f"✅ Result recorded!\n"
                                            f"Prediction: {last_pred:.1f} | Actual: {actual_result:.1f} | Error: ±{error:.1f}"
                                        )
                                        
                                        # 🚀 ACTIVATE LEARNING LOOP: Trigger model retraining if error is large
                                        with st.spinner(f"🤖 Analyzing prediction error and optimizing model..."):
                                            try:
                                                # Get team ID for fetching player stats
                                                team_id = all_team_ids.get(last_team, {}).get("id")
                                                
                                                if team_id:
                                                    # Fetch recent games and player stats
                                                    recent_game_ids, _ = ps.fetch_recent_games_for_team(team_id)
                                                    
                                                    if recent_game_ids:
                                                        # Extract player stats from boxscores
                                                        boxscore_player_ids = []
                                                        player_stats = []
                                                        
                                                        for game_id in recent_game_ids:
                                                            try:
                                                                boxscore = requests.get(
                                                                    f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={game_id}",
                                                                    timeout=10
                                                                ).json()
                                                                
                                                                if 'boxscore' in boxscore:
                                                                    teams_box = boxscore['boxscore'].get('teams', [])
                                                                    for team in teams_box:
                                                                        for athlete in team.get('athletes', []):
                                                                            if athlete['athlete']['displayName'] == update_player:
                                                                                stat_row = {
                                                                                    'Date': boxscore.get('date', ''),
                                                                                    'PTS': float(athlete.get('stats', [])[0].get('displayValue', 0)) if athlete.get('stats') else 0,
                                                                                    'REB': float(athlete.get('stats', [])[2].get('displayValue', 0)) if len(athlete.get('stats', [])) > 2 else 0,
                                                                                    'AST': float(athlete.get('stats', [])[1].get('displayValue', 0)) if len(athlete.get('stats', [])) > 1 else 0,
                                                                                    'OPP': team.get('opponent', {}).get('displayName', 'Unknown')
                                                                                }
                                                                                player_stats.append(stat_row)
                                                            except Exception as e:
                                                                continue
                                                        
                                                        if player_stats:
                                                            stats_df = pd.DataFrame(player_stats)
                                                            
                                                            # Engineer features
                                                            stats_df_eng = pred.engineer_features(stats_df, name=update_player)
                                                            
                                                            if stats_df_eng is not None:
                                                                # Build current model to get MAE baseline
                                                                model_result = pred.build_prediction_models(stats_df_eng, stat=update_stat)
                                                                
                                                                if model_result and len(model_result) >= 2:
                                                                    model, mae = model_result[0], model_result[1]
                                                                    
                                                                    # Trigger adaptive learning
                                                                    updated_model, learning_msg = pred.adaptive_model_training(
                                                                        stats_df_eng,
                                                                        actual_result,
                                                                        last_pred,
                                                                        model,
                                                                        mae,
                                                                        stat=update_stat
                                                                    )
                                                                    
                                                                    if learning_msg:
                                                                        st.info(f"🧠 {learning_msg}")
                                                                        st.info(f"💡 Model is now smarter! Future predictions for {update_player} will be more accurate.")
                                                            
                                            except Exception as e:
                                                st.warning(f"⚠️ Could not trigger learning loop: {str(e)}")
                                    else:
                                        st.warning(f"No recent predictions found for {update_player} - {update_stat}")
                                else:
                                    st.error("Please fill in all fields")
 
