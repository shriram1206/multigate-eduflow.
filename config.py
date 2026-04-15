import os
import secrets
import warnings

# ========== SUPABASE/PostgreSQL DATABASE CONFIGURATION ==========
DB_HOST = os.environ.get('DB_HOST') or os.environ.get('MEF_DB_HOST')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_USER = os.environ.get('DB_USER') or os.environ.get('MEF_DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD') or os.environ.get('MEF_DB_PASSWORD')
DB_NAME = os.environ.get('DB_NAME') or os.environ.get('MEF_DB_NAME', 'postgres')

import urllib.parse
_encoded_pw = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
if DB_USER and DB_HOST and DB_NAME:
    if _encoded_pw:
        SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}:{_encoded_pw}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        SQLALCHEMY_DATABASE_URI = f"postgresql://{DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///mefportal.db'

SQLALCHEMY_TRACK_MODIFICATIONS = False

# ========== SECURITY CONFIGURATION ==========

# --- S-001 FIX: No hardcoded SECRET_KEY ---
_is_production = os.environ.get('FLASK_ENV', 'development').lower() in ('production', 'prod')

SECRET_KEY = (
    os.environ.get('MEF_SECRET_KEY')
    or os.environ.get('FLASK_SECRET_KEY')
    or os.environ.get('SECRET_KEY')
)

if not SECRET_KEY:
    if _is_production:
        raise RuntimeError(
            "\n\n[FATAL] MEF_SECRET_KEY environment variable is REQUIRED in production.\n"
            "Generate one with:\n"
            "  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "Then add to your .env file:\n"
            "  MEF_SECRET_KEY=<generated_value>\n"
        )
    else:
        SECRET_KEY = secrets.token_hex(32)
        warnings.warn(
            "MEF_SECRET_KEY is not set — using a random key. "
            "Sessions will NOT persist across restarts. "
            "Add MEF_SECRET_KEY to your .env file for stable development.",
            UserWarning,
            stacklevel=2
        )

# --- S-007 FIX: Debug mode ---
FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 'yes')
if _is_production and FLASK_DEBUG:
    FLASK_DEBUG = False
    warnings.warn("FLASK_DEBUG forced to False in production environment.", UserWarning, stacklevel=2)

FLASK_HOST = os.environ.get('FLASK_HOST', '127.0.0.1')
FLASK_PORT = int(os.environ.get('FLASK_PORT', 5000))

# --- S-002 FIX: Session cookies ---
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = _is_production  # True only in production (requires HTTPS)

# Production Rate Limiting
LIMITER_STORAGE_URI = os.environ.get('LIMITER_STORAGE_URI', 'memory://')

# Application Settings
APP_NAME = "MEF Portal"
COLLEGE_NAME = "Selvam College of Technology"
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max file size

# Email Configuration
MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@mefportal.edu')

# Pagination
REQUESTS_PER_PAGE = 10
STUDENTS_PER_PAGE = 20

# File Upload
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
