from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
app = Flask(__name__)

app.config.from_object(Config)
app.config['JSON_AS_ASCII'] = False # Ensure Unicode characters are not escaped
app.json.ensure_ascii = False

db.init_app(app)
migrate.init_app(app, db)
login_manager.init_app(app)
login_manager.login_view = 'auth_bp.login'  
    
from auth.routes import auth_bp
from api.routes import api_bp
from app.routes import main_bp
from qr.routes import qr_code_bp
from ad.routes import ad_bp
from yapi.routes import yapi_bp
    
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(qr_code_bp, url_prefix='/qr')
app.register_blueprint(ad_bp, url_prefix='/b')
app.register_blueprint(yapi_bp, url_prefix='/yapi')
app.register_blueprint(main_bp)

from auth.models.user import User
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Centralized Logging Setup ---
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_centralized_logging(app):
    log_dir = os.path.join(app.root_path, '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'app.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    # Optionally, propagate logs to root logger
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.INFO)

setup_centralized_logging(app)