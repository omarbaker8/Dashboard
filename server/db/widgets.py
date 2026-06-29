import json
from .connection import get_db


def get_device_widgets(device_id, base_widgets):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM device_widgets WHERE device_id=? ORDER BY widget_id",
        (device_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return base_widgets

    base_by_id = {bw['id']: bw for bw in base_widgets}
    result = []
    for r in rows:
        bw = base_by_id.get(r['widget_id'])
        if not bw:
            continue
        w = dict(bw)
        w['x'] = r['x']
        w['y'] = r['y']
        w['w'] = r['w']
        w['h'] = r['h']
        if r['css']:
            w['css'] = r['css']
        extra = json.loads(r['extra'] or '{}')
        w.update(extra)
        result.append(w)
    return result


def save_device_widget(device_id, widget):
    extra = {k: v for k, v in widget.items()
             if k not in ('id', 'x', 'y', 'w', 'h', 'css', 'content', 'lock_ratio')}
    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO device_widgets
               (device_id, widget_id, x, y, w, h, css, extra)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (device_id, widget['id'], widget['x'], widget['y'],
         widget['w'], widget['h'], widget.get('css', ''),
         json.dumps(extra)),
    )
    conn.commit()
    conn.close()


def get_device_widget_ids(device_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT widget_id FROM device_widgets WHERE device_id=?", (device_id,)
    ).fetchall()
    conn.close()
    return {r['widget_id'] for r in rows}


def add_device_widget(device_id, device_type, widget_id, base_widget=None,
                      default_lat=None, default_lng=None,
                      default_city=None, default_timezone=None):
    from server.services.preset_layouts import get_preset_for_widget, get_location_widget_ids, GLASS_CSS
    preset = get_preset_for_widget(device_type, widget_id)
    loc_ids = get_location_widget_ids()

    if preset:
        wid, x, y, w, h, css, extra = preset
        extra = dict(extra)
    else:
        bw = base_widget or {}
        wid, x, y = widget_id, bw.get('x', 0), bw.get('y', 0)
        w, h = bw.get('w', 3), bw.get('h', 3)
        css = bw.get('css', GLASS_CSS)
        extra = {k: v for k, v in bw.items()
                 if k not in ('id', 'x', 'y', 'w', 'h', 'css', 'content', 'lock_ratio')}

    if wid in loc_ids and default_lat is not None and default_lng is not None:
        extra['lat'] = default_lat
        extra['lng'] = default_lng
        if default_city:
            extra['city'] = default_city
        if default_timezone:
            extra['timezone'] = default_timezone

    conn = get_db()
    conn.execute(
        """INSERT OR REPLACE INTO device_widgets
               (device_id, widget_id, x, y, w, h, css, extra)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (device_id, wid, x, y, w, h, css, json.dumps(extra)),
    )
    conn.commit()
    conn.close()


def remove_device_widget(device_id, widget_id):
    conn = get_db()
    conn.execute(
        "DELETE FROM device_widgets WHERE device_id=? AND widget_id=?",
        (device_id, widget_id),
    )
    conn.commit()
    conn.close()


def init_device_widgets(device_id, device_type, base_widgets, selected_ids=None,
                        default_lat=None, default_lng=None,
                        default_city=None, default_timezone=None):
    from server.services.preset_layouts import get_preset_layout, get_location_widget_ids
    layout = get_preset_layout(device_type)
    loc_ids = get_location_widget_ids()
    base_ids = {bw['id'] for bw in base_widgets}
    sel = set(selected_ids) if selected_ids is not None else None

    conn = get_db()
    for (wid, x, y, w, h, css, extra) in layout:
        if wid not in base_ids:
            continue
        if sel is not None and wid not in sel:
            continue
        row_extra = dict(extra)
        if wid in loc_ids and default_lat is not None and default_lng is not None:
            row_extra['lat'] = default_lat
            row_extra['lng'] = default_lng
            if default_city:
                row_extra['city'] = default_city
            if default_timezone:
                row_extra['timezone'] = default_timezone
        conn.execute(
            """INSERT OR REPLACE INTO device_widgets
                   (device_id, widget_id, x, y, w, h, css, extra)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (device_id, wid, x, y, w, h, css, json.dumps(row_extra)),
        )
    conn.commit()
    conn.close()
