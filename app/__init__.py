import os
from flask import Flask
from app.extensions import db, login_manager, limiter, csrf
from app.models import load_user

def create_app(test_config=None):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )

    # ── Pull resolved values from config (config.py already validates them) ──
    from config import SECRET_KEY, FLASK_DEBUG, SESSION_COOKIE_SECURE, SQLALCHEMY_DATABASE_URI, SQLALCHEMY_TRACK_MODIFICATIONS

    _is_production = os.environ.get('FLASK_ENV', 'development').lower() in ('production', 'prod')

    app.config.from_mapping(
        SECRET_KEY=SECRET_KEY,
        DEBUG=FLASK_DEBUG,
        SQLALCHEMY_DATABASE_URI=SQLALCHEMY_DATABASE_URI,
        SQLALCHEMY_TRACK_MODIFICATIONS=SQLALCHEMY_TRACK_MODIFICATIONS,
        # --- S-002 FIX: SECURE cookie only in production (requires HTTPS) ---
        SESSION_COOKIE_SECURE=SESSION_COOKIE_SECURE,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=8 * 60 * 60,  # 8 hours
        WTF_CSRF_ENABLED=True,                    # CSRF always enabled
    )

    if test_config:
        app.config.from_mapping(test_config)

    # ── Extensions ─────────────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)

    # ── Structured logging ──────────────────────────────────────────────────
    from app.logging_config import configure_logging
    configure_logging(app)

    # ── Database ────────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    # ── User Loader ─────────────────────────────────────────────────────────
    @login_manager.user_loader
    def user_loader(user_id):
        return load_user(user_id)

    # ── S-012 FIX: Security headers on every response ───────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # HSTS only in production (won't break local HTTP dev)
        if _is_production:
            response.headers['Strict-Transport-Security'] = (
                'max-age=31536000; includeSubDomains'
            )
        # CSP: allow CDN (Tailwind, Google Fonts) used in templates
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com "
            "https://cdn.tailwindcss.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:;"
        )
        return response

    # ── Error handlers ──────────────────────────────────────────────────────
    # OP-004: Comprehensive error page handling
    from app.error_handlers import register_error_handlers
    register_error_handlers(app)

    # ── Health check endpoints ──────────────────────────────────────────────
    # OP-003: Kubernetes liveness/readiness probes
    from app.health import bp as health_bp
    app.register_blueprint(health_bp, url_prefix='')

    # ── Blueprints ──────────────────────────────────────────────────────────
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    from app.staff import bp as staff_bp
    app.register_blueprint(staff_bp)

    from app.requests import bp as requests_bp
    app.register_blueprint(requests_bp)

    return app
