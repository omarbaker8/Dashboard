import os
from flask import Blueprint, jsonify

bp = Blueprint('widget_google_calendar', __name__, url_prefix='/api')


@bp.route('/google_cal_url')
def google_cal_url():
    return jsonify({"url": os.getenv('GOOGLE_CAL_IFRAME_URL', '')})
