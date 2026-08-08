"""
NBA GAME SIMULATION MODULE
==========================
Simulates NBA games with live play-by-play commentary and realistic rotations
Players are rated based on their recent performance stats
"""

import pandas as pd
import numpy as np
from datetime import datetime
import random

class PlayerRating:
    """Calculates player ratings based on recent performance"""
    
    def __init__(self, stats_df, player_name):
        self.player_name = player_name
        self.stats_df = stats_df
        self.rating = self._calculate_rating()
        self.tendencies = self._calculate_tendencies()
        self.minutes_played = 0
        self.foul_count = 0
    
    def _calculate_rating(self):
        """Calculate overall player rating (0-99 scale)"""
        if self.stats_df.empty:
            return 75  # Default rating
        
        # Get recent averages (last 5 games)
        recent = self.stats_df.tail(5)
        
        # Normalize stats to 0-1 scale (based on NBA league averages)
        pts_avg = recent['PTS'].mean() if 'PTS' in recent.columns else 0
        ast_avg = recent['AST'].mean() if 'AST' in recent.columns else 0
        reb_avg = recent['REB'].mean() if 'REB' in recent.columns else 0
        min_avg = recent['MIN'].mean() if 'MIN' in recent.columns else 20
        
        # League average approximations
        pts_norm = min(pts_avg / 25, 1.0)  # 25 PPG = elite
        ast_norm = min(ast_avg / 6, 1.0)   # 6 APG = elite
        reb_norm = min(reb_avg / 8, 1.0)   # 8 RPG = elite
        min_norm = min(min_avg / 30, 1.0)  # 30 MIN = starter
        
        # Weighted average
        rating = (pts_norm * 0.4 + ast_norm * 0.2 + reb_norm * 0.2 + min_norm * 0.2) * 99
        return max(min(rating, 99), 50)  # Clamp between 50-99
    
    def _calculate_tendencies(self):
        """Calculate player tendencies (shooting, playmaking, etc)"""
        if self.stats_df.empty:
            return {
                'three_pt_shooter': 0.5,
                'ball_handler': 0.5,
                'rebounder': 0.5,
                'defender': 0.5,
                'ft_shooter': 0.75
            }
        
        recent = self.stats_df.tail(5)
        
        # Three point shooter
        three_pm = recent['3PM'].mean() if '3PM' in recent.columns else 1
        three_pt_shooter = min(three_pm / 3, 1.0)
        
        # Ball handler (AST/TO ratio)
        ast = recent['AST'].mean() if 'AST' in recent.columns else 2
        to = recent['TO'].mean() if 'TO' in recent.columns else 2
        ball_handler = min(ast / (to + 1), 1.0)
        
        # Rebounder
        reb = recent['REB'].mean() if 'REB' in recent.columns else 4
        rebounder = min(reb / 8, 1.0)
        
        # Defender (STL + BLK)
        stl = recent['STL'].mean() if 'STL' in recent.columns else 1
        blk = recent['BLK'].mean() if 'BLK' in recent.columns else 0.5
        defender = min((stl + blk) / 2, 1.0)
        
        # Free throw shooter
        ft_shooter = 0.75  # Default FT%
        
        return {
            'three_pt_shooter': three_pt_shooter,
            'ball_handler': ball_handler,
            'rebounder': rebounder,
            'defender': defender,
            'ft_shooter': ft_shooter
        }


