import random
import uuid
from .connection import get_db

_ADJECTIVES = [
    'amber', 'bold', 'brave', 'bright', 'calm', 'clever', 'cosmic', 'crisp',
    'crystal', 'daring', 'dawn', 'deep', 'digital', 'dreamy', 'dusk', 'echo',
    'ember', 'ethereal', 'fading', 'fierce', 'floral', 'flowing', 'foggy',
    'frosty', 'gentle', 'gilded', 'glass', 'glowing', 'golden', 'grand',
    'hazy', 'hidden', 'hollow', 'hushed', 'icy', 'iron', 'jade', 'keen',
    'laser', 'lemon', 'light', 'liquid', 'lunar', 'maple', 'marble',
    'meadow', 'mighty', 'misty', 'mossy', 'neon', 'nimble', 'noble', 'nova',
    'opal', 'orchid', 'pastel', 'pearl', 'phantom', 'pine', 'pixel',
    'polar', 'prism', 'proud', 'quiet', 'rapid', 'raven', 'rising', 'rosy',
    'ruby', 'rustic', 'sable', 'sage', 'scarlet', 'shadow', 'shining',
    'silent', 'silver', 'sleek', 'snowy', 'solar', 'spark', 'starry',
    'steady', 'still', 'storm', 'swift', 'tidal', 'timber', 'twilight',
    'velvet', 'violet', 'vivid', 'wandering', 'warm', 'wild', 'winter',
    'woven', 'zen',
]

_NOUNS = [
    'anchor', 'atlas', 'aurora', 'beacon', 'birch', 'breeze', 'brook',
    'canyon', 'cedar', 'cliff', 'cloud', 'comet', 'coral', 'cove', 'crane',
    'creek', 'crest', 'dawn', 'delta', 'dune', 'eagle', 'echo', 'ember',
    'falcon', 'fern', 'field', 'flame', 'flare', 'flower', 'forest',
    'fountain', 'fox', 'frost', 'garden', 'glacier', 'grove', 'harbor',
    'hawk', 'heron', 'hill', 'horizon', 'island', 'lagoon', 'lake', 'lark',
    'leaf', 'lynx', 'maple', 'marsh', 'meadow', 'mist', 'moon', 'moss',
    'mountain', 'nebula', 'oak', 'ocean', 'orchid', 'osprey', 'otter',
    'owl', 'palm', 'panda', 'peak', 'pebble', 'phoenix', 'pine', 'plains',
    'pond', 'prairie', 'rain', 'rapids', 'reef', 'ridge', 'river', 'robin',
    'sage', 'shore', 'sky', 'snow', 'sparrow', 'spring', 'star', 'stone',
    'stream', 'summit', 'sun', 'swan', 'thunder', 'tide', 'trail', 'tulip',
    'valley', 'wave', 'willow', 'wind', 'wolf', 'wren',
]


def _generate_name():
    return f"{random.choice(_ADJECTIVES)}-{random.choice(_NOUNS)}"


def create_device(device_type):
    device_id = uuid.uuid4().hex[:12]
    name = _generate_name()
    conn = get_db()
    for _ in range(10):
        if not conn.execute("SELECT 1 FROM devices WHERE name=?", (name,)).fetchone():
            break
        name = _generate_name()
    conn.execute("INSERT INTO devices (id, name, type) VALUES (?, ?, ?)",
                 (device_id, name, device_type))
    conn.commit()
    conn.close()
    return device_id, name


def get_device(device_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def list_devices():
    conn = get_db()
    rows = conn.execute("SELECT * FROM devices ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
