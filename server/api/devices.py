from flask import Blueprint, redirect, url_for, make_response
from server.db.devices import get_device

bp = Blueprint('devices', __name__)


@bp.route('/switch/<device_id>')
def switch_device(device_id):
    if not get_device(device_id):
        return redirect(url_for('layout.setup'))
    resp = make_response(redirect(url_for('layout.dashboard')))
    resp.set_cookie('device_id', device_id, max_age=60*60*24*365*5,
                    httponly=True, samesite='Lax')
    return resp