class NBAGameSimulator:
    """Simulates a complete NBA game with realistic rotations and pacing"""
    
    def __init__(self, home_team, away_team, home_roster, away_roster):
        """
        Args:
            home_team: Team name
            away_team: Team name
            home_roster: Dict of {player_name: stats_df}
            away_roster: Dict of {player_name: stats_df}
        """
        self.home_team = home_team
        self.away_team = away_team
        self.home_roster = home_roster
        self.away_roster = away_roster
        
        # Create player ratings
        self.home_players = {
            name: PlayerRating(stats, name) 
            for name, stats in home_roster.items()
        }
        self.away_players = {
            name: PlayerRating(stats, name) 
            for name, stats in away_roster.items()
        }
        
        # Create 9-man rotation (5 starters + 4 bench)
        self.home_lineup = self._create_lineup(self.home_players)
        self.away_lineup = self._create_lineup(self.away_players)
        
        # Game state
        self.home_score = 0
        self.away_score = 0
        self.quarter = 1
        self.game_time = 720.0  # Start at 12:00 (in seconds)
        self.possession_count = 0
        self.play_log = []
        self.box_score = {
            'home': {},
            'away': {}
        }
        
        # Initialize box score for all players
        for player in self.home_players:
            self.box_score['home'][player] = {
                'PTS': 0, 'REB': 0, 'AST': 0, '3PM': 0, 'STL': 0, 'BLK': 0, 
                'TO': 0, 'MIN': 0, 'FGM': 0, 'FGA': 0, 'FTM': 0, 'FTA': 0, 'PF': 0
            }
        for player in self.away_players:
            self.box_score['away'][player] = {
                'PTS': 0, 'REB': 0, 'AST': 0, '3PM': 0, 'STL': 0, 'BLK': 0, 
                'TO': 0, 'MIN': 0, 'FGM': 0, 'FGA': 0, 'FTM': 0, 'FTA': 0, 'PF': 0
            }
        
        # Track active players on court
        self.home_on_court = set(self.home_lineup[:5])  # Start with top 5
        self.away_on_court = set(self.away_lineup[:5])
    
    def _create_lineup(self, players_dict):
        """Create 9-man rotation: 5 starters + 4 bench"""
        sorted_players = sorted(
            players_dict.items(),
            key=lambda x: x[1].rating,
            reverse=True
        )
        return [name for name, _ in sorted_players[:9]]  # Top 9 players
    
    def get_active_lineup(self, team_type='home'):
        """Get current 5 active players on court"""
        if team_type == 'home':
            return list(self.home_on_court)
        else:
            return list(self.away_on_court)
    
    def rotate_players(self, team_type='home', quarter=1):
        """Rotate players based on quarter and minutes"""
        if team_type == 'home':
            lineup = self.home_lineup
            on_court = self.home_on_court
            players = self.home_players
        else:
            lineup = self.away_lineup
            on_court = self.away_on_court
            players = self.away_players
        
        # Get current minutes for all players
        total_mins = sum(players[p].minutes_played for p in on_court)
        
        # Substitute high-minute players
        for player in list(on_court):
            player_mins = players[player].minutes_played
            player_fouls = players[player].foul_count
            
            # Substitute if player has 5+ fouls or too many minutes
            if player_fouls >= 5 or (quarter <= 2 and player_mins >= 12) or (quarter > 2 and player_mins >= 30):
                # Find bench player with lowest minutes
                bench_players = [p for p in lineup if p not in on_court and players[p].foul_count < 5]
                if bench_players:
                    bench_player = min(bench_players, key=lambda p: players[p].minutes_played)
                    on_court.discard(player)
                    on_court.add(bench_player)
    
    def add_player_time(self, team_type, player_name, seconds):
        """Add time to player minutes"""
        minutes = seconds / 60.0
        if team_type == 'home':
            self.home_players[player_name].minutes_played += minutes
            self.box_score['home'][player_name]['MIN'] += minutes
        else:
            self.away_players[player_name].minutes_played += minutes
            self.box_score['away'][player_name]['MIN'] += minutes
    
    def _allocate_minutes(self, seconds):
        """Allocate minutes to all active on-court players for both teams."""
        for player_name in self.home_on_court:
            self.add_player_time('home', player_name, seconds / 5.0)
        for player_name in self.away_on_court:
            self.add_player_time('away', player_name, seconds / 5.0)
    
    def simulate_possession(self, offensive_team):
        """Simulate one possession (~20-30 seconds)"""
        team_type = 'home' if offensive_team == self.home_team else 'away'
        players = self.home_players if team_type == 'home' else self.away_players
        lineup = self.get_active_lineup(team_type)
        
        if not lineup:
            return 'error'
        
        possession_time = np.random.uniform(12, 24)  # 12-24 seconds per possession
        self._allocate_minutes(possession_time)
        ball_handler = random.choice(lineup)
        handler = players[ball_handler]
        
        # Decide play type
        play_roll = random.random()
        
        # TURNOVER (5%)
        if play_roll < 0.05:
            self.box_score[team_type][ball_handler]['TO'] += 1
            self.play_log.append({
                'quarter': self.quarter,
                'time': self._format_time(),
                'team': offensive_team,
                'color': 'yellow',
                'description': f"💔 TURNOVER — {ball_handler} loses the ball",
                'pts': (self.home_score, self.away_score)
            })
            return 'turnover'
        
        # STEAL/DEFENSIVE PLAY (4%)
        if play_roll < 0.09:
            def_team_type = 'away' if team_type == 'home' else 'home'
            def_players = self.home_players if def_team_type == 'home' else self.away_players
            def_lineup = self.get_active_lineup(def_team_type)
            defender = random.choice(def_lineup)
            
            # Add steal
            self.box_score[def_team_type][defender]['STL'] += 1
            self.box_score[team_type][ball_handler]['TO'] += 1
            
            self.play_log.append({
                'quarter': self.quarter,
                'time': self._format_time(),
                'team': self.away_team if def_team_type == 'away' else self.home_team,
                'color': 'purple',
                'description': f"🔐 STEAL! {defender} steals from {ball_handler}",
                'pts': (self.home_score, self.away_score)
            })
            return 'turnover'
        
        # THREE-POINT ATTEMPT (30%)
        if play_roll < 0.39:
            three_shooter = random.choice(lineup)
            shooter = players[three_shooter]
            
            # 3-pointer attempt
            self.box_score[team_type][three_shooter]['FGA'] += 1
            make_prob = (shooter.rating / 100) * shooter.tendencies['three_pt_shooter'] * 0.37
            
            if random.random() < make_prob:
                self.box_score[team_type][three_shooter]['PTS'] += 3
                self.box_score[team_type][three_shooter]['3PM'] += 1
                self.box_score[team_type][three_shooter]['FGM'] += 1
                
                if team_type == 'home':
                    self.home_score += 3
                else:
                    self.away_score += 3
                
                # Assist possibility (70%)
                if random.random() < 0.7 and three_shooter != ball_handler:
                    self.box_score[team_type][ball_handler]['AST'] += 1
                
                self.play_log.append({
                    'quarter': self.quarter,
                    'time': self._format_time(),
                    'team': offensive_team,
                    'color': 'green',
                    'description': f"🔥 {three_shooter} hits a 3-pointer! {self.home_score}-{self.away_score}",
                    'pts': (self.home_score, self.away_score)
                })
                
                # And-one possibility (5%)
                if random.random() < 0.05:
                    return 'and_one_three'
                return 'made_three'
            else:
                self.play_log.append({
                    'quarter': self.quarter,
                    'time': self._format_time(),
                    'team': offensive_team,
                    'color': 'red',
                    'description': f"❌ {three_shooter} misses the three",
                    'pts': (self.home_score, self.away_score)
                })
                return 'miss'
        
        # TWO-POINT ATTEMPT (61%)
        else:
            scorer = random.choice(lineup)
            shot_player = players[scorer]
            
            # 2-pointer attempt
            self.box_score[team_type][scorer]['FGA'] += 1
            make_prob = (shot_player.rating / 100) * 0.55
            
            if random.random() < make_prob:
                self.box_score[team_type][scorer]['PTS'] += 2
                self.box_score[team_type][scorer]['FGM'] += 1
                
                if team_type == 'home':
                    self.home_score += 2
                else:
                    self.away_score += 2
                
                # Assist possibility (50%)
                if random.random() < 0.5 and scorer != ball_handler:
                    self.box_score[team_type][ball_handler]['AST'] += 1
                
                self.play_log.append({
                    'quarter': self.quarter,
                    'time': self._format_time(),
                    'team': offensive_team,
                    'color': 'green',
                    'description': f"🎯 {scorer} scores! {self.home_score}-{self.away_score}",
                    'pts': (self.home_score, self.away_score)
                })
                
                # And-one possibility (8%)
                if random.random() < 0.08:
                    return 'and_one_two'
                return 'made_two'
            else:
                self.play_log.append({
                    'quarter': self.quarter,
                    'time': self._format_time(),
                    'team': offensive_team,
                    'color': 'red',
                    'description': f"❌ {scorer} misses",
                    'pts': (self.home_score, self.away_score)
                })
                return 'miss'
    
    def handle_rebound(self, team_type, missed_team_type):
        """Handle rebound after miss"""
        players = self.home_players if team_type == 'home' else self.away_players
        lineup = self.get_active_lineup(team_type)
        
        rebounder = random.choice(lineup)
        reb_player = players[rebounder]
        
        self.box_score[team_type][rebounder]['REB'] += 1
        
        rebound_type = "offensive" if team_type == missed_team_type else "defensive"
        self.play_log.append({
            'quarter': self.quarter,
            'time': self._format_time(),
            'team': self.home_team if team_type == 'home' else self.away_team,
            'color': 'blue',
            'description': f"🏀 {rebounder} gets the {rebound_type} rebound",
            'pts': (self.home_score, self.away_score)
        })
    
    def handle_and_one(self, team_type, player_name, points):
        """Handle and-one free throw"""
        players = self.home_players if team_type == 'home' else self.away_players
        ft_player = players[player_name]
        
        # Free throw attempt
        self.box_score[team_type][player_name]['FTA'] += 1
        
        if random.random() < ft_player.tendencies['ft_shooter']:
            self.box_score[team_type][player_name]['FTM'] += 1
            self.box_score[team_type][player_name]['PTS'] += 1
            
            if team_type == 'home':
                self.home_score += 1
            else:
                self.away_score += 1
            
            self.play_log.append({
                'quarter': self.quarter,
                'time': self._format_time(),
                'team': self.home_team if team_type == 'home' else self.away_team,
                'color': 'green',
                'description': f"⭐ {player_name} AND-ONE! Free throw made! {self.home_score}-{self.away_score}",
                'pts': (self.home_score, self.away_score)
            })
        else:
            self.play_log.append({
                'quarter': self.quarter,
                'time': self._format_time(),
                'team': self.home_team if team_type == 'home' else self.away_team,
                'color': 'red',
                'description': f"❌ {player_name} misses the AND-ONE free throw",
                'pts': (self.home_score, self.away_score)
            })
    
    def _format_time(self):
        """Format game time for display"""
        minutes = int(self.game_time // 60)
        seconds = int(self.game_time % 60)
        return f"{minutes}:{seconds:02d}"
    
    def simulate_quarter(self, quarter_num):
        """Simulate one quarter (12 minutes = 720 seconds)"""
        self.quarter = quarter_num
        self.game_time = 720.0
        
        # Target 48-54 possessions per quarter
        possessions_this_quarter = np.random.randint(48, 55)
        possessions_count = 0
        
        current_team = self.home_team if random.random() < 0.5 else self.away_team
        
        while possessions_count < possessions_this_quarter and self.game_time > 0:
            # Rotate players if needed
            self.rotate_players('home', quarter_num)
            self.rotate_players('away', quarter_num)
            
            # Simulate possession
            result = self.simulate_possession(current_team)
            
            # Handle rebounds after misses
            if result == 'miss':
                if random.random() < 0.6:  # 60% chance defensive rebound
                    def_team = self.away_team if current_team == self.home_team else self.home_team
                    def_type = 'away' if def_team == self.away_team else 'home'
                    self.handle_rebound(def_type, 'home' if current_team == self.home_team else 'away')
                    current_team = def_team
                else:  # 40% chance offensive rebound
                    off_type = 'home' if current_team == self.home_team else 'away'
                    self.handle_rebound(off_type, off_type)
            
            # Handle and-ones
            elif result == 'and_one_two':
                team_type = 'home' if current_team == self.home_team else 'away'
                scorer = [p for p in self.get_active_lineup(team_type)][-1]  # Last score maker
                self.handle_and_one(team_type, scorer, 1)
                current_team = self.away_team if current_team == self.home_team else self.home_team
            
            elif result == 'and_one_three':
                team_type = 'home' if current_team == self.home_team else 'away'
                scorer = [p for p in self.get_active_lineup(team_type)][-1]
                self.handle_and_one(team_type, scorer, 1)
                current_team = self.away_team if current_team == self.home_team else self.home_team
            
            elif result != 'turnover':
                current_team = self.away_team if current_team == self.home_team else self.home_team
            else:
                current_team = self.away_team if current_team == self.home_team else self.home_team
            
            # Advance time
            possession_time = np.random.uniform(12, 24)
            self.game_time -= possession_time
            possessions_count += 1
        
        # Quarter end
        self.play_log.append({
            'quarter': self.quarter,
            'time': 'END',
            'team': None,
            'color': 'neutral',
            'description': f"📊 END OF Q{self.quarter} | {self.home_team} {self.home_score} - {self.away_team} {self.away_score}",
            'pts': (self.home_score, self.away_score)
        })
    
    def simulate_game(self):
        """Simulate complete game (4 quarters)"""
        for q in range(1, 5):
            self.simulate_quarter(q)
        
        return self.get_final_stats()
    
    def get_play_log(self):
        """Get the play-by-play log"""
        return self.play_log
    
    def get_final_stats(self):
        """Get final box score and stats"""
        return {
            'home_team': self.home_team,
            'away_team': self.away_team,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'home_box_score': self.box_score['home'],
            'away_box_score': self.box_score['away'],
            'play_log': self.play_log
        }
    
    def get_home_team_stats(self):
        """Get home team box score as DataFrame (only players who played)"""
        data = []
        for player, stats in self.box_score['home'].items():
            if stats['MIN'] > 0:  # Only include players who played
                row = {'Player': player}
                row.update(stats)
                data.append(row)
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        totals = {'Player': 'TEAM TOTALS'}
        for col in ['PTS', 'REB', 'AST', '3PM', 'STL', 'BLK', 'TO', 'MIN', 'FGM', 'FGA', 'FTM', 'FTA', 'PF']:
            if col in df.columns:
                totals[col] = df[col].sum()
        
        return pd.concat([df, pd.DataFrame([totals])], ignore_index=True)
    
    def get_away_team_stats(self):
        """Get away team box score as DataFrame (only players who played)"""
        data = []
        for player, stats in self.box_score['away'].items():
            if stats['MIN'] > 0:  # Only include players who played
                row = {'Player': player}
                row.update(stats)
                data.append(row)
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        totals = {'Player': 'TEAM TOTALS'}
        for col in ['PTS', 'REB', 'AST', '3PM', 'STL', 'BLK', 'TO', 'MIN', 'FGM', 'FGA', 'FTM', 'FTA', 'PF']:
            if col in df.columns:
                totals[col] = df[col].sum()
        
        return pd.concat([df, pd.DataFrame([totals])], ignore_index=True)


def format_play_log(play_log):
    """Format play-by-play log for display"""
    df_data = []
    for play in play_log:
        df_data.append({
            'Q': play['quarter'],
            'Time': play['time'],
            'Play': play['description'],
            'Score': f"{play['pts'][0]} - {play['pts'][1]}",
            'Type': play['color']
        })
    
    return pd.DataFrame(df_data)


def get_player_rating_card(player_rating):
    """Get a formatted player rating card"""
    rating = player_rating.rating
    tendencies = player_rating.tendencies
    
    # Get rating tier
    if rating >= 90:
        tier = "⭐ ELITE"
    elif rating >= 80:
        tier = "🔥 STAR"
    elif rating >= 70:
        tier = "💪 SOLID"
    else:
        tier = "📈 DEVELOPING"
    
    return {
        'Overall': f"{rating:.0f}",
        'Tier': tier,
        '3-Pt': f"{tendencies['three_pt_shooter']*100:.0f}",
        'Playmaker': f"{tendencies['ball_handler']*100:.0f}",
        'Rebounder': f"{tendencies['rebounder']*100:.0f}",
        'Defender': f"{tendencies['defender']*100:.0f}"
    }


def get_play_color_style(color):
    """Get CSS/styling for play colors"""
    color_map = {
        'green': '#00ff00',    # Made basket
        'red': '#ff0000',      # Miss
        'yellow': '#ffff00',   # Turnover
        'purple': '#9900ff',   # Steal
        'blue': '#0099ff',     # Rebound
        'neutral': '#cccccc'   # Quarter end
    }
    return color_map.get(color, '#ffffff')
