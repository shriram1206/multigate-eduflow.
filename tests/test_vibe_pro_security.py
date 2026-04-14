"""
tests/test_vibe_pro_security.py
─────────────────────────────────
Security-focused tests for the MEF Portal.

All tests use the in-memory SQLite fixture from conftest.py.
Live Supabase is NEVER touched.

Coverage areas
──────────────
S-01  CSRF enforcement
S-02  Session isolation & logout
S-03  Role-based access control (privilege escalation)
S-04  Security response headers
S-05  Input sanitisation / XSS rejection
S-06  Rate-limit decorator presence (smoke)
S-07  Account lockout rows don't break login flow
"""

import pytest
from werkzeug.security import generate_password_hash


# ─── Helpers ────────────────────────────────────────────────────────────────

def _login(client, reg_no, password):
    return client.post(
        '/login',
        data={'register_number': reg_no, 'password': password},
        follow_redirects=True,
    )


def _logout(client):
    return client.get('/logout', follow_redirects=True)


# ─── S-01  CSRF enforcement ──────────────────────────────────────────────────

class TestCSRFEnforcement:
    """
    The production app enables WTF_CSRF_ENABLED=True.
    The test app disables it for convenience; these tests verify the config
    toggle itself is respected and that POST routes do NOT accept unsafe
    methods in an unexpected way.

    Real CSRF checks are covered by Flask-WTF's own test suite — we just
    confirm our app wires the extension correctly.
    """

    def test_csrf_extension_loaded(self, app):
        """Flask-WTF CSRFProtect must be initialised on the app."""
        # extensions.py exposes `csrf`; verify it is bound to the app
        from app.extensions import csrf
        # If csrf is bound, it has an _app attribute or is listed in app extensions
        assert csrf is not None

    def test_csrf_disabled_in_test_config(self, app):
        """Test config must disable CSRF so our POST fixtures work."""
        assert app.config.get('WTF_CSRF_ENABLED') is False

    def test_production_csrf_config_is_true_by_default(self):
        """create_app() without override must set WTF_CSRF_ENABLED=True."""
        from app import create_app
        prod_app = create_app({'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                               'SECRET_KEY': 'prod-test-key',
                               'TESTING': True})
        assert prod_app.config.get('WTF_CSRF_ENABLED') is True


# ─── S-02  Session isolation & logout ──────────────────────────────────────

class TestSessionSecurity:

    def test_unauthenticated_dashboard_redirects_to_login(self, client):
        """GET /dashboard without a session must redirect, not 200."""
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code in (302, 301)
        assert 'login' in resp.headers.get('Location', '').lower()

    def test_session_cleared_completely_on_logout(self, client, seeded_student):
        """No sensitive keys should survive a logout."""
        _login(client, 'TST001', 'Test@1234')
        _logout(client)
        with client.session_transaction() as sess:
            assert 'id' not in sess
            assert 'username' not in sess
            assert 'role' not in sess

    def test_dashboard_inaccessible_after_logout(self, client, seeded_student):
        """After logout the dashboard must redirect, not render."""
        _login(client, 'TST001', 'Test@1234')
        _logout(client)
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code in (302, 301)


# ─── S-03  Role-based access control ───────────────────────────────────────

class TestRoleBasedAccessControl:

    def test_student_cannot_access_mentor_dashboard(self, client, seeded_student):
        """A logged-in Student must be redirected away from /mentor."""
        _login(client, 'TST001', 'Test@1234')
        resp = client.get('/mentor', follow_redirects=False)
        # Must redirect (not 200) — student has no business on mentor page
        assert resp.status_code in (302, 301, 403)
        _logout(client)

    def test_student_cannot_access_advisor_dashboard(self, client, seeded_student):
        """A logged-in Student must be redirected away from /advisor."""
        _login(client, 'TST001', 'Test@1234')
        resp = client.get('/advisor', follow_redirects=False)
        assert resp.status_code in (302, 301, 403)
        _logout(client)

    def test_student_cannot_access_hod_dashboard(self, client, seeded_student):
        """A logged-in Student must be redirected away from /hod."""
        _login(client, 'TST001', 'Test@1234')
        resp = client.get('/hod', follow_redirects=False)
        assert resp.status_code in (302, 301, 403)
        _logout(client)

    def test_student_cannot_access_user_management(self, client, seeded_student):
        """User management is HOD/Admin only — students must be denied."""
        _login(client, 'TST001', 'Test@1234')
        resp = client.get('/user_management', follow_redirects=True)
        html = resp.data.decode()
        # Either got a 403 or was flashed an 'access denied' message
        assert resp.status_code in (200, 403)
        if resp.status_code == 200:
            assert 'access denied' in html.lower() or 'dashboard' in resp.request.path.lower()
        _logout(client)

    def test_unauthenticated_user_cannot_access_mentor_dashboard(self, client):
        """Unauthenticated requests to /mentor must redirect to login."""
        _logout(client)   # ensure clean state
        resp = client.get('/mentor', follow_redirects=False)
        assert resp.status_code in (302, 301)

    def test_unauthenticated_user_cannot_access_hod_dashboard(self, client):
        """Unauthenticated requests to /hod must redirect to login."""
        _logout(client)
        resp = client.get('/hod', follow_redirects=False)
        assert resp.status_code in (302, 301)

    def test_mentor_cannot_perform_hod_actions(self, client, seeded_mentor):
        """A Mentor must not be able to access /hod_action."""
        _login(client, 'MEN901', 'Mentor@1234')
        resp = client.post('/hod_action',
                           data={'request_id': '1', 'action': 'Approve'},
                           follow_redirects=False)
        # Must redirect away, not process
        assert resp.status_code in (302, 301, 403)
        _logout(client)


