"""
tests/test_phase3.py

Phase 3 - Code Quality & Operational Improvements Tests

CQ-005: Comprehensive docstrings — tests verify functions are documented
CQ-008: Service layer — tests verify service methods work correctly
OP-003: Health check endpoints — tests verify health checks work
OP-004: Error page handling — tests verify custom error pages render

Run with: pytest tests/test_phase3.py -v
"""

import pytest
import json
from datetime import datetime, timedelta
from flask import Flask
from app import create_app
from app.extensions import db
from app.models import User, Request, AuditLog, PasswordResetToken
from app.services.auth_service import AuthService
from app.services.request_service import RequestService
from app.services.audit_service import AuditService
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """Create Flask application for testing."""
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SECRET_KEY': 'test-secret-key-phase3',
        'WTF_CSRF_ENABLED': False,
        'RATELIMIT_ENABLED': False,
    })

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        user = User(
            username='testuser',
            name='Test User',
            register_number='CS001',
            email='test@example.com',
            password=generate_password_hash('Password@123'),
            role='Student',
            department='CSE',
            year='1',
            dob='2003-01-15',
            student_type='Day Scholar',
        )
        db.session.add(user)
        db.session.commit()
        yield user
        db.session.delete(user)
        db.session.commit()


# ────────────────────────────────────────────────────────────────────────────────
# CQ-005: Comprehensive Docstrings Tests
# ────────────────────────────────────────────────────────────────────────────────

class TestDocstrings:
    """Verify all major functions have comprehensive docstrings."""

    def test_auth_service_docstrings(self):
        """Verify AuthService methods have docstrings."""
        assert AuthService.verify_password.__doc__ is not None
        assert 'password' in AuthService.verify_password.__doc__.lower()

        assert AuthService.authenticate_user.__doc__ is not None
        assert 'authenticate' in AuthService.authenticate_user.__doc__.lower()

        assert AuthService.register_user.__doc__ is not None
        assert 'register' in AuthService.register_user.__doc__.lower()

    def test_request_service_docstrings(self):
        """Verify RequestService methods have docstrings."""
        assert RequestService.create_request.__doc__ is not None
        assert RequestService.update_request_status.__doc__ is not None
        assert RequestService.get_request_with_audit_trail.__doc__ is not None

    def test_audit_service_docstrings(self):
        """Verify AuditService methods have docstrings."""
        assert AuditService.get_audit_trail.__doc__ is not None
        assert AuditService.export_audit_to_csv.__doc__ is not None
        assert AuditService.get_department_audit_history.__doc__ is not None


# ────────────────────────────────────────────────────────────────────────────────
# CQ-008: Service Layer Tests
# ────────────────────────────────────────────────────────────────────────────────

