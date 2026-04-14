"""
tests/test_main.py
──────────────────
Integration tests for the /dashboard, /unified_request, and /status routes.

Safety guarantee
────────────────
• We use unittest.mock.patch to mock `db.session.execute` and `db.session.query`.
• This prevents executing PostgreSQL-specific raw SQL (e.g., generate_series, to_char)
  against our in-memory SQLite test database.
"""

import pytest
from unittest.mock import patch, MagicMock


# ════════════════════════════════════════════════════════════════════════
# /dashboard
# ════════════════════════════════════════════════════════════════════════

class TestDashboard:

    def test_dashboard_redirects_if_not_logged_in(self, client):
        resp = client.get('/dashboard', follow_redirects=False)
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '')

    @patch('app.main.routes.db.session.query')
    def test_dashboard_loads_for_student(self, mock_query, client, seeded_student):
        # Setup mocks to return empty/dummy data
        mock_query.return_value.filter.return_value.order_by.return_value.all.return_value = []
        mock_query.return_value.filter_by.return_value.count.return_value = 0
        mock_query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        # Login
        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})

        # Access dashboard
        resp = client.get('/dashboard')
        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'Dashboard' in html


# ════════════════════════════════════════════════════════════════════════
# /unified_request
# ════════════════════════════════════════════════════════════════════════

class TestUnifiedRequest:

    @patch('app.main.routes.db.session.execute')
    @patch('app.main.routes.db.session.add')
    @patch('app.main.routes.db.session.commit')
    def test_leave_request_submission(self, mock_commit, mock_add, mock_execute, client, seeded_student):
        # Mock the execute call that checks for leave limits
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [] # No violations
        mock_execute.return_value = mock_result

        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})

        resp = client.post('/unified_request', data={
            'request_type': 'leave',
            'type': 'Sick Leave',
            'reason': 'Feeling unwell',
            'from_date': '2030-01-01',
            'to_date': '2030-01-02'
        }, follow_redirects=True)

        assert resp.status_code == 200
        assert mock_add.called
        assert mock_commit.called

    def test_leave_request_invalid_date_range(self, client, seeded_student):
        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})

        resp = client.post('/unified_request', data={
            'request_type': 'leave',
            'type': 'Sick Leave',
            'reason': 'Feeling unwell',
            'from_date': '2030-01-02', # After to_date
            'to_date': '2030-01-01'
        }, follow_redirects=True)

        assert resp.status_code == 200
        html = resp.data.decode()
        assert 'danger' in html # Flash message class


# ════════════════════════════════════════════════════════════════════════
# /status
# ════════════════════════════════════════════════════════════════════════

class TestStatus:

    @patch('app.main.routes.db.session.query')
    def test_status_page_loads(self, mock_query, client, seeded_student):
        mock_query.return_value.filter.return_value.count.return_value = 0
        mock_query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})

        resp = client.get('/status')
        assert resp.status_code == 200
