from .connection import get_db, init_db


def init_app(app):
    with app.app_context():
        init_db()
