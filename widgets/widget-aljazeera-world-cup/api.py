import json
import re
import base64
import urllib.parse
import requests
from flask import Blueprint, jsonify
from server.services.cache import cached

bp = Blueprint('widget_aljazeera_world_cup', __name__, url_prefix='/api')

_AJ_HOMEPAGE = 'https://www.aljazeera.com/'
_AJ_GRAPHQL  = 'https://www.aljazeera.com/graphql'
_AJ_HEADERS  = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept':  'application/json',
    'Referer': 'https://www.aljazeera.com/',
}
_AJ_BADGE = (
    'https://omo.akamai.opta.net/image.php'
    '?secure=true&h=omo.akamai.opta.net'
    '&sport=football&entity=team&description=badges'
    '&dimensions=150&id={}'
)


def _badge_url(team_id):
    return _AJ_BADGE.format(urllib.parse.quote(str(team_id), safe='')) if team_id else ''


def _resolve_team(state, ref):
    key = ref.get('__ref', '')
    team = state.get(key, {})
    return {'name': team.get('name', ''), 'badge_url': _badge_url(team.get('id', ''))}


def _resolve_match(state, ref):
    key = ref.get('__ref', '')
    raw = state.get(key)
    if not raw:
        return None
    home = _resolve_team(state, raw.get('home', {}))
    away = _resolve_team(state, raw.get('away', {}))
    return {
        'date': raw.get('date', ''), 'time': raw.get('time', ''),
        'status': raw.get('matchStatus', ''),
        'live_minute': raw.get('currentMatchTime'),
        'period': raw.get('periodName'),
        'home_team': home['name'], 'home_badge_url': home['badge_url'],
        'home_goals': raw.get('homeGoals'), 'home_penalties': raw.get('homePenaltyShootouts'),
        'away_team': away['name'], 'away_badge_url': away['badge_url'],
        'away_goals': raw.get('awayGoals'), 'away_penalties': raw.get('awayPenaltyShootouts'),
    }


@cached(ttl=60)
def _fetch():
    resp = requests.get(_AJ_HOMEPAGE, headers=_AJ_HEADERS, timeout=10)
    resp.raise_for_status()
    m = re.search(r'window\.__APOLLO_STATE__="([^"]+)"', resp.text)
    if not m:
        raise ValueError('Apollo state not found')
    state     = json.loads(base64.b64decode(m.group(1)).decode('utf-8'))
    hp        = state.get('HomepageAj:{}', {})
    post_id   = int(hp.get('id', 0))
    ticker_on = bool(hp.get('tickerEnabled', False))
    match_refs = hp.get('selectedLeagueMatches', [])

    all_matches = [_resolve_match(state, r) for r in match_refs]
    played = sorted(
        (x for x in all_matches if x and x['status'] == 'Played'),
        key=lambda x: x['date'] + 'T' + x['time'],
        reverse=True,
    )
    recent = played[:4]

    ticker = None
    if ticker_on and post_id:
        gql = requests.get(
            _AJ_GRAPHQL,
            headers=_AJ_HEADERS,
            params={
                'wp-site': 'aje',
                'operationName': 'FootballTickerMatchesQuery',
                'variables': json.dumps({'postId': post_id}, separators=(',', ':')),
                'extensions': '{}',
            },
            timeout=10,
        )
        gql.raise_for_status()
        matches = gql.json().get('data', {}).get('footballMultipleMatchesDetails', [])
        if matches:
            raw = matches[0]
            teams = {t['position']: t for t in raw.get('teams', [])}
            h, a = teams.get('home', {}), teams.get('away', {})
            match = raw.get('match', {})
            ticker = {
                'date': match.get('date', ''), 'time': match.get('time', ''),
                'status': match.get('status', ''),
                'live_minute': match.get('currentMatchTime'),
                'period': match.get('periodName'),
                'home_team': h.get('name', ''), 'home_badge_url': _badge_url(h.get('id', '')),
                'home_goals': h.get('totalGoals'), 'home_penalties': h.get('totalPenaltyShootouts'),
                'away_team': a.get('name', ''), 'away_badge_url': _badge_url(a.get('id', '')),
                'away_goals': a.get('totalGoals'), 'away_penalties': a.get('totalPenaltyShootouts'),
            }

    if ticker:
        ht, at = ticker['home_team'].lower(), ticker['away_team'].lower()
        recent = [m for m in recent
                  if not (m['home_team'].lower() == ht and m['away_team'].lower() == at)]

    return {'ticker': ticker, 'recent': recent, 'ticker_enabled': ticker_on}


@bp.route('/world_cup')
def api_world_cup():
    try:
        return jsonify(_fetch())
    except Exception as e:
        print(f'[world_cup] fetch failed: {e}')
        return jsonify({'ticker': None, 'recent': [], 'ticker_enabled': False, 'error': str(e)}), 500
