"""
NBA PLAYER STATS PREDICTION MODULE
===================================
Fetches player stats from ESPN API and predicts future performance
Uses: GradientBoosting ML models for accurate predictions
"""

import pandas as pd
import numpy as np
import requests
from sklearn.ensemble import GradientBoostingRegressor, VotingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, r2_score
import warnings
import os
from datetime import datetime
warnings.filterwarnings('ignore')


def fetch_player_stats_from_espn(player_id, team_id, max_games=20):
    """
    Fetch recent game stats from ESPN API
    Returns: DataFrame with player stats
    """
    try:
        # ESPN API endpoint for player stats
        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/roster"

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # Extract player info and stats
        player_stats = []

        if 'athletes' in data:
            for athlete in data['athletes']:
                if str(athlete.get('id')) == str(player_id):
                    # Get recent stats
                    if 'stats' in athlete:
                        for stat_group in athlete.get('stats', []):
                            if 'displayName' in stat_group:
                                player_stats.append(stat_group)

        return player_stats

    except Exception as e:
        print(f"Error fetching from ESPN: {e}")
        return []


def fetch_player_game_logs_espn(player_name, team_name, max_games=20):
    """
    Fetch player game logs from ESPN (alternative approach)
    Uses player name and team to find stats
    """
    try:
        # Try ESPN stats page scraping approach
        team_abbr = {
            'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BRK',
            'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
            'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
            'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'LA Clippers': 'LAC',
            'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM', 'Miami Heat': 'MIA',
            'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN', 'New Orleans Pelicans': 'NOP',
            'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC', 'Orlando Magic': 'ORL',
            'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX', 'Portland Trail Blazers': 'POR',
            'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS', 'Toronto Raptors': 'TOR',
            'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
        }.get(team_name, team_name[:3].upper())

        # Basketball Reference approach (alternative)
        player_slug = player_name.lower().replace(' ', '-')

        # Return stub for now - in production would scrape
        return None

    except Exception as e:
        print(f"Error fetching game logs: {e}")
        return None


def calculate_team_defensive_profile(team_id, game_ids):
    """
    Calculates defensive metrics for a team (avg points, assists, rebounds allowed)
    based on recent game IDs.
    """
    if not game_ids:
        # Fallback to league averages if no game data
        return {
            'avg_pts_allowed': 112.0,
            'avg_ast_allowed': 26.0,
            'avg_reb_allowed': 44.0
        }
    
    pts_allowed_list = []
    ast_allowed_list = []
    reb_allowed_list = []

    # Use a set to store processed game IDs to avoid redundant API calls if game_ids has duplicates
    processed_game_ids = set()

    # Limit to last 5 games for efficiency, as in the original code
    for gid in game_ids[:5]:
        if gid in processed_game_ids:
            continue
        processed_game_ids.add(gid)

        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={gid}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                boxscore = data.get('boxscore', {})
                
                # The 'players' key in boxscore contains team entries, each with 'statistics'
                teams_data = boxscore.get('players', [])
                if not teams_data:
                    # Fallback if 'players' is not present or empty
                    teams_data = boxscore.get('teams', [])
                
                for team_entry in teams_data:
                    if not isinstance(team_entry, dict):
                        continue
                    
                    current_team_id = str(team_entry.get('team', {}).get('id'))
                    
                    # If this is NOT the team we're profiling, their stats are what our team ALLOWED
                    if current_team_id != str(team_id):
                        statistics = team_entry.get('statistics', [])
                        for stat_group in statistics:
                            # Check if this stat_group contains team-level statistics
                            if 'team' in stat_group and stat_group['team'] and 'stats' in stat_group['team']:
                                stat_names = stat_group.get('names', [])
                                stats_values = stat_group['team']['stats']
                                
                                # Create a dictionary for easy lookup
                                stat_dict = dict(zip(stat_names, stats_values))
                                
                                # Extract points, assists, rebounds
                                pts_allowed_list.append(pd.to_numeric(stat_dict.get('points', 0), errors='coerce'))
                                ast_allowed_list.append(pd.to_numeric(stat_dict.get('assists', 0), errors='coerce'))
                                reb_allowed_list.append(pd.to_numeric(stat_dict.get('rebounds', 0), errors='coerce'))
                                break # Found team stats for this opponent, move to next game
            
        except Exception as e:
            # print(f"Error fetching defensive profile for game {gid}: {e}") # Uncomment for debugging
            continue
    
    # Filter out NaNs and calculate averages
    pts_allowed_list = [x for x in pts_allowed_list if pd.notna(x)]
    ast_allowed_list = [x for x in ast_allowed_list if pd.notna(x)]
    reb_allowed_list = [x for x in reb_allowed_list if pd.notna(x)]

    return {
        'avg_pts_allowed': np.mean(pts_allowed_list) if pts_allowed_list else 112.0,
        'avg_ast_allowed': np.mean(ast_allowed_list) if ast_allowed_list else 26.0,
        'avg_reb_allowed': np.mean(reb_allowed_list) if reb_allowed_list else 44.0
    }


