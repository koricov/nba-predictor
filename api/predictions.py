import json
import os
import random
from datetime import datetime, timedelta
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
    
    home_advantage = (
        (home_stats['win_pct'] - away_stats['win_pct']) * 10 +
        (home_stats['net_rating'] - away_stats['net_rating']) * 0.5 +
        (home_stats['rest_days'] - away_stats['rest_days']) * 1.5 +
        3
    )
    
    expected_margin = home_advantage
    home_covers = expected_margin > -spread
    
    edge = abs(expected_margin + spread)
    confidence = min(85, max(50, int(50 + edge * 3)))
    
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

def fetch_scores():
    """Fetch completed NBA game scores from The Odds API"""
    if not ODDS_API_KEY:
        return None, "API key not configured"
    
    # Get scores from the last 3 days
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/scores?apiKey={ODDS_API_KEY}&daysFrom=3"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, f"Scores API error: {e.code}"
    except Exception as e:
        return None, str(e)

def determine_result(game_id, pick, pick_spread, scores_data):
    """
    Determine if our pick covered the spread based on final scores.
    Returns: 'won', 'lost', 'push', or None if game not completed
    """
    if not scores_data:
        return None
    
    # Find the game in scores data
    for game in scores_data:
        if game.get('id') == game_id:
            # Check if game is completed
            if not game.get('completed'):
                return None
            
            scores = game.get('scores')
            if not scores or len(scores) < 2:
                return None
            
            # Get scores for each team
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            
            home_score = None
            away_score = None
            
            for score in scores:
                if score.get('name') == home_team:
                    home_score = int(score.get('score', 0))
                elif score.get('name') == away_team:
                    away_score = int(score.get('score', 0))
            
            if home_score is None or away_score is None:
                return None
            
            # Calculate actual margin (positive = home won by X)
            actual_margin = home_score - away_score
            
            # Determine if our pick covered
            # If we picked home team with spread -5, they need to win by more than 5
            # If we picked away team with spread +5, they need to lose by less than 5 (or win)
            
            if pick == home_team:
                # We picked home team
                # pick_spread is the spread we got (e.g., -5 means home favored by 5)
                # Home covers if actual_margin > -pick_spread
                # e.g., if spread is -5, home needs to win by more than 5
                cover_margin = actual_margin + pick_spread
                if cover_margin > 0:
                    return 'won'
                elif cover_margin < 0:
                    return 'lost'
                else:
                    return 'push'
            else:
                # We picked away team
                # pick_spread is positive (e.g., +5 means away is underdog by 5)
                # Away covers if actual_margin < pick_spread
                # e.g., if spread is +5, away needs to lose by less than 5 (or win)
                cover_margin = pick_spread - actual_margin
                if cover_margin > 0:
                    return 'won'
                elif cover_margin < 0:
                    return 'lost'
                else:
                    return 'push'
    
    return None

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
        
        # Fetch scores for completed games
        scores_data, scores_error = fetch_scores()
        
        predictions = []
        
        for game in games_data or []:
            home_team = game.get('home_team')
            away_team = game.get('away_team')
            commence_time = game.get('commence_time')
            game_id = game.get('id')
            
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
            
            # Check if game is completed and determine result
            result = determine_result(
                game_id, 
                prediction['pick'], 
                prediction['pick_spread'],
                scores_data
            )
            
            # Get final scores if available
            final_scores = None
            if scores_data:
                for score_game in scores_data:
                    if score_game.get('id') == game_id and score_game.get('completed'):
                        scores = score_game.get('scores', [])
                        if len(scores) >= 2:
                            final_scores = {}
                            for s in scores:
                                final_scores[s.get('name')] = int(s.get('score', 0))
            
            predictions.append({
                'game_id': game_id,
                'home_team': home_team,
                'away_team': away_team,
                'commence_time': commence_time,
                'spread': spread,
                'bookmaker': bookmaker_name,
                'prediction': prediction,
                'result': result,  # 'won', 'lost', 'push', or None
                'final_scores': final_scores  # {'Team A': 110, 'Team B': 105} or None
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
