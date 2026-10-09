"""Create the SQLAlchemy tables for a local demonstration database."""

from app import app, db


with app.app_context():
    db.create_all()
