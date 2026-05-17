# 🏀 NBA Stats & Schedule Hub

A Streamlit web application that displays NBA games scheduled for tomorrow and provides detailed player statistics from their last 10 games. Timezone-aware for Asia/Manila.

## Features

- **Games Tomorrow** 📅
  - Real-time NBA schedule for the next day (Asia/Manila timezone)
  - View game times, home/away teams, and game status
  - Auto-updates every hour

- **Player Stats** 📊
  - Browse players from teams playing tomorrow
  - View detailed statistics from last 10 games
  - Automatic player ID matching via boxscore lookup
  - Summary metrics (PPG, RPG, APG, SPG, BPG)
  - Game-by-game breakdown with comprehensive stats

- **Smart Features** 🎯
  - Timezone-aware scheduling (converts UTC to Manila time)
  - Intelligent player matching across API endpoints
  - Cached data (1-hour TTL) for performance
  - Debug info for troubleshooting player lookups
  - Responsive design with tabbed interface

## Tech Stack

- **[Streamlit](https://streamlit.io/)** - Web app framework
- **[Pandas](https://pandas.pydata.org/)** - Data manipulation and display
- **[Requests](https://docs.python-requests.org/)** - HTTP client for API calls
- **[python-dateutil](https://dateutil.readthedocs.io/)** - Timezone handling
- **ESPN API** - Real-time NBA data source

## Installation

### Prerequisites
- Python 3.7 or higher
- pip or conda package manager

### Clone the Repository

```bash
git clone https://github.com/RalphJade/NBA-Sched-Stats.git
cd NBA-Sched-Stats
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually install:

```bash
pip install streamlit pandas requests python-dateutil
```

## Usage

### Run the Application

```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`

### Tabs

**Tab 1: Games Tomorrow 🎮**
- View all NBA games scheduled for tomorrow (Asia/Manila time)
- Shows game date, time, teams, and status
- Updates every hour automatically

**Tab 2: Player Stats 📊**
1. Select a team (from teams playing tomorrow)
2. Select a player from the roster
3. View their stats from the last 10 completed games
4. See summary statistics and game-by-game breakdowns

## Data Sources

### ESPN API Endpoints Used

- **Scoreboard API**: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard`
  - Fetches upcoming and completed games
  - Returns game schedules, times, and status

- **Team Roster API**: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{teamId}/roster`
  - Retrieves complete team rosters
  - Used to populate player selections

- **Game Summary API**: `https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary`
  - Fetches detailed boxscore data
  - Contains player statistics per game

## Configuration

### Timezone
The app is configured to use **Asia/Manila** timezone (UTC+8). To change:

In `app.py`, modify the `manila_zone` variable:

```python
manila_zone = tz.gettz('YOUR_TIMEZONE')  # e.g., 'America/New_York', 'Europe/London'
```

### Cache TTL (Time To Live)
Data is cached for **1 hour** by default. Adjust in the decorator:

```python
@st.cache_data(ttl=3600)  # Change 3600 to desired seconds
```

### Lookback Period
The app fetches player stats from the **last 10 games**. To adjust:

In the `fetch_recent_games_for_team()` function:

```python
def fetch_recent_games_for_team(team_id, days_back=20):  # Change 20 to desired days
```

## How It Works

### Game Schedule Retrieval
1. Gets current date/time in Manila timezone
2. Queries ESPN API for yesterday → day+2
3. Filters games occurring on "tomorrow" (Manila date)
4. Extracts team IDs for games found

### Player Stats Collection
1. Fetches rosters for teams playing tomorrow
2. User selects team and player
3. App finds recent completed games for the team
4. Searches boxscores to match player by name
5. Extracts and displays statistics

### Player ID Matching
The app automatically matches players across different API endpoints:
- **Roster API** provides one player ID format
- **Boxscore API** may use a different ID format
- App searches by player name to find correct ID in boxscore data

## Troubleshooting

### "No games scheduled for tomorrow"
- Verify the current date/time in Manila timezone
- Check if it's the offseason (April-October)
- Try checking the schedule manually at ESPN.com

### "Could not find [Player] in any recent boxscores"
- Player may not have played in the last 10 games
- Check the debug info (expand "🔧 Debug Info" section) to see:
  - Games searched
  - All players in boxscore
  - Search process results
- Player might be on roster but inactive/injured

### API Connection Issues
- Verify internet connection
- ESPN API endpoints may be temporarily unavailable
- Check network firewall/proxy settings
- Wait a moment and refresh the page

### Slow Load Times
- First load for a player may take 10-15 seconds (API calls)
- Subsequent loads within 1 hour use cached data
- Reduce `days_back` parameter to decrease API calls

## Performance Notes

- **Caching**: 1-hour TTL prevents excessive API calls
- **Timeout**: 10-second timeout per API request
- **Pagination**: Limits to last 10 games per player
- **Deduplication**: Prevents duplicate game IDs across multiple API queries

## API Rate Limiting

ESPN API endpoints do not require authentication but may have rate limits:
- Use caching (already implemented)
- Avoid rapid refreshes
- Consider adding delays between requests if needed

## Future Enhancements

- Team performance statistics
- Advanced player filtering and comparison
- Historical stats tracking
- Injury reports integration
- Betting odds display
- Push notifications for game tips-off
- Custom timezone selection in UI

## Known Limitations

- Data limited to ESPN API availability
- Player history limited to last 10 games
- No authentication or user accounts
- No data persistence between sessions
- API data may lag 5-10 minutes behind live events

## Contributing

Contributions are welcome! Feel free to:
- Report bugs and issues
- Suggest new features
- Improve code documentation
- Optimize performance

## License

This project is open source. Check the repository for license details.

## Author

**Ralph Jade**

## Disclaimer

This app is for informational purposes only. Sports statistics are provided by ESPN and subject to their terms of use. Use responsibly!

---

**Questions or Issues?** Open an issue on the [GitHub repository](https://github.com/RalphJade/NBA-Sched-Stats).

Happy hooping! 🏀🚀