def engineer_features(df, name="Dataset", opp_def_stats=None):
    """Create comprehensive features from raw stats"""
    if df is None or df.empty:
        return None

    df = df.copy()

    # Ensure 'Date' column is datetime and sort for time-series features
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.sort_values('Date').reset_index(drop=True)
    else:
        # If no Date column, cannot calculate time-series features like rest days
        pass # Or raise an error/warning

    # STEP 1: Clean string data - handle formats like '10-22' (take first number)
    for col in df.columns:
        if col not in ['Date', 'OPP', 'Opponent']:
            df[col] = df[col].astype(str).apply(
                lambda x: x.split('-')[0].strip() if '-' in str(x) else x
            )

    # STEP 2: Ensure we have numeric columns
    numeric_cols = ['PTS', 'AST', 'REB', '3PM', 'FGM', 'FGA', 'FTM', 'FTA', '3PA', 'MIN', 'TO', 'STL']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 1. ROLLING AVERAGES (Recent Form)
    for window in [3, 5, 10]:
        if 'PTS' in df.columns:
            df[f'pts_avg_{window}'] = df['PTS'].rolling(window=window, min_periods=1).mean()
        if 'AST' in df.columns:
            df[f'ast_avg_{window}'] = df['AST'].rolling(window=window, min_periods=1).mean()
        if 'REB' in df.columns:
            df[f'reb_avg_{window}'] = df['REB'].rolling(window=window, min_periods=1).mean()
        if '3PM' in df.columns:
            df[f'3pm_avg_{window}'] = df['3PM'].rolling(window=window, min_periods=1).mean()

    # 1b. EXPONENTIAL WEIGHTED AVERAGES (More weight to recent games)
    for span in [3, 5]:
        for col in ['PTS', 'AST', 'REB', '3PM']:
            if col in df.columns:
                df[f'{col.lower()}_ewa_{span}'] = df[col].ewm(span=span, adjust=False).mean()

    # 2. EFFICIENCY METRICS
    if 'FGM' in df.columns and 'FGA' in df.columns:
        df['FG%'] = df['FGM'] / df['FGA'].replace(0, 1)
    if '3PA' in df.columns:
        df['3P_Attempt_Rate'] = df['3PA'] / df['FGA'].replace(0, 1)
    if 'FTM' in df.columns and 'FTA' in df.columns:
        df['FT%'] = df['FTM'] / df['FTA'].replace(0, 1)

    # True Shooting %
    if 'PTS' in df.columns and 'FGA' in df.columns and 'FTA' in df.columns:
        df['TS%'] = df['PTS'] / (2 * (df['FGA'] + 0.44 * df['FTA'])).replace(0, 1)

    # 2b. OPPONENT DEFENSIVE CONTEXT
    if opp_def_stats:
        df['Opp_Def_Points'] = df['OPP'].apply(lambda x: opp_def_stats.get(x, {}).get('avg_pts_allowed', 112.0))
        df['Opp_Def_Assists'] = df['OPP'].apply(lambda x: opp_def_stats.get(x, {}).get('avg_ast_allowed', 26.0))
        df['Opp_Def_Rebounds'] = df['OPP'].apply(lambda x: opp_def_stats.get(x, {}).get('avg_reb_allowed', 44.0))
    else:
        # Default baseline values if no data provided
        df['Opp_Def_Points'] = 112.0
        df['Opp_Def_Assists'] = 26.0
        df['Opp_Def_Rebounds'] = 44.0

    # 3. VOLUME METRICS
    if 'FGA' in df.columns:
        df['Shot_Volume'] = df['FGA']
    if 'FGA' in df.columns and 'FTA' in df.columns and 'TO' in df.columns:
        df['Usage_Rate'] = (df['FGA'] + df['FTA'] + df['TO']) / (df['FGA'] + df['FTA']).replace(0, 1)

    # 4. GAME CONTEXT
    if 'MIN' in df.columns:
        if df['MIN'].max() > df['MIN'].min():
            df['Minutes_Scaled'] = (df['MIN'] - df['MIN'].min()) / (df['MIN'].max() - df['MIN'].min() + 0.1)
    if 'OPP' in df.columns:
        df['Is_Home'] = (~df['OPP'].astype(str).str.startswith('@')).astype(int)

    # Days of Rest and Back-to-Back
    if 'Date' in df.columns and not df['Date'].isnull().all():
        df['Days_Rest'] = df['Date'].diff().dt.days.fillna(0).astype(int)
        df['Back_to_Back'] = (df['Days_Rest'] <= 1).astype(int)
    else:
        df['Days_Rest'] = 0
        df['Back_to_Back'] = 0

    # 5. MOMENTUM INDICATORS
    if 'PTS' in df.columns:
        df['PTS_Trend'] = df['PTS'].diff().fillna(0)
        df['PTS_Volatility'] = df['PTS'].rolling(window=5, min_periods=2).std().fillna(0)
        if 'pts_avg_5' in df.columns and 'pts_avg_10' in df.columns:
            df['Form_Score'] = (df['pts_avg_5'] - df['pts_avg_10']).fillna(0)

    # Fill NaN from rolling calculations
    df = df.ffill().bfill()
    df = df.fillna(0)

    return df


