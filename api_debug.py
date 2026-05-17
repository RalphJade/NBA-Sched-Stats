"""
Quick debug script to check what games are in a team's schedule.
Run this to diagnose why games aren't being found.

Usage:
    python debug_schedule.py
"""

import requests
import json
from datetime import datetime

def debug_team_schedule(team_id="24"):  # 24 = San Antonio Spurs
    """
    Fetch and display a team's schedule for debugging.
    """
    url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{team_id}/schedule"
    
    print(f"Fetching schedule for team ID: {team_id}")
    print(f"URL: {url}\n")
    
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        events = data.get('events', [])
        print(f"Total events in schedule: {len(events)}\n")
        
        if not events:
            print("❌ No events found!")
            return
        
        # Show the last 5 events (most recent)
        print("=" * 80)
        print("LAST 5 EVENTS (Most Recent):")
        print("=" * 80)
        
        for i, event in enumerate(reversed(events[:5])):
            print(f"\nEvent {i}:")
            print(f"  ID: {event.get('id', 'N/A')}")
            
            # Get date
            try:
                comp = event.get('competitions', [{}])[0]
                game_date = comp.get('date', 'N/A')
                print(f"  Date: {game_date}")
            except:
                print(f"  Date: N/A")
            
            # Get status
            status_obj = event.get('status', {})
            status_type = status_obj.get('type', {})
            print(f"  Status State: {status_type.get('state', 'N/A')}")
            print(f"  Status Detail: {status_type.get('detail', 'N/A')}")
            print(f"  Status Name: {status_type.get('name', 'N/A')}")
            
            # Get teams
            try:
                comp = event.get('competitions', [{}])[0]
                competitors = comp.get('competitors', [])
                print(f"  Competitors: {len(competitors)}")
                for comp_entry in competitors:
                    team_name = comp_entry.get('team', {}).get('displayName', 'N/A')
                    score = comp_entry.get('score', 'N/A')
                    home_away = comp_entry.get('homeAway', 'N/A')
                    print(f"    - {home_away}: {team_name} (Score: {score})")
            except Exception as e:
                print(f"  Error parsing competitors: {e}")
            
            print(f"  Raw status: {json.dumps(status_type, indent=2)}")
        
        # Show game status summary
        print("\n" + "=" * 80)
        print("GAME STATUS SUMMARY:")
        print("=" * 80)
        
        completed_count = 0
        in_progress_count = 0
        scheduled_count = 0
        
        for event in events:
            status_type = event.get('status', {}).get('type', {})
            status_state = status_type.get('state', '')
            status_detail = status_type.get('detail', '')
            
            if status_state == 'post' or 'Final' in status_detail:
                completed_count += 1
            elif status_state == 'in':
                in_progress_count += 1
            else:
                scheduled_count += 1
        
        print(f"Completed: {completed_count}")
        print(f"In Progress: {in_progress_count}")
        print(f"Scheduled: {scheduled_count}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # You can change the team ID here
    # 24 = San Antonio Spurs
    # 1 = Atlanta Hawks
    # 2 = Boston Celtics
    # etc.
    
    team_id = "24"  # San Antonio Spurs
    debug_team_schedule(team_id)