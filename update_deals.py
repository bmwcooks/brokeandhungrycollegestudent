import json
import os
import requests
from datetime import datetime, timedelta
import pytz

# ESPN path segment differs from display league slug for some competitions
LEAGUE_API_MAP = {
    "mls": "usa.1",
}

# Metrics that map directly to the competitor scoreboard score field
SCOREBOARD_SCORE_METRICS = {
    None,
    "score",
    "runs",
    "goals",
    "points",
}


def fetch_espn_scores(sport, league, date_str):
    """Fetch completed games for a given sport/league and date (YYYYMMDD)."""
    api_league = LEAGUE_API_MAP.get(league, league)
    url = f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{api_league}/scoreboard?dates={date_str}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json().get('events', [])
    except Exception as e:
        print(f"Error fetching {sport}/{league}: {e}")
        return []


def get_stat_value(team_data, metric):
    """Resolve a trigger metric from ESPN competitor payload when possible."""
    if metric in SCOREBOARD_SCORE_METRICS:
        try:
            return int(team_data.get('score', 0) or 0)
        except (TypeError, ValueError):
            return 0

    # Map common promo metrics onto ESPN statistics names when present
    aliases = {
        "home_runs": {"homeruns", "home_runs", "homerun", "hr"},
        "strikeouts": {"strikeouts", "strikeout", "k", "pitcherstrikeouts"},
        "double_plays": {"doubleplays", "double_plays", "gidp"},
    }
    wanted = aliases.get(metric, {str(metric).lower().replace(" ", "")})

    for stat in team_data.get('statistics', []) or []:
        name = str(stat.get('name', '')).lower().replace(" ", "").replace("_", "")
        abbreviation = str(stat.get('abbreviation', '')).lower()
        display = str(stat.get('displayName', '')).lower().replace(" ", "").replace("_", "")
        if name in wanted or abbreviation in wanted or display in wanted:
            try:
                return int(float(stat.get('displayValue', stat.get('value', 0)) or 0))
            except (TypeError, ValueError):
                return 0

    # Unsupported advanced metric with no box-score stats available
    return None


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
    location = trigger.get('location')
    if location and location != 'any' and team_data.get('homeAway') != location:
        return False

    # Check Win trigger
    if trigger.get('type') == 'win':
        return team_data.get('winner') is True

    # Check Score/Stat trigger
    if trigger.get('type') == 'stat':
        metric = trigger.get('metric')
        stat_val = get_stat_value(team_data, metric)
        if stat_val is None:
            return False
        threshold = trigger.get('threshold', 0) or 0
        return stat_val >= threshold

    return False


def main():
    pacific = pytz.timezone('US/Pacific')
    now = datetime.now(pacific)
    yesterday = now - timedelta(days=1)
    date_str = yesterday.strftime('%Y%m%d')
    # Most "next day until 11:59 PM" deals expire at Pacific midnight tonight
    expires_at = now.replace(hour=23, minute=59, second=59, microsecond=0)

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
                promo_copy['expires_at'] = expires_at.strftime('%Y-%m-%dT%H:%M:%S%z')
                active_deals.append(promo_copy)
                break

    output = {
        "last_updated": now.strftime('%Y-%m-%d %H:%M:%S %Z'),
        "expires_at": expires_at.strftime('%Y-%m-%dT%H:%M:%S%z'),
        "deals": active_deals
    }

    os.makedirs('public', exist_ok=True)
    with open('public/active_deals.json', 'w') as f:
        json.dump(output, f, indent=2)

    print(f"Successfully processed. Active deals exported: {len(active_deals)}")


if __name__ == "__main__":
    main()
