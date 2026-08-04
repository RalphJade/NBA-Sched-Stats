from __future__ import annotations

from typing import Any, Dict, List, Optional


def get_available_team_names(all_players: Dict[str, Dict[str, Any]], upcoming_teams: Optional[set] = None) -> List[str]:
    """Return a sorted list of teams that have rosters and optionally are in the upcoming games list."""
    upcoming = set(upcoming_teams or [])

    if not all_players:
        return []

    if upcoming:
        return [
            team_name
            for team_name in sorted(all_players.keys())
            if all_players.get(team_name) and team_name in upcoming
        ]

    return [team_name for team_name in sorted(all_players.keys()) if all_players.get(team_name)]


def get_player_context(all_players: Dict[str, Dict[str, Any]], all_team_ids: Dict[str, Dict[str, Any]], selected_team: str, selected_player: str) -> Optional[Dict[str, Any]]:
    """Build a normalized player context object used across multiple tabs."""
    roster = all_players.get(selected_team, {})
    if not roster or selected_player not in roster:
        return None

    player_info = roster[selected_player]
    team_info = all_team_ids.get(selected_team, {})

    return {
        "selected_team": selected_team,
        "roster": roster,
        "selected_player": selected_player,
        "player_info": player_info,
        "player_id": player_info.get("id"),
        "player_image": player_info.get("image"),
        "team_logo": team_info.get("logo"),
        "team_id": team_info.get("id"),
        "player_position": player_info.get("position", "N/A"),
        "player_jersey": player_info.get("jersey", "N/A"),
        "player_age": player_info.get("age", "N/A"),
        "player_height": player_info.get("height", "N/A"),
        "player_weight": player_info.get("weight", "N/A"),
        "player_experience": player_info.get("experience", "N/A"),
    }


def load_player_stat_history(playerstats_module: Any, team_id: Any, selected_player: str, selected_team: str) -> Dict[str, Any]:
    """Load recent boxscore stats for a player using one shared path across tabs."""
    recent_game_ids, game_fetch_debug = playerstats_module.fetch_recent_games_for_team(team_id)

    if not recent_game_ids:
        return {
            "recent_game_ids": [],
            "game_fetch_debug": game_fetch_debug,
            "boxscore_player_ids": [],
            "debug_log": [],
            "stats": [],
        }

    boxscore_player_ids, debug_log = playerstats_module.find_correct_player_ids_in_boxscores(
        recent_game_ids,
        selected_player,
        selected_team,
    )

    if not boxscore_player_ids:
        return {
            "recent_game_ids": recent_game_ids,
            "game_fetch_debug": game_fetch_debug,
            "boxscore_player_ids": [],
            "debug_log": debug_log,
            "stats": [],
        }

    raw_stats = playerstats_module.fetch_boxscore_stats(recent_game_ids, boxscore_player_ids)
    all_stats: List[Dict[str, Any]] = []
    for player_id in boxscore_player_ids:
        all_stats.extend(raw_stats.get(player_id, []))

    return {
        "recent_game_ids": recent_game_ids,
        "game_fetch_debug": game_fetch_debug,
        "boxscore_player_ids": boxscore_player_ids,
        "debug_log": debug_log,
        "stats": playerstats_module._standardize_stats(all_stats),
    }
