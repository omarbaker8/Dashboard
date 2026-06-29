import os
from pathlib import Path
from flask import Flask

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / 'templates'),
        static_folder=str(BASE_DIR / 'static'),
        static_url_path='/static',
    )
    app.config['BASE_DIR'] = str(BASE_DIR)

    try:
        from dotenv import load_dotenv
        load_dotenv(BASE_DIR / '.env')
    except ImportError:
        pass

    from .db import init_app as _init_db
    _init_db(app)

    from .api import register_blueprints
    register_blueprints(app)

    return app
