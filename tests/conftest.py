"""
tests/conftest.py
─────────────────
Central test configuration and fixtures.

Strategy
────────
• We configure the app with TESTING=True and WTF_CSRF_ENABLED=False
  so we can send POST requests without generating real CSRF tokens.
• SQLALCHEMY_DATABASE_URI is overridden to SQLite in-memory, which is
  sufficient for all non-PostgreSQL-specific route logic.
• Any route that calls a PostgreSQL-only function (e.g. generate_series)
  is tested at the *form-validation* layer only — never hitting the DB.
"""

import pytest
from unittest.mock import MagicMock, patch
from werkzeug.security import generate_password_hash

# ── App factory ──────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    """Real Flask app wired to an in-memory SQLite DB for isolation."""
    from app import create_app

    test_config = {
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key-do-not-use-in-prod',
        'SERVER_NAME': None,
        'RATELIMIT_ENABLED': False,      # disable rate limiting during tests
        'RATELIMIT_STORAGE_URI': 'memory://',
    }

    application = create_app(test_config)

    # Build all tables in the in-memory SQLite DB
    with application.app_context():
        from app.extensions import db
        db.create_all()

    return application


@pytest.fixture(scope='session')
def client(app):
    """Flask test client with cookie support (needed for sessions)."""
    return app.test_client()


# ── Helper: seed a user ──────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def seeded_student(app):
    """
    Creates a fresh Student user in the in-memory DB for each test,
    then cleans up afterwards.
    """
    from app.extensions import db
    from app.models import User

    with app.app_context():
        # Ensure no residual user from last test
        User.query.filter_by(register_number='TST001').delete()
        db.session.commit()

        user = User(
            username='test_student',
            name='Test Student',
            role='Student',
            password=generate_password_hash('Test@1234'),
            register_number='TST001',
            email='test@example.com',
            department='cse',
            year='2',
            dob='2000-01-01',
            student_type='Day Scholar',
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    yield user_id   # hand the ID to the test

    # Teardown
    with app.app_context():
        from app.models import AuthLockout
        AuthLockout.query.filter_by(register_number='TST001').delete()
        User.query.filter_by(register_number='TST001').delete()
        db.session.commit()


@pytest.fixture(scope='function')
def seeded_mentor(app):
    """Creates a fresh Mentor user for staff route tests."""
    from app.extensions import db
    from app.models import User

    with app.app_context():
        User.query.filter_by(register_number='MEN901').delete()
        db.session.commit()

        mentor = User(
            username='test_mentor',
            name='Test Mentor',
            role='Mentor',
            password=generate_password_hash('Mentor@1234'),
            register_number='MEN901',
            email='mentor@example.com',
            department='cse',
            year='',
            dob='1990-01-01',
            student_type='',
        )
        db.session.add(mentor)
        db.session.commit()
        mentor_id = mentor.id

    yield mentor_id

    with app.app_context():
        User.query.filter_by(register_number='MEN901').delete()
        db.session.commit()
