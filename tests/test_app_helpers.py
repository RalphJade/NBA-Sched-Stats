import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app_helpers import get_available_team_names


class AppHelpersTests(unittest.TestCase):
    def test_get_available_team_names_filters_to_upcoming_teams(self):
        all_players = {
            "BOS": {"Jayson Tatum": {}},
            "LAL": {"LeBron James": {}},
            "GSW": {"Stephen Curry": {}},
        }

        self.assertEqual(get_available_team_names(all_players, {"BOS", "LAL"}), ["BOS", "LAL"])

    def test_get_available_team_names_falls_back_to_all_teams_when_upcoming_is_empty(self):
        all_players = {
            "BOS": {"Jayson Tatum": {}},
            "LAL": {"LeBron James": {}},
        }

        self.assertEqual(get_available_team_names(all_players, set()), ["BOS", "LAL"])


if __name__ == "__main__":
    unittest.main()