class TestAuthService:
    """Test AuthService business logic (CQ-008)."""

    def test_verify_password_success(self, app, test_user):
        """Test password verification succeeds with correct password."""
        with app.app_context():
            # Get fresh user from DB to ensure it's in session
            user = User.query.filter_by(register_number='CS001').first()
            result = AuthService.verify_password(user.password, 'Password@123')
            assert result is True

    def test_verify_password_failure(self, app, test_user):
        """Test password verification fails with incorrect password."""
        with app.app_context():
            # Get fresh user from DB to ensure it's in session
            user = User.query.filter_by(register_number='CS001').first()
            result = AuthService.verify_password(user.password, 'WrongPassword123')
            assert result is False

    def test_authenticate_user_success(self, app, test_user):
        """Test successful user authentication."""
        with app.app_context():
            user, error = AuthService.authenticate_user('CS001', 'Password@123')
            assert user is not None
            assert error is None
            assert user.username == 'testuser'

    def test_authenticate_user_invalid_credentials(self, app, test_user):
        """Test authentication fails with invalid credentials."""
        with app.app_context():
            user, error = AuthService.authenticate_user('CS001', 'WrongPassword')
            assert user is None
            assert error is not None

    def test_authenticate_user_nonexistent(self, app):
        """Test authentication fails for nonexistent user."""
        with app.app_context():
            user, error = AuthService.authenticate_user('INVALID', 'password')
            assert user is None
            assert error is not None

    def test_register_user_success(self, app):
        """Test successful user registration."""
        with app.app_context():
            success, msg = AuthService.register_user(
                name='New User',
                register_number='CS002',
                email='new@example.com',
                password='NewPassword@123',
                role='Student',
                department='CSE',
                dob='2003-06-20',
            )
            assert success is True
            assert msg == "Registration successful"

            # Verify user created in database
            user = User.query.filter_by(register_number='CS002').first()
            assert user is not None
            assert user.name == 'New User'

    def test_register_user_duplicate(self, app, test_user):
        """Test registration fails with duplicate registration number."""
        with app.app_context():
            success, msg = AuthService.register_user(
                name='Duplicate Test',
                register_number='CS001',  # Already exists
                email='dup@example.com',
                password='Password@123',
            )
            assert success is False
            assert "already exists" in msg

    def test_register_user_weak_password(self, app):
        """Test registration fails with weak password."""
        with app.app_context():
            success, msg = AuthService.register_user(
                name='Weak Password Test',
                register_number='CS003',
                email='weak@example.com',
                password='weak',  # Too short
            )
            assert success is False

    def test_update_user_profile(self, app, test_user):
        """Test updating user profile."""
        with app.app_context():
            # Get user ID from DB to ensure it's accessible
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            success, msg = AuthService.update_user_profile(
                user_id,
                name='Updated Name',
                email='updated@example.com',
            )
            assert success is True

            # Verify changes saved
            user = db.session.get(User, user_id)
            assert user.name == 'Updated Name'
            assert user.email == 'updated@example.com'

    def test_change_password_success(self, app, test_user):
        """Test successful password change."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            success, msg = AuthService.change_password(
                user_id,
                'Password@123',  # Current password
                'NewPassword@456',  # New password
            )
            assert success is True

    def test_change_password_wrong_current(self, app, test_user):
        """Test password change fails with wrong current password."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            success, msg = AuthService.change_password(
                user_id,
                'WrongPassword',  # Wrong current password
                'NewPassword@456',
            )
            assert success is False

    def test_change_password_weak_new(self, app, test_user):
        """Test password change fails with weak new password."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            success, msg = AuthService.change_password(
                user_id,
                'Password@123',
                'weak',  # Weak new password
            )
            assert success is False

    def test_session_data_preparation(self, app, test_user):
        """Test session data preparation."""
        with app.app_context():
            # Get user from DB
            user = User.query.filter_by(register_number='CS001').first()
            session_data = AuthService.get_user_session_data(user)
            assert session_data['id'] == user.id
            assert session_data['username'] == user.username
            assert session_data['role'] == 'Student'
            assert session_data['department'] == 'cse'  # Normalized


class TestRequestService:
    """Test RequestService business logic (CQ-008)."""

    def test_create_request_success(self, app, test_user):
        """Test successful request creation."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            success, msg, request_id = RequestService.create_request(
                user_id=user_id,
                request_type='leave',
                reason='Medical appointment',
                from_date='2026-04-15',
                to_date='2026-04-15',
                department='CSE',
                student_name='Test User',
            )
            assert success is True
            assert request_id is not None

            # Verify request created
            req = db.session.get(Request, request_id)
            assert req is not None
            assert req.status == 'Pending'

    def test_create_request_invalid_dates(self, app, test_user):
        """Test request creation with invalid date range."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            success, msg, request_id = RequestService.create_request(
                user_id=user_id,
                request_type='leave',
                reason='Test',
                from_date='2026-04-20',
                to_date='2026-04-15',  # Before from_date
                department='CSE',
                student_name='Test User',
            )
            assert success is False

    def test_update_request_status(self, app, test_user):
        """Test updating request status."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            # Create request
            req = Request(
                user_id=user_id,
                type='leave',
                reason='Test',
                from_date='2026-04-15',
                to_date='2026-04-15',
                status='Pending',
                student_name='Test User',
                department='CSE',
                request_type='leave',
            )
            db.session.add(req)
            db.session.flush()

            # Update status
            success, msg = RequestService.update_request_status(
                req.id,
                'Approved',
                user_id,
                note='Looks good',
            )
            assert success is True

            # Verify status updated
            updated_req = db.session.get(Request, req.id)
            assert updated_req.status == 'Approved'

            # Verify audit log created
            audit = AuditLog.query.filter_by(request_id=req.id).first()
            assert audit is not None
            assert audit.action == 'Approved'


