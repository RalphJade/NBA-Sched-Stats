"""
Advanced ML Module for NBA Player Prop Predictions
Features: XGBoost, Ensemble Methods, LSTM, Feature Engineering, Opponent Context
Now includes: PRA, PR, PA, RA, and 3-Pointers Made
"""

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')

from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import Ridge
from xgboost import XGBRegressor
from sklearn.metrics import mean_squared_error, r2_score
from datetime import datetime, timedelta
from scipy import stats
from typing import Dict, Tuple, List, Optional


# ============================================================================
# COMBO STATS HELPER
# ============================================================================

def compute_combo_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute combo stats and 3PM from raw boxscore data.
    Adds: PRA, Points+Rebounds, Points+Assists, Rebounds+Assists, 3PM
    """
    df = df.copy()
    
    # Ensure base columns are numeric
    base_cols = ['Points', 'Rebounds', 'Assists', 'Steals', 'Blocks']
    for col in base_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Compute combo stats
    if all(c in df.columns for c in ['Points', 'Rebounds', 'Assists']):
        df['PRA'] = df['Points'] + df['Rebounds'] + df['Assists']
    
    if all(c in df.columns for c in ['Points', 'Rebounds']):
        df['Points+Rebounds'] = df['Points'] + df['Rebounds']
    
    if all(c in df.columns for c in ['Points', 'Assists']):
        df['Points+Assists'] = df['Points'] + df['Assists']
    
    if all(c in df.columns for c in ['Rebounds', 'Assists']):
        df['Rebounds+Assists'] = df['Rebounds'] + df['Assists']
    
    # 3-Pointers Made — try common naming conventions
    three_point_cols = ['3PM', '3P', '3P Made', 'FG3M', 'Three Pointers Made', '3PT Made']
    for col in three_point_cols:
        if col in df.columns:
            df['3PM'] = pd.to_numeric(df[col], errors='coerce')
            break
    
    return df


# ============================================================================
# UI HELPER
# ============================================================================

def style_recommendation(rec: pd.Series) -> str:
    """Format a single recommendation card"""
    prob = float(rec['Probability'].rstrip('%'))
    color = '🟢' if rec['Type'] == 'OVER' else '🔴'
    
    if prob >= 80:
        confidence_emoji = '🔥'
    elif prob >= 70:
        confidence_emoji = '⭐'
    else:
        confidence_emoji = '✓'
    
    return f"""{color} **{rec['Prop Line']}**
    
