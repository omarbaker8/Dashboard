import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH         = str(BASE_DIR / 'dashboard.db')
WIDGETS_DIR     = str(BASE_DIR / 'widgets')
WALLPAPERS_DIR  = str(BASE_DIR / 'static' / 'wallpapers')
AERIALS_DIR     = str(BASE_DIR / 'static' / 'aerials')
FONTS_DIR       = str(BASE_DIR / 'static' / 'fonts')
THUMBS_DIR      = str(BASE_DIR / 'static' / 'wallpapers' / '.thumbs')
ALLOWED_IMAGE_EXT = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg')
THUMB_SIZE      = (280, 175)

_cfg_path = BASE_DIR / 'config' / 'default.json'
if _cfg_path.exists():
    with open(_cfg_path) as _f:
        DEFAULT_CONFIG = json.load(_f)
else:
    DEFAULT_CONFIG = {
        "background": "url('/static/wallpapers/Aligned.png') no-repeat center / cover fixed",
        "bg_blur": 0,
        "bg_dim": 0,
    }
