"""
tests/test_phase2_email.py
──────────────────────────
Tests for the async email notification service.
Ensures that send_async delegates to the background thread correctly,
and that the notify helpers format the right subjects and recipients.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.email_service import send_async, notify_submitted, notify_status_changed, send_password_reset

@patch('app.email_service.threading.Thread')
def test_send_async_spawns_thread(mock_thread):
    """Test that send_async fires a background daemon thread."""
    mock_instance = MagicMock()
    mock_thread.return_value = mock_instance

    send_async('test@example.com', 'Subject', '<p>HTML</p>', 'Text')
    
    mock_thread.assert_called_once()
    args, kwargs = mock_thread.call_args
    assert kwargs.get('daemon') is True
    mock_instance.start.assert_called_once()


@patch('app.email_service.send_async')
def test_notify_submitted(mock_send):
    """Test student submission email formatting."""
    notify_submitted('student@example.com', 'Alice', 'Leave', 123)
    
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    to, subject, html, text = args
    
    assert to == 'student@example.com'
    assert 'Leave request submitted (#123)' in subject
    assert 'Alice' in html
    assert '#123' in html


@patch('app.email_service.send_async')
def test_notify_status_changed_approved(mock_send):
    """Test approval notification email formatting."""
    notify_status_changed('student@example.com', 'Alice', 'Leave', 123, 'Approved', 'Dr. Smith')
    
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    to, subject, html, text = args
    
    assert '✅' in subject
    assert 'Approved' in subject
    assert 'Dr. Smith' in html


@patch('app.email_service.send_async')
def test_notify_status_changed_rejected(mock_send):
    """Test rejection notification email with note."""
    notify_status_changed(
        'student@example.com', 'Alice', 'Permission', 456, 
        'Mentor Rejected', 'Prof. Jones', 'Invalid reason'
    )
    
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    to, subject, html, text = args
    
    assert '❌' in subject
    assert 'Mentor Rejected' in subject
    assert 'Invalid reason' in html


@patch('app.email_service.send_async')
def test_send_password_reset(mock_send):
    """Test password reset email formatting."""
    send_password_reset('user@example.com', 'Bob', 'http://reset.link')
    
    mock_send.assert_called_once()
    args, kwargs = mock_send.call_args
    to, subject, html, text = args
    
    assert 'Password Reset Request' in subject
    assert 'http://reset.link' in html
    assert '30 minutes' in html