def get_available_features(df):
    """Get list of features available for modeling"""
    feature_cols = [
        'pts_avg_3', 'pts_avg_5', 'pts_avg_10',
        'pts_ewa_3', 'ast_ewa_3', 'reb_ewa_3', '3pm_ewa_3',
        'ast_avg_3', 'ast_avg_5',
        'reb_avg_3', 'reb_avg_5',
        '3pm_avg_3', '3pm_avg_5',
        'FG%', 'TS%', '3P_Attempt_Rate',
        'Shot_Volume', 'Usage_Rate',
        'Minutes_Scaled', 'Is_Home',
        'PTS_Trend', 'Form_Score', 'PTS_Volatility',
        'Opp_Def_Points', 'Opp_Def_Assists', 'Opp_Def_Rebounds',
        'Days_Rest', 'Back_to_Back'
        # Note: Injury status is not directly available from current ESPN API game logs.
    ]

    # Return only features that exist in the dataframe
    return [f for f in feature_cols if f in df.columns]


def build_prediction_models(df, stat='PTS'):
    """
    Build ML models for a specific stat prediction
    Returns: model, MAE, R², predictions
    """
    # FIX: Lowered minimum from 5 to 3 games to match app.py requirement
    if df is None or df.empty or len(df) < 3:
        return None, None, None, None

    feature_cols = get_available_features(df)

    if not feature_cols or stat not in df.columns:
        return None, None, None, None

    # FIX: Limit features for small datasets to prevent overfitting
    max_features = max(3, len(df) - 1)
    if len(feature_cols) > max_features:
        # Prioritize most predictive features
        priority_features = []
        for f in ['pts_avg_3', 'ast_avg_3', 'reb_avg_3', '3pm_avg_3',
                    'pts_ewa_3', 'ast_ewa_3', 'reb_ewa_3', '3pm_ewa_3',
                    'pts_avg_5', 'ast_avg_5', 'reb_avg_5', '3pm_avg_5',
                    'Minutes_Scaled', 'Is_Home', 'PTS_Trend', 'Form_Score', 'PTS_Volatility',
                    'Opp_Def_Points', 'Opp_Def_Assists']:
            if f in feature_cols:
                priority_features.append(f)

        remaining = [f for f in feature_cols if f not in priority_features]
        feature_cols = priority_features + remaining
        feature_cols = feature_cols[:max_features]

    # Prepare data
    try:
        df_clean = df[feature_cols + [stat]].dropna()

        # Remove any remaining non-numeric values
        for col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')

        df_clean = df_clean.dropna()

        if len(df_clean) < 3:
            return None, None, None, None

        X = df_clean[feature_cols]
        y = df_clean[stat]

        # Remove any infinite values
        X = X.replace([np.inf, -np.inf], np.nan).dropna()
        y = y[X.index]

        if len(X) < 3 or len(y) < 3:
            return None, None, None, None

        # FIX: Better train-test split for small datasets
        if len(X) >= 5:
            train_size = max(2, int(0.7 * len(X)))
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]
        else:
            # For 3-4 games: use all but 1 for training
            train_size = max(2, len(X) - 1)
            X_train, X_test = X[:train_size], X[train_size:]
            y_train, y_test = y[:train_size], y[train_size:]

        if len(X_test) == 0 or len(y_test) == 0:
            # Use all data for training if too few
            X_train, X_test = X, X
            y_train, y_test = y, y

        # FIX: Adjust model complexity based on dataset size
        n_estimators = min(50, max(10, len(X_train) * 5))
        max_depth = min(3, max(1, len(X_train) // 2))

        # Build Ensemble Model: Linear (Ridge) + Non-Linear (GB)
        # Ridge provides stability for small samples, GB captures form patterns
        gb = GradientBoostingRegressor(
            n_estimators=n_estimators,
            learning_rate=0.1,
            max_depth=max_depth,
            random_state=42,
            subsample=min(0.8, max(0.5, len(X_train) / len(X)))
        )
        
        ridge = Ridge(alpha=10.0) # High alpha for stability on tiny datasets
        
        ensemble = VotingRegressor(
            estimators=[('gb', gb), ('ridge', ridge)],
            weights=[0.4, 0.6] if len(X) < 8 else [0.6, 0.4]
        )

        model = Pipeline([
            ('scaler', RobustScaler()),
            ('regressor', ensemble)
        ])

        model.fit(X_train, y_train)
        predictions = model.predict(X_test)

        # CRITICAL FIX: Store exact features used so prediction uses same columns
        model._used_features = feature_cols

        # Evaluate
        mae = mean_absolute_error(y_test, predictions)
        r2 = r2_score(y_test, predictions)

        return model, mae, r2, predictions

    except Exception as e:
        print(f"Error building model: {e}")
        return None, None, None, None


def predict_next_game(model, df, next_opp_stats=None):
    """
    Predict stat for next game based on last game features
    Returns: prediction value
    """
    if model is None or df is None or df.empty:
        return None

    # CRITICAL FIX: Use exact features the model was trained on
    feature_cols = getattr(model, '_used_features', None)
    if feature_cols is None:
        feature_cols = get_available_features(df)

    if not feature_cols:
        return None

    try:
        next_features = df[feature_cols].iloc[-1:].copy()
        
        # Inject the upcoming opponent's defensive context into the prediction set
        if next_opp_stats:
            if 'Opp_Def_Points' in next_features.columns:
                next_features['Opp_Def_Points'] = next_opp_stats.get('avg_pts_allowed', 112.0)
            if 'Opp_Def_Assists' in next_features.columns:
                next_features['Opp_Def_Assists'] = next_opp_stats.get('avg_ast_allowed', 26.0)
            if 'Opp_Def_Rebounds' in next_features.columns:
                next_features['Opp_Def_Rebounds'] = next_opp_stats.get('avg_reb_allowed', 44.0)

        # For Days_Rest and Back_to_Back for the *next* game, we assume 1 day rest and not back-to-back
        # This is a simplification. A more advanced approach would involve knowing the actual schedule.
        if 'Days_Rest' in next_features.columns:
            next_features['Days_Rest'] = 1
        if 'Back_to_Back' in next_features.columns:
            next_features['Back_to_Back'] = 0

        prediction = model.predict(next_features.values)[0]
        return prediction
    except Exception as e:
        print(f"Error making prediction: {e}")
        return None


def get_feature_importance(model, df):
    """Get feature importance from trained model"""
    if model is None or df is None or df.empty:
        return None

    # CRITICAL FIX: Use exact features the model was trained on
    feature_cols = getattr(model, '_used_features', None)
    if feature_cols is None:
        feature_cols = get_available_features(df)

    if not feature_cols:
        return None

    try:
        # Support Pipeline and VotingRegressor
        regressor = model
        if hasattr(model, 'named_steps'):
            regressor = model.named_steps['regressor']
            
        if hasattr(regressor, 'named_estimators_'):
            # Use the GB model for importance as Ridge importance (coeffs) scale differently
            gb_model = regressor.named_estimators_.get('gb')
            importances = gb_model.feature_importances_ if gb_model else None
        else:
            importances = getattr(regressor, 'feature_importances_', None)
            
        if importances is None:
            return None

        importance_df = pd.DataFrame({
            'Feature': feature_cols,
            'Importance': importances
        }).sort_values('Importance', ascending=False)

        return importance_df
    except Exception as e:
        print(f"Error getting feature importance: {e}")
        return None


def calculate_stats_summary(df, games=10):
    """Calculate summary stats for last N games"""
    if df is None or df.empty:
        return None

    stats_to_track = ['PTS', 'AST', 'REB', '3PM', 'FG%', 'TS%', 'MIN']

    summary = {}

    for stat in stats_to_track:
        if stat in df.columns:
            try:
                numeric_vals = pd.to_numeric(df[stat], errors='coerce')
                last_games = numeric_vals.tail(games)

                if not last_games.empty:
                    summary[stat] = {
                        'avg': last_games.mean(),
                        'min': last_games.min(),
                        'max': last_games.max(),
                        'std': last_games.std()
                    }
            except:
                pass

    return summary if summary else None


def format_prediction_output(stat, prediction, actual_last, avg_last_5):
    """Format prediction for display"""
    if prediction is None:
        return None

    output = {
        'stat': stat,
        'prediction': round(prediction, 1),
        'actual_last': round(actual_last, 1) if actual_last else None,
        'avg_last_5': round(avg_last_5, 1) if avg_last_5 else None,
        'range_low': round(prediction - 2, 1),
        'range_high': round(prediction + 2, 1)
    }

    return output


def adaptive_model_training(stats_df, actual_result, previous_prediction, model, model_mae, stat='PTS'):
    """
    Model learns from its mistakes by retraining when prediction error is large
    
    Args:
        stats_df: DataFrame with player stats (training data)
        actual_result: Actual stat value from the game
        previous_prediction: Previous model prediction
        model: Trained model object
        model_mae: Model's Mean Absolute Error threshold
        stat: Stat being predicted (default 'PTS')
    
    Returns:
        Updated model after retraining if error threshold exceeded
    """
    if model is None or stats_df is None or stats_df.empty:
        return model, None
    
    try:
        # Calculate prediction error
        actual_result = pd.to_numeric(actual_result, errors='coerce')
        previous_prediction = pd.to_numeric(previous_prediction, errors='coerce')
        
        if pd.isna(actual_result) or pd.isna(previous_prediction):
            return model, None
        
        error = abs(actual_result - previous_prediction)
        error_threshold = model_mae * 1.5 if model_mae else 5.0
        
        # If error is large, retrain with new data
        if error > error_threshold:
            
            # Build new improved model with existing data
            retrained_model, new_mae, new_r2, _ = build_prediction_models(stats_df, stat=stat)
            
            if retrained_model is not None:
                improvement_msg = f"✅ Model adapted to new data! Previous error: {error:.1f}, New MAE: {new_mae:.1f}"
                return retrained_model, improvement_msg
        
        return model, None
        
    except Exception as e:
        print(f"Error in adaptive training: {e}")
        return model, None


def initialize_prediction_history(filepath='prediction_history.csv'):
    """Initialize or load prediction history from CSV"""
    try:
        if os.path.exists(filepath):
            history = pd.read_csv(filepath)
            # Ensure necessary columns exist
            required_cols = ['Date', 'Player', 'Team', 'Stat', 'Prediction', 'Actual', 'Error']
            for col in required_cols:
                if col not in history.columns:
                    history[col] = None
            return history
        else:
            # Create new history dataframe
            return pd.DataFrame(columns=['Date', 'Player', 'Team', 'Stat', 'Prediction', 'Actual', 'Error'])
    except Exception as e:
        print(f"Error loading prediction history: {e}")
        return pd.DataFrame(columns=['Date', 'Player', 'Team', 'Stat', 'Prediction', 'Actual', 'Error'])


def record_prediction(player_name, team_name, stat, prediction, actual=None, filepath='prediction_history.csv'):
    """
    Record a prediction and optionally its actual result for tracking
    
    Args:
        player_name: Name of the player
        team_name: Name of the team
        stat: Stat being predicted (PTS, AST, REB, etc.)
        prediction: Predicted value
        actual: Actual result (can be added later)
        filepath: Path to prediction history CSV
    """
    try:
        history = initialize_prediction_history(filepath)
        
        error = None
        if actual is not None:
            actual = pd.to_numeric(actual, errors='coerce')
            if not pd.isna(actual):
                error = abs(actual - prediction)
        
        new_record = pd.DataFrame({
            'Date': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
            'Player': [player_name],
            'Team': [team_name],
            'Stat': [stat],
            'Prediction': [round(prediction, 1)],
            'Actual': [round(actual, 1) if actual is not None else None],
            'Error': [round(error, 1) if error is not None else None]
        })
        
        history = pd.concat([history, new_record], ignore_index=True)
        history.to_csv(filepath, index=False)
        
        return True
    except Exception as e:
        print(f"Error recording prediction: {e}")
        return False


def track_model_accuracy(filepath='prediction_history.csv', window=20):
    """
    Track model accuracy over time by calculating rolling metrics
    
    Args:
        filepath: Path to prediction history CSV
        window: Window size for rolling calculations
    
    Returns:
        Dictionary with accuracy metrics and rolling statistics
    """
    try:
        history = initialize_prediction_history(filepath)
        
        if history.empty or 'Error' not in history.columns:
            return {
                'total_predictions': 0,
                'total_with_results': 0,
                'mean_error': 0,
                'rolling_mae': pd.DataFrame(),
                'accuracy_by_stat': {}
            }
        
        # Calculate metrics for records with actual results
        history_with_actuals = history.dropna(subset=['Actual', 'Error'])
        
        if history_with_actuals.empty:
            return {
                'total_predictions': len(history),
                'total_with_results': 0,
                'mean_error': 0,
                'rolling_mae': pd.DataFrame(),
                'accuracy_by_stat': {}
            }
        
        # Calculate rolling MAE
        history_with_actuals = history_with_actuals.copy()
        history_with_actuals['Error'] = pd.to_numeric(history_with_actuals['Error'], errors='coerce')
        history_with_actuals['rolling_mae'] = history_with_actuals['Error'].rolling(
            window=min(window, len(history_with_actuals)), 
            min_periods=1
        ).mean()
        
        # Accuracy by stat type
        accuracy_by_stat = {}
        for stat in history['Stat'].unique():
            if pd.notna(stat):
                stat_errors = history_with_actuals[history_with_actuals['Stat'] == stat]['Error']
                if len(stat_errors) > 0:
                    accuracy_by_stat[stat] = {
                        'mae': stat_errors.mean(),
                        'count': len(stat_errors),
                        'best': stat_errors.min(),
                        'worst': stat_errors.max()
                    }
        
        return {
            'total_predictions': len(history),
            'total_with_results': len(history_with_actuals),
            'mean_error': history_with_actuals['Error'].mean() if len(history_with_actuals) > 0 else 0,
            'rolling_mae': history_with_actuals[['Date', 'rolling_mae']],
            'accuracy_by_stat': accuracy_by_stat,
            'recent_predictions': history.tail(10)
        }
        
    except Exception as e:
        print(f"Error tracking model accuracy: {e}")
        return {
            'total_predictions': 0,
            'total_with_results': 0,
            'mean_error': 0,
            'rolling_mae': pd.DataFrame(),
            'accuracy_by_stat': {}
        }


def get_model_performance_report(filepath='prediction_history.csv'):
    """
    Generate a comprehensive performance report for the model
    
    Returns:
        Dictionary with various performance metrics
    """
    accuracy_data = track_model_accuracy(filepath)
    
    report = {
        'total_predictions_made': accuracy_data['total_predictions'],
        'predictions_with_results': accuracy_data['total_with_results'],
        'overall_mae': round(accuracy_data['mean_error'], 2),
        'stats_tracked': list(accuracy_data['accuracy_by_stat'].keys()),
        'by_stat': accuracy_data['accuracy_by_stat'],
        'improvement_trend': "improving" if len(accuracy_data['rolling_mae']) > 5 and 
                            accuracy_data['rolling_mae'].iloc[-1]['rolling_mae'] < 
                            accuracy_data['rolling_mae'].iloc[-5]['rolling_mae'] else "stable"
    }
    
    return report