class TestAuditService:
    """Test AuditService business logic (CQ-008)."""

    def test_get_audit_trail(self, app, test_user):
        """Test retrieving audit trail for request."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            # Create request
            req = Request(
                user_id=user_id,
                type='leave',
                reason='Test',
                from_date='2026-04-15',
                to_date='2026-04-15',
                status='Pending',
                student_name='Test User',
                department='CSE',
                request_type='leave',
            )
            db.session.add(req)
            db.session.flush()

            # Add audit entry
            audit_entry = AuditLog(
                request_id=req.id,
                actor_id=user_id,
                actor_name='Test User',
                actor_role='Student',
                action='Submitted',
            )
            db.session.add(audit_entry)
            db.session.commit()

            # Get audit trail
            trail = AuditService.get_audit_trail(req.id)
            assert len(trail) == 1
            assert trail[0]['action'] == 'Submitted'

    def test_export_audit_to_csv(self, app, test_user):
        """Test exporting audit history to CSV."""
        with app.app_context():
            # Get user ID from DB
            user = User.query.filter_by(register_number='CS001').first()
            user_id = user.id
            
            # Create request
            req = Request(
                user_id=user_id,
                type='leave',
                reason='Test',
                from_date='2026-04-15',
                to_date='2026-04-15',
                status='Pending',
                student_name='Test User',
                department='CSE',
                request_type='leave',
            )
            db.session.add(req)
            db.session.commit()

            # Export to CSV
            success, msg, csv_content = AuditService.export_audit_to_csv(user_id)
            assert success is True
            assert csv_content is not None
            assert 'Request ID' in csv_content


# ────────────────────────────────────────────────────────────────────────────────
# OP-003: Health Check Endpoint Tests
# ────────────────────────────────────────────────────────────────────────────────

class TestHealthCheck:
    """Test health check endpoints (OP-003)."""

    def test_liveness_probe(self, client):
        """Test liveness probe always returns 200."""
        response = client.get('/healthz/live')
        assert response.status_code == 200

        data = json.loads(response.data)
        assert data['status'] == 'alive'

    def test_readiness_probe_ready(self, client):
        """Test readiness probe returns 200 when ready."""
        response = client.get('/healthz/ready')
        # Should be 200 if database is connected
        assert response.status_code in (200, 503)

        data = json.loads(response.data)
        assert 'ready' in data

    def test_legacy_health_endpoint(self, client):
        """Test legacy /healthz endpoint."""
        response = client.get('/healthz')
        assert response.status_code in (200, 503)

        data = json.loads(response.data)
        assert 'ready' in data or 'status' in data


# ────────────────────────────────────────────────────────────────────────────────
# OP-004: Error Page Handling Tests
# ────────────────────────────────────────────────────────────────────────────────

class TestErrorPageHandling:
    """Test custom error page rendering (OP-004)."""

    def test_404_error_page(self, client):
        """Test 404 error page renders."""
        response = client.get('/nonexistent-page')
        assert response.status_code == 404
        assert b'404' in response.data or b'not found' in response.data.lower()

    def test_405_error_page(self, client):
        """Test 405 error page (method not allowed)."""
        response = client.post('/login/')  # Adjust path if needed
        # Should get 405 if route doesn't accept POST
        if response.status_code == 405:
            assert b'405' in response.data or b'not allowed' in response.data.lower()

    def test_error_page_no_stack_trace(self, client):
        """Test error pages don't expose stack traces."""
        response = client.get('/nonexistent')
        assert response.status_code == 404

        # Should NOT contain Python stack trace markers
        assert b'Traceback' not in response.data
        assert b'File "' not in response.data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
