"""
tests/test_phase2_audit.py
──────────────────────────
Tests for the audit logging subsystem and CSV generation.
Verifies that student submissions and staff actions log correctly,
and that CSV endpoints generate valid CSV data.
"""

import pytest
from app.models import User, Request, AuditLog
from app.extensions import db
from unittest.mock import patch


@pytest.fixture
def logged_in_student(client, seeded_student, app):
    with app.app_context():
        user = User.query.get(seeded_student)
        register_number = user.register_number
        
    client.post('/login', data={'register_number': register_number, 'password': 'Test@1234'})
    return seeded_student


@patch('app.email_service.notify_submitted')  # mock out email sender
def test_student_submission_creates_audit_log(mock_notify, client, logged_in_student, app):
    """When a student submits, an AuditLog entry must be generated."""
    
    response = client.post('/unified_request', data={
        'request_type': 'leave',
        'type': 'Sick',
        'reason': 'Feeling unwell',
        'from_date': '2024-01-01',
        'to_date': '2024-01-02'
    })
    
    assert response.status_code == 302
    
    with app.app_context():
        req = Request.query.filter_by(user_id=logged_in_student).first()
        assert req is not None
        
        logs = AuditLog.query.filter_by(request_id=req.id).all()
        assert len(logs) == 1
        assert logs[0].action == 'Submitted'
        assert logs[0].actor_role == 'Student'


def test_student_csv_export(client, logged_in_student, app):
    """Student should be able to download their own requests as CSV."""
    with app.app_context():
        # Inject a fake request
        user = User.query.get(logged_in_student)
        req = Request(
            user_id=user.id, student_name=user.name, department=user.department,
            request_type='Leave', type='Sick', reason='Sick leave test',
            from_date='2024-01-01', to_date='2024-01-02', status='Pending'
        )
        db.session.add(req)
        db.session.commit()
        
    response = client.get('/export_my_csv')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    
    data = response.data.decode('utf-8')
    assert 'ID,Request Type,Type,Reason' in data
    assert 'Sick leave test' in data


def test_hod_csv_export(client, app, seeded_student):
    """HOD should be able to download department requests as CSV."""
    # First, create and login as an HOD
    with app.app_context():
        hod = User(
            username='hod_cse', name='HOD CSE', role='HOD',
            password='test', register_number='HOD001',
            email='hod@example.com', dob='1980-01-01',
            department='cse'
        )
        db.session.add(hod)
        db.session.commit()
        hod_id = hod.id  # Capture ID before session close
    
    with client.session_transaction() as sess:
        sess['username'] = 'hod_cse'
        sess['name'] = 'HOD CSE'
        sess['role'] = 'HOD'
        sess['department'] = 'cse'
        sess['id'] = hod_id

    # Create a request for CSE
    with app.app_context():
        # Clean up first to avoid integrity issues with pre-seeded data if any exists
        Request.query.filter_by(user_id=seeded_student).delete()
        req = Request(
            user_id=seeded_student, student_name='Test', department='cse',
            request_type='Leave', type='Sick', reason='Export me',
            from_date='2024-01-01', to_date='2024-01-02', status='Approved'
        )
        db.session.add(req)
        db.session.commit()

    response = client.get('/export_csv?status=Approved')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    
    data = response.data.decode('utf-8')
    assert 'Student Name,Department,Request Type' in data
    assert 'Export me' in data
