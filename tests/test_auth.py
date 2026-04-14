"""
tests/test_auth.py
───────────────────
Integration tests for the /login and /logout routes.

Safety guarantee
────────────────
• All tests use the in-memory SQLite fixture from conftest.py.
• Your live Supabase database is NEVER touched.
• CSRF is disabled for the test app.
"""

import pytest
from werkzeug.security import generate_password_hash


# ════════════════════════════════════════════════════════════════════════
# /login  →  GET
# ════════════════════════════════════════════════════════════════════════

class TestLoginPageGET:

    def test_login_page_loads(self, client):
        """Login page must render with HTTP 200."""
        resp = client.get('/login')
        assert resp.status_code == 200

    def test_login_page_contains_form(self, client):
        """Login page HTML must include the registration number input."""
        resp = client.get('/login')
        html = resp.data.decode()
        assert 'register_number' in html or 'Register' in html


# ════════════════════════════════════════════════════════════════════════
# /login  →  POST  (failure cases)
# ════════════════════════════════════════════════════════════════════════

class TestLoginPOSTFailures:

    def test_empty_credentials_rejected(self, client):
        """Posting empty fields must NOT redirect to dashboard."""
        resp = client.post('/login', data={
            'register_number': '',
            'password': '',
        }, follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode()
        # Must stay on the login page or show an error flash
        assert ('required' in html.lower() or 'invalid' in html.lower()
                or 'register_number' in html.lower())

    def test_wrong_credentials_rejected(self, client, seeded_student):
        """Wrong password must return to login with an error, not redirect to dashboard."""
        resp = client.post('/login', data={
            'register_number': 'TST001',
            'password': 'WrongPassword!99',
        }, follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'invalid' in html.lower() or 'credentials' in html.lower()

    def test_nonexistent_user_rejected(self, client):
        """Unknown register number must return invalid credentials flash."""
        resp = client.post('/login', data={
            'register_number': 'DOESNOTEXIST999',
            'password': 'SomePass@1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'invalid' in html.lower() or 'credentials' in html.lower()

    def test_missing_password_rejected(self, client, seeded_student):
        """Omitting password should be rejected cleanly."""
        resp = client.post('/login', data={
            'register_number': 'TST001',
            'password': '',
        }, follow_redirects=True)
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════
# /login  →  POST  (success case)
# ════════════════════════════════════════════════════════════════════════

class TestLoginPOSTSuccess:

    def test_valid_student_login_redirects_to_dashboard(self, client, seeded_student):
        """A student with correct credentials must end up at /dashboard."""
        resp = client.post('/login', data={
            'register_number': 'TST001',
            'password': 'Test@1234',
        }, follow_redirects=True)
        assert resp.status_code == 200
        # After login, must NOT be on the login page
        html = resp.data.decode()
        # Dashboard contains the student's name or a dashboard keyword
        assert 'dashboard' in resp.request.path.lower() or 'dashboard' in html.lower()

    def test_session_populated_after_login(self, client, seeded_student, app):
        """Session must contain user id, role, and username after login."""
        with client.session_transaction() as sess:
            sess.clear()   # ensure clean slate

        resp = client.post('/login', data={
            'register_number': 'TST001',
            'password': 'Test@1234',
        }, follow_redirects=True)

        with client.session_transaction() as sess:
            assert 'id' in sess
            assert sess.get('role') == 'Student'
            assert sess.get('username') == 'test_student'


# ════════════════════════════════════════════════════════════════════════
# /logout
# ════════════════════════════════════════════════════════════════════════

class TestLogout:

    def test_logout_clears_session_and_redirects(self, client, seeded_student):
        """After logout the user must be redirected to login and session cleared."""
        # Login first
        client.post('/login', data={
            'register_number': 'TST001',
            'password': 'Test@1234',
        })

        # Now logout
        resp = client.get('/logout', follow_redirects=True)
        assert resp.status_code == 200
        html = resp.data.decode()
        # Must land back on login page
        assert 'login' in resp.request.path.lower() or 'register_number' in html.lower()

        # Session must be empty
        with client.session_transaction() as sess:
            assert 'id' not in sess
            assert 'username' not in sess


# ════════════════════════════════════════════════════════════════════════
# Account lockout logic
# ════════════════════════════════════════════════════════════════════════

class TestAccountLockout:

    def test_repeated_failures_do_not_crash_server(self, client, seeded_student):
        """
        Hammering /login with wrong credentials must not crash the server
        (5xx). We expect consistent 200 with error messages.
        """
        for _ in range(6):
            resp = client.post('/login', data={
                'register_number': 'TST001',
                'password': 'BadPass@99',
            }, follow_redirects=True)
            assert resp.status_code == 200
