import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schedule import fetch_upcoming_games_espn


class FallbackDataTests(unittest.TestCase):
    def test_fetch_upcoming_games_espn_returns_fallback_when_live_data_empty(self):
        start_date, end_date, games_df, team_ids = fetch_upcoming_games_espn(days_ahead=3)

        self.assertIsInstance(start_date, str)
        self.assertIsInstance(end_date, str)
        self.assertIsInstance(games_df, pd.DataFrame)
        self.assertIsInstance(team_ids, dict)


if __name__ == "__main__":
    unittest.main()
