from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_sqlalchemy import SQLAlchemy
import logging
import os

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

csrf = CSRFProtect()

# --- S-009 FIX: Use env var for storage so Redis can be plugged in for prod ---
_storage_uri = os.environ.get('LIMITER_STORAGE_URI', 'memory://')

if _storage_uri == 'memory://':
    logging.getLogger('mefportal').warning(
        "Rate limiter using in-memory storage — limits reset on restart. "
        "Set LIMITER_STORAGE_URI=redis://localhost:6379 for production."
    )

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    storage_options={},
    strategy="fixed-window"
)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger('mefportal')
