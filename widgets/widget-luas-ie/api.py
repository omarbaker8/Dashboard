import xml.etree.ElementTree as ET
import requests
from flask import Blueprint, request, jsonify
from server.services.cache import cached

bp = Blueprint('widget_luas_ie', __name__, url_prefix='/api')

_LUAS_API_URL = 'https://luasforecasts.rpa.ie/xml/get.ashx'


@cached(ttl=60)
def _fetch(stop_code):
    resp = requests.get(
        _LUAS_API_URL,
        params={'action': 'forecast', 'stop': stop_code, 'encrypt': 'false'},
        timeout=10,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    stop_name = root.attrib.get('stop', stop_code)
    message = root.findtext('message', '')
    directions = []
    for direction in root.findall('direction'):
        dir_name = direction.attrib.get('name', '')
        trams = [
            {'destination': t.attrib.get('destination', ''),
             'dueMins': t.attrib.get('dueMins', '')}
            for t in direction.findall('tram')
        ]
        directions.append({'name': dir_name, 'trams': trams})
    return {'stop': stop_name, 'message': message, 'directions': directions, 'error': None}


@bp.route('/luas')
def api_luas():
    stop_code = request.args.get('stop', 'CHE').strip().upper()
    try:
        return jsonify(_fetch(stop_code))
    except Exception as e:
        print(f'[luas] fetch failed for {stop_code}: {e}')
        return jsonify({'stop': stop_code, 'message': '', 'directions': [], 'error': str(e)}), 502