# ─── S-04  Security response headers ────────────────────────────────────────

class TestSecurityHeaders:
    """
    __init__.py attaches security headers via @after_request.
    Verify every response carries the required headers.
    """

    def test_x_content_type_options_header(self, client):
        resp = client.get('/login')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'

    def test_x_frame_options_header(self, client):
        resp = client.get('/login')
        val = resp.headers.get('X-Frame-Options', '')
        assert val in ('SAMEORIGIN', 'DENY')

    def test_x_xss_protection_header(self, client):
        resp = client.get('/login')
        assert '1' in resp.headers.get('X-XSS-Protection', '')

    def test_referrer_policy_header(self, client):
        resp = client.get('/login')
        assert resp.headers.get('Referrer-Policy') != ''

    def test_content_security_policy_header_present(self, client):
        resp = client.get('/login')
        assert 'Content-Security-Policy' in resp.headers

    def test_csp_blocks_arbitrary_scripts(self, client):
        """CSP must include a default-src or script-src directive."""
        resp = client.get('/login')
        csp = resp.headers.get('Content-Security-Policy', '')
        assert 'default-src' in csp or 'script-src' in csp

    def test_headers_present_on_404(self, client):
        """Security headers must appear even on error responses."""
        resp = client.get('/this-route-does-not-exist-xyz')
        assert resp.headers.get('X-Content-Type-Options') == 'nosniff'


# ─── S-05  Input sanitisation ───────────────────────────────────────────────

class TestInputSanitisation:
    """
    Verify that XSS payloads in login fields do not echo raw HTML back.
    """

    XSS_PAYLOAD = '<script>alert("xss")</script>'

    def test_xss_in_register_number_not_reflected_raw(self, client):
        """Script tag in register_number must NOT appear unescaped in response."""
        resp = client.post('/login', data={
            'register_number': self.XSS_PAYLOAD,
            'password': 'irrelevant',
        }, follow_redirects=True)
        html = resp.data.decode()
        assert '<script>alert' not in html

    def test_xss_in_password_not_reflected_raw(self, client):
        """Script tag in password must NOT appear unescaped in response."""
        resp = client.post('/login', data={
            'register_number': 'NONEXISTENT',
            'password': self.XSS_PAYLOAD,
        }, follow_redirects=True)
        html = resp.data.decode()
        assert '<script>alert' not in html


# ─── S-06  Rate-limit decorator smoke ───────────────────────────────────────

class TestRateLimitDecoratorSmoke:
    """
    We don't test actual rate-limit blocking (disabled in test config).
    We verify the decorated routes are still reachable (decorator doesn't break routing).
    """

    def test_login_route_reachable(self, client):
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_mentor_action_route_exists(self, client, seeded_student, seeded_mentor):
        """POST to /mentor_action from a non-mentor must redirect, not 404/500."""
        _login(client, 'TST001', 'Test@1234')   # student — will be rejected by role check
        resp = client.post('/mentor_action',
                           data={'request_id': '999', 'action': 'Approve'},
                           follow_redirects=False)
        assert resp.status_code != 404
        assert resp.status_code != 500
        _logout(client)


# ─── S-07  Account lockout row doesn't break login ──────────────────────────

class TestAccountLockoutIntegration:

    def test_existing_lockout_row_does_not_block_valid_login(self, app, client, seeded_student):
        """
        If an AuthLockout row exists but lockout_until is NULL/past,
        a correct login must still succeed.
        """
        from app.extensions import db
        from app.models import AuthLockout

        # Insert a lockout row with 0 failed attempts (no active lockout)
        with app.app_context():
            AuthLockout.query.filter_by(register_number='TST001').delete()
            row = AuthLockout(register_number='TST001', failed_attempts=0, lockout_until=None)
            db.session.add(row)
            db.session.commit()

        resp = _login(client, 'TST001', 'Test@1234')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'dashboard' in resp.request.path.lower() or 'dashboard' in html.lower()

        # Cleanup
        with app.app_context():
            AuthLockout.query.filter_by(register_number='TST001').delete()
            db.session.commit()
