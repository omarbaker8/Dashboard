from flask import (Blueprint, render_template, request, redirect,
                   url_for, jsonify, make_response)
from server.db.devices import get_device, create_device, list_devices
from server.db.config import get_device_config, save_device_config
from server.db.widgets import (get_device_widgets, save_device_widget,
                                get_device_widget_ids, add_device_widget,
                                remove_device_widget, init_device_widgets)
from server.services import widget_loader
from server.services.preset_layouts import (get_preset_layout,
                                             get_location_widget_ids,
                                             get_refresh_widget_defaults)
from server.config import DEFAULT_CONFIG

bp = Blueprint('layout', __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_device_id():
    return request.cookies.get('device_id')


def _require_device():
    did = _current_device_id()
    return get_device(did) if did else None


def _cast_setting(value, spec):
    """Cast a raw form string to the type declared in a manifest settings spec."""
    t = spec.get('type', 'string')
    if t == 'integer':
        try:
            v = int(value)
            mn, mx = spec.get('min'), spec.get('max')
            if mn is not None:
                v = max(mn, v)
            if mx is not None:
                v = min(mx, v)
            return v
        except (ValueError, TypeError):
            return spec.get('default')
    elif t in ('float', 'latitude', 'longitude'):
        try:
            v = float(value)
            mn, mx = spec.get('min'), spec.get('max')
            if mn is not None:
                v = max(mn, v)
            if mx is not None:
                v = min(mx, v)
            return v
        except (ValueError, TypeError):
            return spec.get('default')
    elif t == 'boolean':
        return str(value).lower() in ('true', '1', 'yes', 'on')
    elif t == 'list':
        items = [s.strip() for s in str(value).split(',') if s.strip()]
        return items or spec.get('default', [])
    elif t == 'enum':
        allowed = spec.get('options', [])
        return value if value in allowed else spec.get('default')
    else:
        s = str(value).strip()
        max_len = spec.get('maxLength')
        return s[:max_len] if max_len else s


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------

@bp.route('/')
def index():
    if not _require_device():
        return redirect(url_for('layout.setup'))
    return redirect(url_for('layout.dashboard'))


@bp.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        device_type = request.form.get('device_type', 'laptop')
        if device_type not in ('laptop', 'tablet'):
            device_type = 'laptop'
        return redirect(url_for('layout.setup_widgets', type=device_type))
    return render_template('setup.html', devices=list_devices())


@bp.route('/setup/widgets', methods=['GET', 'POST'])
def setup_widgets():
    device_type = request.args.get('type') or request.form.get('device_type', 'laptop')
    if device_type not in ('laptop', 'tablet'):
        device_type = 'laptop'

    base_widgets = widget_loader.get_base_widgets()
    base_by_id = {bw['id']: bw for bw in base_widgets}
    preset_ids = [e[0] for e in get_preset_layout(device_type) if e[0] in base_by_id]

    if request.method == 'POST':
        selected = set(request.form.getlist('widgets'))
        d_lat = request.form.get('default_lat', '').strip()
        d_lng = request.form.get('default_lng', '').strip()
        d_city = request.form.get('default_city', '').strip()
        d_tz = request.form.get('default_timezone', '').strip()
        lat = float(d_lat) if d_lat else None
        lng = float(d_lng) if d_lng else None

        device_id, _ = create_device(device_type)
        init_device_widgets(device_id, device_type, base_widgets,
                            selected_ids=selected,
                            default_lat=lat, default_lng=lng,
                            default_city=d_city or None,
                            default_timezone=d_tz or None)
        cfg = dict(DEFAULT_CONFIG)
        if lat is not None:
            cfg.update({'default_lat': lat, 'default_lng': lng,
                        'default_city': d_city, 'default_timezone': d_tz})
        save_device_config(device_id, cfg)

        resp = make_response(redirect(url_for('layout.dashboard')))
        resp.set_cookie('device_id', device_id, max_age=60*60*24*365*5,
                        httponly=True, samesite='Lax')
        return resp

    return render_template('setup_widgets.html',
                           device_type=device_type,
                           widgets=[base_by_id[wid] for wid in preset_ids],
                           preselected=set(preset_ids))


@bp.route('/dashboard')
def dashboard():
    device = _require_device()
    if not device:
        return redirect(url_for('layout.setup'))
    config = get_device_config(device['id'])
    widgets = get_device_widgets(device['id'], widget_loader.get_base_widgets())
    loc_widgets = get_location_widget_ids()
    refresh_widgets = set(get_refresh_widget_defaults())
    return render_template('dashboard.html', widgets=widgets, config=config,
                           device=device, loc_widgets=loc_widgets,
                           refresh_widgets=refresh_widgets)


@bp.route('/settings', methods=['GET', 'POST'])
def settings():
    device = _require_device()
    if not device:
        return redirect(url_for('layout.setup'))

    config = get_device_config(device['id'])

    if request.method == 'POST':
        action = request.form.get('action')
        is_ajax = (request.headers.get('X-Requested-With') == 'fetch'
                   or 'application/json' in (request.headers.get('Accept') or ''))

        # ----------------------------------------------------------------
        # update_widget — generic, manifest-driven. Zero per-widget if-chains.
        # ----------------------------------------------------------------
        if action == 'update_widget':
            widget_id = request.form.get('id', '').strip()
            new_css = request.form.get('css', '').strip()
            if not widget_id:
                return jsonify({"status": "error"}) if is_ajax else redirect(url_for('layout.settings'))

            manifest = widget_loader.load_manifest(widget_id)
            widgets = get_device_widgets(device['id'], widget_loader.get_base_widgets())

            for w in widgets:
                if w['id'] != widget_id:
                    continue
                if new_css:
                    w['css'] = new_css

                # Apply every setting declared in manifest.settings[]
                for spec in manifest.get('settings', []):
                    key = spec['key']
                    raw = request.form.get(key)
                    if raw is None:
                        continue
                    w[key] = _cast_setting(raw, spec)

                # Location fields — injected if manifest.requires.location is true
                if manifest.get('requires', {}).get('location'):
                    for key in ('lat', 'lng'):
                        raw = request.form.get(key)
                        if raw is not None:
                            try:
                                w[key] = float(raw)
                            except ValueError:
                                pass
                    for key in ('timezone', 'city'):
                        raw = request.form.get(key)
                        if raw is not None:
                            w[key] = raw.strip()

                # Refresh interval — injected if manifest declares a refresh block
                if manifest.get('refresh') and request.form.get('refresh_interval') is not None:
                    try:
                        w['refresh_interval'] = int(request.form['refresh_interval'])
                    except ValueError:
                        pass

                save_device_widget(device['id'], w)
                break

            return jsonify({"status": "ok", "action": action, "id": widget_id}) if is_ajax \
                else redirect(url_for('layout.settings'))

        # ----------------------------------------------------------------
        # update_default_location
        # ----------------------------------------------------------------
        elif action == 'update_default_location':
            d_lat = request.form.get('default_lat', '').strip()
            d_lng = request.form.get('default_lng', '').strip()
            d_city = request.form.get('default_city', '').strip()
            d_tz = request.form.get('default_timezone', '').strip()
            if d_lat and d_lng:
                try:
                    config['default_lat'] = float(d_lat)
                    config['default_lng'] = float(d_lng)
                    config['default_city'] = d_city
                    config['default_timezone'] = d_tz
                    save_device_config(device['id'], config)
                except ValueError:
                    pass
            return jsonify({"status": "ok", "action": action}) if is_ajax \
                else redirect(url_for('layout.settings'))

        # ----------------------------------------------------------------
        # update_background
        # ----------------------------------------------------------------
        elif action == 'update_background':
            bg_css = request.form.get('background_css', '').strip()
            if bg_css:
                config['background'] = bg_css
                config['bg_video'] = ''
            config['bg_blur'] = int(request.form.get('bg_blur', 0) or 0)
            config['bg_dim'] = int(request.form.get('bg_dim', 0) or 0)
            bg_video = request.form.get('bg_video')
            if bg_video is not None:
                config['bg_video'] = bg_video.strip()
                if config['bg_video']:
                    config['background'] = 'transparent'
            save_device_config(device['id'], config)
            return jsonify({"status": "ok", "action": action, "config": config}) if is_ajax \
                else redirect(url_for('layout.settings'))

        # ----------------------------------------------------------------
        # remove_widget / add_widget
        # ----------------------------------------------------------------
        elif action == 'remove_widget':
            widget_id = request.form.get('id', '').strip()
            if widget_id:
                remove_device_widget(device['id'], widget_id)
            return jsonify({"status": "ok", "action": action, "id": widget_id}) if is_ajax \
                else redirect(url_for('layout.settings'))

        elif action == 'add_widget':
            widget_id = request.form.get('id', '').strip()
            if widget_id:
                base_by_id = {bw['id']: bw for bw in widget_loader.get_base_widgets()}
                if widget_id in base_by_id:
                    d_lat = config.get('default_lat')
                    d_lng = config.get('default_lng')
                    add_device_widget(
                        device['id'], device['type'], widget_id,
                        base_widget=base_by_id[widget_id],
                        default_lat=d_lat if isinstance(d_lat, (int, float)) else None,
                        default_lng=d_lng if isinstance(d_lng, (int, float)) else None,
                        default_city=config.get('default_city') or None,
                        default_timezone=config.get('default_timezone') or None,
                    )
            return jsonify({"status": "ok", "action": action, "id": widget_id}) if is_ajax \
                else redirect(url_for('layout.settings'))

        return redirect(url_for('layout.settings'))

    # GET
    widgets = get_device_widgets(device['id'], widget_loader.get_base_widgets())
    active_ids = get_device_widget_ids(device['id'])
    base_widgets = widget_loader.get_base_widgets()
    available_widgets = [{'id': bw['id'], 'active': bw['id'] in active_ids}
                         for bw in base_widgets]
    return render_template('settings.html',
                           widgets=widgets,
                           config=config,
                           device=device,
                           available_widgets=available_widgets,
                           loc_widgets=get_location_widget_ids(),
                           refresh_widget_defaults=get_refresh_widget_defaults())


# ---------------------------------------------------------------------------
# Layout API
# ---------------------------------------------------------------------------

@bp.route('/api/update_layout', methods=['POST'])
def update_layout():
    device = _require_device()
    if not device:
        return jsonify({"status": "error", "message": "no device"})
    changes = request.json
    if not changes:
        return jsonify({"status": "error", "message": "no data"})
    widgets = get_device_widgets(device['id'], widget_loader.get_base_widgets())
    widget_map = {w['id']: w for w in widgets}
    for item in changes:
        wid = item.get('id')
        if wid not in widget_map:
            continue
        w = widget_map[wid]
        for key in ('x', 'y', 'w', 'h'):
            val = item.get(key)
            if val is not None:
                w[key] = val
        save_device_widget(device['id'], w)
    return jsonify({"status": "success"})
