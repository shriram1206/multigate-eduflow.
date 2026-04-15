"""
tests/test_phase2_reset.py
──────────────────────────
Integration tests for the forgot password and reset password flow.
Ensures tokens are generated, emails are sent, and tokens expire/invalidate correctly.
"""

import pytest
from app.models import User, PasswordResetToken
from app.extensions import db
from werkzeug.security import check_password_hash
from unittest.mock import patch

def test_forgot_password_invalid_email(client, app):
    """Submitting an unregistered email should fail gracefully with generic message."""
    response = client.post('/forgot_password', data={'email': 'nobody@example.com'})
    assert response.status_code == 302
    
    with client.session_transaction() as sess:
        flashes = dict(sess.get('_flashes', []))
        # Ensure we show the same message regardless of whether the email exists
        assert "receive a reset link shortly" in flashes.get('info', '')


@patch('app.services.email_service.email_service.send_password_reset')
def test_forgot_password_valid_email(mock_send, client, app, seeded_student):
    """Submitting a valid email generates a token and sends email."""
    with app.app_context():
        user = User.query.get(seeded_student)
        email = user.email
    
    response = client.post('/forgot_password', data={'email': email})
    assert response.status_code == 302
    
    # Assert email was sent
    mock_send.assert_called_once()
    
    # Assert token was generated in DB
    with app.app_context():
        token = PasswordResetToken.query.filter_by(user_id=seeded_student, used=False).first()
        assert token is not None
        assert len(token.token) > 20


@patch('app.services.email_service.email_service.send_password_reset')
def test_reset_password_flow(mock_send, client, app, seeded_student):
    """Full end-to-end password reset flow."""
    with app.app_context():
        user = User.query.get(seeded_student)
        email = user.email
    
    # 1. Request reset
    client.post('/forgot_password', data={'email': email})
    
    with app.app_context():
        # Get the latest active token
        token_obj = PasswordResetToken.query.filter_by(user_id=seeded_student, used=False).first()
        assert token_obj is not None, "Token was not created or was immediately invalidated"
        token_str = token_obj.token
        
    # 2. Access reset page
    response = client.get(f'/reset_password/{token_str}')
    assert response.status_code == 200
    assert b"Set New Password" in response.data
    
    # 3. Submit new password
    response = client.post(f'/reset_password/{token_str}', data={
        'new_password': 'NewPassword!123',
        'confirm_password': 'NewPassword!123'
    })
    
    assert response.status_code == 302
    
    # 4. Verify password changed and token marked used
    with app.app_context():
        updated_user = User.query.get(seeded_student)
        assert check_password_hash(updated_user.password, 'NewPassword!123')
        
        updated_token = PasswordResetToken.query.filter_by(token=token_str).first()
        assert updated_token.used is True


def test_reset_password_invalid_token(client):
    """Using a fake token redirects to login with error."""
    response = client.get('/reset_password/fake-token-123')
    assert response.status_code == 302
    
    with client.session_transaction() as sess:
        flashes = dict(sess.get('_flashes', []))
        assert "expired" in flashes.get('danger', '')
