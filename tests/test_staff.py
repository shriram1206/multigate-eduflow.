"""
tests/test_staff.py
───────────────────
Integration tests for the staff routes ensuring RBAC (Role Based Access Control)
is enforced accurately.
"""

import pytest
from unittest.mock import patch

# ════════════════════════════════════════════════════════════════════════
# Role checks
# ════════════════════════════════════════════════════════════════════════

class TestStaffAccessControl:

    def test_student_cannot_access_mentor_dashboard(self, client, seeded_student):
        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})

        resp = client.get('/mentor', follow_redirects=False)
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '')

    def test_student_cannot_access_advisor_dashboard(self, client, seeded_student):
        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})
        
        resp = client.get('/advisor', follow_redirects=False)
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '')

    def test_student_cannot_access_hod_dashboard(self, client, seeded_student):
        client.post('/login', data={'register_number': 'TST001', 'password': 'Test@1234'})
        
        resp = client.get('/hod', follow_redirects=False)
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '')

    @patch('app.staff.routes.db.session.execute')
    def test_mentor_can_access_mentor_dashboard(self, mock_execute, client, seeded_mentor):
        # Setup mock for the mentor dashboard query
        mock_execute.return_value.fetchall.return_value = []

        client.post('/login', data={'register_number': 'MEN901', 'password': 'Mentor@1234'})

        resp = client.get('/mentor', follow_redirects=True)
        assert resp.status_code == 200
        # Mentor dashboard should have something related to the mentor
        html = resp.data.decode().lower()
        assert 'mentor' in html

    def test_mentor_cannot_access_hod_dashboard(self, client, seeded_mentor):
        client.post('/login', data={'register_number': 'MEN901', 'password': 'Mentor@1234'})

        resp = client.get('/hod', follow_redirects=False)
        assert resp.status_code == 302
        assert 'login' in resp.headers.get('Location', '')