**Probability:** {rec['Probability']} {confidence_emoji}  
**Hit Rate:** {rec['Hit Rate %']:.0f}% | **Games:** {rec['Games Hit']}  
**Trend:** {rec['Trend']} | **Confidence:** {rec['Confidence']}  
**ML Prediction:** {rec['ML Prediction']} (Range: {rec['Pred Range']})"""


# ============================================================================
# OPPONENT STRENGTH MODULE
# ============================================================================

class OpponentStrengthAnalyzer:
    """Analyzes defensive strength of opponents and adjusts predictions"""
    
    def __init__(self):
        self.opponent_stats = {}
    
    def calculate_defensive_ratings(self, games_df: pd.DataFrame) -> Dict:
        """
        Calculate defensive efficiency ratings for each team.
        Lower score = stronger defense (allows fewer points)
        """
        if games_df.empty:
            return {}
        
        defensive_stats = {}
        
        for team in games_df['Opponent'].unique():
            team_games = games_df[games_df['Opponent'] == team]
            
            if len(team_games) > 0:
                avg_points_allowed = team_games['Points'].mean()
                avg_rebounds_allowed = team_games.get('Rebounds', pd.Series()).mean() if 'Rebounds' in team_games.columns else 0
                avg_assists_allowed = team_games.get('Assists', pd.Series()).mean() if 'Assists' in team_games.columns else 0
                
                # Defensive rating: lower = stronger defense
                defensive_stats[team] = {
                    'avg_points_allowed': avg_points_allowed,
                    'avg_rebounds_allowed': avg_rebounds_allowed,
                    'avg_assists_allowed': avg_assists_allowed,
                    'games_vs': len(team_games)
                }
        
        return defensive_stats
    
    def get_opponent_adjustment(self, opponent: str, stat_type: str, 
                                league_avg: float, defensive_stats: Dict) -> float:
        """
        Return adjustment multiplier based on opponent strength.
        > 1.0 = play easier opponent, expect higher stats
        < 1.0 = play stronger opponent, expect lower stats
        """
        if opponent not in defensive_stats:
            return 1.0
        
        opp_data = defensive_stats[opponent]
        
        stat_map = {
            'Points': 'avg_points_allowed',
            'Rebounds': 'avg_rebounds_allowed',
            'Assists': 'avg_assists_allowed'
        }
        
        # Combo stats default to neutral (1.0) — could be extended with composite logic
        if stat_type not in stat_map:
            return 1.0
        
        opp_allowed = opp_data[stat_map[stat_type]]
        
        if league_avg > 0:
            adjustment = opp_allowed / league_avg
        else:
            adjustment = 1.0
        
        return np.clip(adjustment, 0.85, 1.15)  # Clip extreme adjustments


# ============================================================================
# FEATURE ENGINEERING MODULE
# ============================================================================

class AdvancedFeatureEngineer:
    """Creates advanced features from raw game stats"""
    
    @staticmethod
    def engineer_features(stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create advanced features from raw stats:
        - Time-weighted averages (recent games matter more)
        - Trend detection (trending up/down)
        - Consistency metrics (std dev, coefficient of variation)
        - Recency decay
        - Rolling statistics
        """
        df = stats_df.copy()
        
        if df.empty or len(df) < 3:
            return df
        
        # Ensure Date column exists and is sorted
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.sort_values('Date', ascending=True)
        
        # Time weights: recent games weighted higher
        n_games = len(df)
        time_weights = np.exp(np.linspace(-2, 0, n_games))  # Exponential decay
        time_weights = time_weights / time_weights.sum()
        
        stat_cols = ['Points', 'Rebounds', 'Assists', 'Steals', 'Blocks',
                     'PRA', 'Points+Rebounds', 'Points+Assists', 'Rebounds+Assists', '3PM']
        
        for stat in stat_cols:
            if stat not in df.columns:
                continue
            
            # Convert to numeric
            numeric_vals = pd.to_numeric(df[stat], errors='coerce')
            
            # 1. Time-weighted average (recent games matter more)
            df[f'{stat}_weighted_avg'] = (numeric_vals * time_weights).sum()
            
            # 2. Simple moving average (last 3 games)
            df[f'{stat}_ma3'] = numeric_vals.rolling(window=3, min_periods=1).mean()
            
            # 3. Trend (linear regression slope)
            if len(numeric_vals) >= 3:
                valid_idx = numeric_vals.dropna().index
                if len(valid_idx) >= 3:
                    x = np.arange(len(valid_idx))
                    y = numeric_vals[valid_idx].values
                    z = np.polyfit(x, y, 1)
                    trend = z[0]  # slope
                else:
                    trend = 0
            else:
                trend = 0
            df[f'{stat}_trend'] = trend
            
            # 4. Consistency (coefficient of variation)
            mean_val = numeric_vals.mean()
            std_val = numeric_vals.std()
            cv = (std_val / mean_val) if mean_val > 0 else 0
            df[f'{stat}_consistency'] = 1 - np.clip(cv, 0, 1)  # Higher = more consistent
            
            # 5. Volatility (std dev)
            df[f'{stat}_volatility'] = numeric_vals.std()
            
            # 6. Game-to-game momentum
            if len(numeric_vals) >= 2:
                momentum = numeric_vals.diff().sum() / (len(numeric_vals) - 1)
            else:
                momentum = 0
            df[f'{stat}_momentum'] = momentum
            
            # 7. Recent form (last 3 games average)
            recent_avg = numeric_vals.tail(3).mean()
            df[f'{stat}_recent_avg'] = recent_avg
            
            # 8. Performance vs personal average
            personal_avg = numeric_vals.mean()
            df[f'{stat}_vs_avg'] = numeric_vals - personal_avg if personal_avg > 0 else 0
        
        return df
    
    @staticmethod
    def create_game_context_features(stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        Add game context features:
        - Home/Away indicator
        - Days of rest
        - Back-to-back detection
        - Opponent strength proxy
        """
        df = stats_df.copy()
        
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.sort_values('Date')
            
            # Days of rest (gap between games)
            df['Days_Rest'] = df['Date'].diff().dt.days
            df['Days_Rest'] = df['Days_Rest'].fillna(1)
            
            # Back-to-back detection
            df['Back_to_Back'] = (df['Days_Rest'] <= 1).astype(int)
            
            # Game number in season (proxy for fatigue)
            df['Games_Played_Season'] = range(1, len(df) + 1)
        
        # Home/Away if we can infer from opponent
        if 'Opponent' in df.columns:
            df['Opponent_Count'] = df['Opponent'].value_counts().map(df['Opponent'])
            df['Familiar_Opponent'] = (df['Opponent_Count'] > 1).astype(int)
        
        return df


# ============================================================================
# ML MODEL ENSEMBLE
# ============================================================================

class PropPredictionEnsemble:
    """
    Ensemble of XGBoost, Random Forest, Gradient Boosting, and Ridge models
    for robust prop line predictions
    """
    
    def __init__(self):
        self.models = {
            'xgboost': XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                subsample=0.8,
                random_state=42,
                verbosity=0
            ),
            'rf': RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            ),
            'gb': GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            ),
            'ridge': Ridge(alpha=1.0)
        }
        self.scaler = RobustScaler()
        self.is_trained = False
    
    def prepare_training_data(self, stats_df: pd.DataFrame, 
                             stat_col: str) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Prepare X and y for training with engineered features
        """
        df = stats_df.copy()
        
        # Engineer features
        df = AdvancedFeatureEngineer.engineer_features(df)
        df = AdvancedFeatureEngineer.create_game_context_features(df)
        
        # Select feature columns
        feature_cols = [col for col in df.columns if (
            col.endswith(('_weighted_avg', '_ma3', '_trend', '_consistency', 
                         '_volatility', '_momentum', '_recent_avg', '_vs_avg')) or
            col in ['Days_Rest', 'Back_to_Back', 'Games_Played_Season', 'Familiar_Opponent']
        )]
        
        # Get target variable
        if stat_col not in df.columns:
            return None, None, feature_cols
        
        y = pd.to_numeric(df[stat_col], errors='coerce')
        
        # Build X from available features
        X = pd.DataFrame(index=df.index)
        for col in feature_cols:
            if col in df.columns:
                X[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Fill missing values
        X = X.fillna(X.mean())
        y = y.fillna(y.mean())
        
        # Remove any remaining NaNs
        valid_idx = ~(X.isna().any(axis=1) | y.isna())
        X = X[valid_idx]
        y = y[valid_idx]
        
        if len(X) < 4:
            return None, None, feature_cols
        
        return X.values, y.values, list(X.columns)
    
    def train(self, stats_df: pd.DataFrame, stat_col: str) -> bool:
        """
        Train all models in ensemble
        """
        X, y, feature_cols = self.prepare_training_data(stats_df, stat_col)
        
        if X is None or len(X) < 4:
            return False
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train each model
        for name, model in self.models.items():
            try:
                model.fit(X_scaled, y)
            except Exception as e:
                print(f"Warning: {name} training failed: {e}")
                continue
        
        self.is_trained = True
        self.feature_cols = feature_cols
        return True
    
    def predict(self, stats_df: pd.DataFrame) -> Dict[str, float]:
        """
        Get ensemble prediction (average of all models + confidence interval)
        Returns: mean prediction, std (uncertainty), low_bound, high_bound
        """
        if not self.is_trained:
            return None
        
        df = stats_df.copy()
        df = AdvancedFeatureEngineer.engineer_features(df)
        df = AdvancedFeatureEngineer.create_game_context_features(df)
        
        # Create feature vector (use last game as prediction context)
        X = pd.DataFrame(index=[0])
        for col in self.feature_cols:
            if col in df.columns:
                val = pd.to_numeric(df[col], errors='coerce').iloc[-1]
                X[col] = val
            else:
                X[col] = 0
        
        X = X.fillna(0)
        X_scaled = self.scaler.transform(X.values)
        
        # Get predictions from all models
        predictions = []
        for name, model in self.models.items():
            try:
                pred = model.predict(X_scaled)[0]
                predictions.append(pred)
            except:
                continue
        
        if not predictions:
            return None
        
        predictions = np.array(predictions)
        mean_pred = predictions.mean()
        std_pred = predictions.std()
        
        # Confidence interval (95%)
        low_bound = mean_pred - 1.96 * std_pred
        high_bound = mean_pred + 1.96 * std_pred
        
        return {
            'prediction': max(0, mean_pred),
            'std': std_pred,
            'lower_bound': max(0, low_bound),
            'upper_bound': high_bound,
            'model_agreement': 1 - (std_pred / mean_pred) if mean_pred > 0 else 0  # 0-1 score
        }


# ============================================================================
# ADVANCED PROP RECOMMENDATION ENGINE
# ============================================================================

class AdvancedPropRecommender:
    """
    ML-powered prop recommendation system combining:
    - XGBoost ensemble predictions
    - Opponent strength adjustments
    - Trend analysis
    - Probability calibration
    Now supports: PRA, PR, PA, RA, and 3-Pointers Made
    """
    
    def __init__(self):
        self.ensemble = {}  # One ensemble per stat
        self.opponent_analyzer = OpponentStrengthAnalyzer()
        self.feature_engineer = AdvancedFeatureEngineer()
    
    def calculate_advanced_recommendations(self, game_stats_df: pd.DataFrame,
                                          player_name: str,
                                          n_games: int = 10,
                                          tomorrow_opponent: Optional[str] = None) -> Tuple[pd.DataFrame, int]:
        """
        Calculate ML-enhanced prop recommendations with opponent context
        """
        if game_stats_df.empty:
            return None, 0
        
        df = game_stats_df.copy()
        
        # Compute combo stats and 3PM
        df = compute_combo_stats(df)
        
        # Sort by date (most recent first)
        if 'Date' in df.columns:
            try:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.sort_values('Date', ascending=False)
            except:
                pass
        
        # Take recent games
        recent_df = df.head(n_games).copy()
        recent_df = recent_df.sort_values('Date', ascending=True)  # Chronological for analysis
        actual_games = len(recent_df)
        
        if actual_games < 3:
            return None, 0
        
        # Opponent strength analysis
        defensive_stats = self.opponent_analyzer.calculate_defensive_ratings(recent_df)
        
        stat_mapping = {
            'Points': ('PTS', 'Points'),
            'Rebounds': ('REB', 'Rebounds'),
            'Assists': ('AST', 'Assists'),
            'Steals': ('STL', 'Steals'),
            'Blocks': ('BLK', 'Blocks'),
            'PRA': ('PRA', 'PRA'),
            'Points+Rebounds': ('PR', 'Points+Rebounds'),
            'Points+Assists': ('PA', 'Points+Assists'),
            'Rebounds+Assists': ('RA', 'Rebounds+Assists'),
            '3PM': ('3PM', '3-Pointers Made'),
        }
        
        recommendations = []
        
        for col_name, (stat_label, readable_name) in stat_mapping.items():
            if col_name not in recent_df.columns:
                continue
            
            numeric_vals = pd.to_numeric(recent_df[col_name], errors='coerce')
            numeric_vals = numeric_vals.dropna()
            
            if len(numeric_vals) < 3:
                continue
            
            # Train ensemble for this stat
            ensemble = PropPredictionEnsemble()
            ensemble.train(recent_df, col_name)
            
            # Get ML prediction
            ml_pred = ensemble.predict(recent_df)
            
            if ml_pred is None:
                continue
            
            pred_val = ml_pred['prediction']
            pred_std = ml_pred['std']
            lower_bound = ml_pred['lower_bound']
            upper_bound = ml_pred['upper_bound']
            model_agreement = ml_pred['model_agreement']
            
            # Opponent adjustment
            if tomorrow_opponent and tomorrow_opponent in defensive_stats:
                adj_factor = self.opponent_analyzer.get_opponent_adjustment(
                    tomorrow_opponent, col_name, numeric_vals.mean(), defensive_stats
                )
                pred_val *= adj_factor
                lower_bound *= adj_factor
                upper_bound *= adj_factor
            
            # Trend analysis
            if len(numeric_vals) >= 5:
                recent_avg = numeric_vals.tail(3).mean()
                earlier_avg = numeric_vals.head(2).mean()
                trend_direction = "📈 Hot" if recent_avg > earlier_avg else "📉 Cold" if recent_avg < earlier_avg else "➡️ Stable"
                trend_pct = ((recent_avg - earlier_avg) / earlier_avg * 100) if earlier_avg > 0 else 0
            else:
                trend_direction = "➡️ Stable"
                trend_pct = 0
            
            # Generate dynamic prop lines based on ML prediction
            base_lines = [
                lower_bound + (upper_bound - lower_bound) * 0.25,
                pred_val,
                upper_bound - (upper_bound - lower_bound) * 0.25
            ]
            
            for line in sorted(set([round(x * 2) / 2 for x in base_lines if x > 0])):
                games_over = (numeric_vals > line).sum()
                games_under = (numeric_vals < line).sum()
                games_push = (numeric_vals == line).sum()
                valid_games = len(numeric_vals) - games_push
                
                if valid_games == 0:
                    continue
                
                # Calculate probability using ML confidence
                hit_rate_over = (games_over / valid_games) * 100
                hit_rate_under = (games_under / valid_games) * 100
                
                # Adjust hit rate with model agreement confidence
                confidence_score = (model_agreement + 1) / 2  # Normalize to 0-1
                
                # Probability-based filter (more sophisticated than hard 70% threshold)
                for bet_type, hit_rate in [("OVER", hit_rate_over), ("UNDER", hit_rate_under)]:
                    adjusted_confidence = hit_rate * confidence_score / 100
                    
                    if adjusted_confidence >= 0.65:  # Lower threshold but confidence-weighted
                        recommendations.append({
                            "Player": player_name,
                            "Stat": readable_name,
                            "Prop Line": f"{bet_type} {line}",
                            "Hit Rate %": hit_rate,
                            "ML Prediction": f"{pred_val:.1f}",
                            "Confidence": f"{confidence_score*100:.0f}%",
                            "Probability": f"{adjusted_confidence*100:.0f}%",
                            "Trend": trend_direction,
                            "Type": bet_type,
                            "Games Hit": f"{int(games_over if bet_type == 'OVER' else games_under)}/{len(numeric_vals)}",
                            "Pred Range": f"{lower_bound:.1f}-{upper_bound:.1f}",
                            "Model Agreement": model_agreement
                        })
        
        if recommendations:
            rec_df = pd.DataFrame(recommendations)
            rec_df = rec_df.sort_values('Probability', ascending=False)
            return rec_df, actual_games
        
        return None, actual_games