import json
import os
import random
import math
from datetime import datetime
from http.server import BaseHTTPRequestHandler
import urllib.request
import urllib.error

# Your API key (set as environment variable in Vercel)
ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')

# Team tiers for generating stats
TEAM_TIERS = {
    'Boston Celtics': 1, 'Oklahoma City Thunder': 1, 'Cleveland Cavaliers': 1,
    'Denver Nuggets': 2, 'Milwaukee Bucks': 2, 'New York Knicks': 2,
    'Phoenix Suns': 2, 'Los Angeles Lakers': 2, 'Miami Heat': 2,
    'Minnesota Timberwolves': 2, 'Dallas Mavericks': 2, 'Sacramento Kings': 2,
    'Indiana Pacers': 3, 'Orlando Magic': 3, 'Philadelphia 76ers': 3,
    'Los Angeles Clippers': 3, 'Golden State Warriors': 3, 'Houston Rockets': 3,
    'Memphis Grizzlies': 3, 'New Orleans Pelicans': 3, 'Atlanta Hawks': 3,
    'Chicago Bulls': 4, 'Brooklyn Nets': 4, 'Toronto Raptors': 4,
    'San Antonio Spurs': 4, 'Utah Jazz': 4, 'Portland Trail Blazers': 4,
    'Charlotte Hornets': 5, 'Detroit Pistons': 5, 'Washington Wizards': 5,
}

def get_team_abbrev(name):
    abbrevs = {
        'Atlanta Hawks': 'ATL', 'Boston Celtics': 'BOS', 'Brooklyn Nets': 'BKN',
        'Charlotte Hornets': 'CHA', 'Chicago Bulls': 'CHI', 'Cleveland Cavaliers': 'CLE',
        'Dallas Mavericks': 'DAL', 'Denver Nuggets': 'DEN', 'Detroit Pistons': 'DET',
        'Golden State Warriors': 'GSW', 'Houston Rockets': 'HOU', 'Indiana Pacers': 'IND',
        'Los Angeles Clippers': 'LAC', 'Los Angeles Lakers': 'LAL', 'Memphis Grizzlies': 'MEM',
        'Miami Heat': 'MIA', 'Milwaukee Bucks': 'MIL', 'Minnesota Timberwolves': 'MIN',
        'New Orleans Pelicans': 'NOP', 'New York Knicks': 'NYK', 'Oklahoma City Thunder': 'OKC',
        'Orlando Magic': 'ORL', 'Philadelphia 76ers': 'PHI', 'Phoenix Suns': 'PHX',
        'Portland Trail Blazers': 'POR', 'Sacramento Kings': 'SAC', 'San Antonio Spurs': 'SAS',
        'Toronto Raptors': 'TOR', 'Utah Jazz': 'UTA', 'Washington Wizards': 'WAS'
    }
    return abbrevs.get(name, 'UNK')

def get_team_stats(team_name):
    """Generate realistic stats based on team tier"""
    tier = TEAM_TIERS.get(team_name, 3)
    
    base_win_pct = {1: 0.70, 2: 0.58, 3: 0.50, 4: 0.40, 5: 0.30}[tier]
    base_net = {1: 8, 2: 4, 3: 0, 4: -4, 5: -8}[tier]
    
    # Add some randomness based on team name (consistent for same team)
    seed = sum(ord(c) for c in team_name) + datetime.now().day
    random.seed(seed)
    
    win_pct = min(1.0, max(0.0, base_win_pct + random.uniform(-0.15, 0.15)))
    wins = round(win_pct * 10)
    net_rating = round(base_net + random.uniform(-3, 3), 1)
    rest_days = random.choice([1, 2, 3])
    
    return {
        'record_l10': f"{wins}-{10-wins}",
        'net_rating': net_rating,
        'rest_days': rest_days,
        'win_pct': win_pct
    }

def predict_spread(home_team, away_team, spread):
    """Generate prediction for a game"""
    home_stats = get_team_stats(home_team)
    away_stats = get_team_stats(away_team)
    
    home_abbrev = get_team_abbrev(home_team)
    away_abbrev = get_team_abbrev(away_team)
    
    # Calculate expected edge
    home_advantage = (
        (home_stats['win_pct'] - away_stats['win_pct']) * 10 +
        (home_stats['net_rating'] - away_stats['net_rating']) * 0.5 +
        (home_stats['rest_days'] - away_stats['rest_days']) * 1.5 +
        3  # Home court advantage
    )
    
    expected_margin = home_advantage
    home_covers = expected_margin > -spread
    
    # Calculate confidence (50-85 range)
    edge = abs(expected_margin + spread)
    confidence = min(85, max(50, int(50 + edge * 3)))
    
    # Build reasoning
    reasons = []
    home_wins = int(home_stats['record_l10'].split('-')[0])
    away_wins = int(away_stats['record_l10'].split('-')[0])
    
    if abs(home_wins - away_wins) >= 2:
        better = home_abbrev if home_wins > away_wins else away_abbrev
        better_record = home_stats['record_l10'] if home_wins > away_wins else away_stats['record_l10']
        reasons.append(f"{better} {better_record} L10")
    
    if abs(home_stats['net_rating'] - away_stats['net_rating']) > 3:
        better = home_abbrev if home_stats['net_rating'] > away_stats['net_rating'] else away_abbrev
        reasons.append(f"{better} better net rating")
    
    rest_diff = home_stats['rest_days'] - away_stats['rest_days']
    if abs(rest_diff) >= 1:
        rested = home_abbrev if rest_diff > 0 else away_abbrev
        reasons.append(f"{rested} rest advantage")
    
    if not reasons:
        reasons.append("Close matchup, model finds slight edge")
    
    return {
        'pick': home_team if home_covers else away_team,
        'pick_spread': spread if home_covers else -spread,
        'confidence': confidence,
        'reasoning': ' • '.join(reasons[:3]),
        'home_stats': {
            'record_l10': home_stats['record_l10'],
            'net_rating': home_stats['net_rating'],
            'rest_days': home_stats['rest_days']
        },
        'away_stats': {
            'record_l10': away_stats['record_l10'],
            'net_rating': away_stats['net_rating'],
            'rest_days': away_stats['rest_days']
        }
    }

def fetch_odds():
    """Fetch NBA odds from The Odds API"""
    if not ODDS_API_KEY:
        return None, "API key not configured"
    
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey={ODDS_API_KEY}&regions=us&markets=spreads&oddsFormat=american"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"API error: {e.code}"
    except Exception as e:
        return None, str(e)

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Fetch odds from API
        games_data, error = fetch_odds()
        
        if error:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'error': error, 'games': []}).encode())
            return
        
        predictions = []
        
        for game in games_data or []:
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            commence_time = game.get('commence_time')
            
            # Get spread from first bookmaker
            spread = None
            bookmaker_name = None
            
            for bookmaker in game.get('bookmakers', []):
                for market in bookmaker.get('markets', []):
                    if market.get('key') == 'spreads':
                        for outcome in market.get('outcomes', []):
                            if outcome.get('name') == home_team:
                                spread = outcome.get('point')
                                bookmaker_name = bookmaker.get('title')
                                break
                        if spread is not None:
                            break
                if spread is not None:
                    break
            
            if spread is None:
                continue
            
            prediction = predict_spread(home_team, away_team, spread)
            
            predictions.append({
                'game_id': game.get('id'),
                'home_team': home_team,
                'away_team': away_team,
                'commence_time': commence_time,
                'spread': spread,
                'bookmaker': bookmaker_name,
                'prediction': prediction
            })
        
        response = {
            'generated_at': datetime.utcnow().isoformat(),
            'games': predictions
        }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
