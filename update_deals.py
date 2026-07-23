import json
import os
import requests
from datetime import datetime, timedelta
import pytz

def fetch_espn_scores(sport, league, date_str):
    """Fetch completed games for a given sport/league and date (YYYYMMDD)."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard?dates={date_str}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get('events', [])
    except Exception as e:
        print(f"Error fetching {sport}/{league}: {e}")
        return []

def check_trigger(promo, event):
    """Determine whether a game event fulfilled a promotion's trigger requirements."""
    team_name = promo['team']
    trigger = promo['trigger']
    
    competitions = event.get('competitions', [])
    if not competitions:
        return False
        
    competitors = competitions[0].get('competitors', [])
    team_data = next((c for c in competitors if c.get('team', {}).get('displayName') == team_name), None)
    
    if not team_data:
        return False

    # Check Location filter (e.g. 'home')
    if trigger.get('location') == 'home' and team_data.get('homeAway') != 'home':
        return False
        
    # Check Win trigger
    if trigger.get('type') == 'win':
        return team_data.get('winner') is True

    # Check Score/Stat trigger
    if trigger.get('type') == 'stat':
        stat_val = int(team_data.get('score', 0))
        threshold = trigger.get('threshold', 0)
        if stat_val >= threshold:
            return True

    return False

def main():
    pacific = pytz.timezone('US/Pacific')
    yesterday = datetime.now(pacific) - timedelta(days=1)
    date_str = yesterday.strftime('%Y%m%d')

    if not os.path.exists('promotions.json'):
        print("promotions.json not found.")
        return

    with open('promotions.json', 'r') as f:
        db = json.load(f)

    active_deals = []
    fetched_leagues = {}

    for promo in db.get('promotions', []):
        if not promo.get('active', True):
            continue
        
        league = promo['league']
        sport = promo['sport']
        key = f"{sport}/{league}"

        if key not in fetched_leagues:
            fetched_leagues[key] = fetch_espn_scores(sport, league, date_str)

        events = fetched_leagues[key]
        for event in events:
            # Ensure the game is officially completed
            status_state = event.get('status', {}).get('type', {}).get('state')
            if status_state != 'post':
                continue
            
            if check_trigger(promo, event):
                promo_copy = dict(promo)
                promo_copy['activated_by'] = event.get('name', 'Yesterday\'s Game')
                active_deals.append(promo_copy)
                break

    output = {
        "last_updated": datetime.now(pacific).strftime('%Y-%m-%d %H:%M:%S %Z'),
        "deals": active_deals
    }

    os.makedirs('public', exist_ok=True)
    with open('public/active_deals.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Successfully processed. Active deals exported: {len(active_deals)}")

if __name__ == "__main__":
    main()
