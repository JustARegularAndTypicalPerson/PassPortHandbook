"""Environment-backed configuration for the portfolio snapshot."""

import os
import secrets


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or secrets.token_urlsafe(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///portfolio.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
    REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
