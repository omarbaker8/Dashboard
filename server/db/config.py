from .connection import get_db
from server.config import DEFAULT_CONFIG


def get_device_config(device_id):
    result = dict(DEFAULT_CONFIG)
    conn = get_db()
    rows = conn.execute(
        "SELECT key, value FROM device_config WHERE device_id=?", (device_id,)
    ).fetchall()
    conn.close()
    for r in rows:
        val = r['value']
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass
        result[r['key']] = val
    return result


def save_device_config(device_id, config):
    conn = get_db()
    for k, v in config.items():
        conn.execute(
            "INSERT OR REPLACE INTO device_config (device_id, key, value) VALUES (?, ?, ?)",
            (device_id, k, str(v)),
        )
    conn.commit()
    conn.close()
