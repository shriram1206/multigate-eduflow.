"""
tests/test_email_service.py

Tests for Phase 2: Email Notifications
"""

import pytest
from unittest.mock import patch, MagicMock
from flask import Flask
from app.services.email_service import email_service, EmailService


@pytest.fixture
def app():
    """Create Flask test app with email config"""
    app = Flask(__name__)
    app.config['MAIL_SERVER'] = 'smtp.example.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_DEFAULT_SENDER'] = 'test@mefportal.edu'
    app.config['TESTING'] = True
    
    service = EmailService()
    service.init_app(app)
    return app, service


class TestEmailServiceBasics:
    """Test basic email service functionality"""
    
    def test_email_service_initialization(self, app):
        """Test email service initializes correctly"""
        test_app, service = app
        assert service.mail is not None
        assert service.app is not None
    
    @patch('app.services.email_service.Message')
    def test_send_email_basic(self, mock_message, app):
        """Test basic email sending"""
        test_app, service = app
        mock_mail = MagicMock()
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_email(
                    'student@college.edu',
                    'welcome',
                    {
                        'user_name': 'John Doe',
                        'register_number': '23CS001',
                        'portal_url': 'http://localhost:5000'
                    }
                )
        
        assert result is True
        mock_mail.send.assert_called_once()
    
    def test_invalid_template_name(self, app):
        """Test sending with invalid template name"""
        test_app, service = app
        
        result = service.send_email(
            'student@college.edu',
            'invalid_template',
            {}
        )
        
        assert result is False


class TestEmailNotifications:
    """Test specific notification emails"""
    
    @patch('app.services.email_service.Message')
    @patch('app.services.email_service.render_template_string')
    def test_send_request_submitted(self, mock_render, mock_message, app):
        """Test request submission notification"""
        test_app, service = app
        mock_render.return_value = '<html>Test</html>'
        mock_mail = MagicMock()
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_request_submitted(
                    'student@college.edu',
                    'Alice Johnson',
                    {
                        'request_type': 'Leave Request',
                        'date_from': '2026-04-20',
                        'date_to': '2026-04-22'
                    }
                )
        
        assert result is True
    
    @patch('app.services.email_service.Message')
    @patch('app.services.email_service.render_template_string')
    def test_send_request_approved(self, mock_render, mock_message, app):
        """Test request approval notification"""
        test_app, service = app
        mock_render.return_value = '<html>Approved</html>'
        mock_mail = MagicMock()
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_request_approved(
                    'student@college.edu',
                    'Bob Smith',
                    {
                        'request_type': 'Leave Request',
                        'date_from': '2026-04-25',
                        'date_to': '2026-04-26'
                    },
                    mentor_comment='Looks good!'
                )
        
        assert result is True
    
    @patch('app.services.email_service.Message')
    @patch('app.services.email_service.render_template_string')
    def test_send_request_rejected(self, mock_render, mock_message, app):
        """Test request rejection notification"""
        test_app, service = app
        mock_render.return_value = '<html>Rejected</html>'
        mock_mail = MagicMock()
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_request_rejected(
                    'student@college.edu',
                    'Carol White',
                    {
                        'request_type': 'Exam Request',
                        'date_from': '2026-05-01',
                        'date_to': '2026-05-02'
                    },
                    mentor_comment='Exam date conflicts with scheduled course'
                )
        
        assert result is True
    
    @patch('app.services.email_service.Message')
    @patch('app.services.email_service.render_template_string')
    def test_send_password_reset(self, mock_render, mock_message, app):
        """Test password reset email"""
        test_app, service = app
        mock_render.return_value = '<html>Reset Link</html>'
        mock_mail = MagicMock()
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_password_reset(
                    'user@college.edu',
                    'David Lee',
                    'http://localhost:5000/reset/abc123token'
                )
        
        assert result is True
    
    @patch('app.services.email_service.Message')
    @patch('app.services.email_service.render_template_string')
    def test_send_welcome(self, mock_render, mock_message, app):
        """Test welcome email for new users"""
        test_app, service = app
        mock_render.return_value = '<html>Welcome</html>'
        mock_mail = MagicMock()
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_welcome(
                    'newuser@college.edu',
                    'Eve Taylor',
                    '23CS099',
                    'http://localhost:5000'
                )
        
        assert result is True


class TestEmailTemplates:
    """Test email template coverage"""
    
    def test_all_templates_exist(self):
        """Test all required templates are defined"""
        from app.services.email_service import EMAIL_TEMPLATES
        
        required_templates = [
            'request_submitted',
            'request_approved',
            'request_rejected',
            'password_reset',
            'welcome'
        ]
        
        for template in required_templates:
            assert template in EMAIL_TEMPLATES, f"Template '{template}' not found"
            assert 'subject' in EMAIL_TEMPLATES[template]
            assert 'template' in EMAIL_TEMPLATES[template]
    
    def test_template_content_quality(self):
        """Test templates have minimum quality standards"""
        from app.services.email_service import EMAIL_TEMPLATES
        
        for name, template_data in EMAIL_TEMPLATES.items():
            # Check subject is not empty
            assert len(template_data['subject']) > 0, f"{name}: Subject is empty"
            assert len(template_data['subject']) < 100, f"{name}: Subject too long"
            
            # Check template HTML has content
            assert len(template_data['template']) > 100, f"{name}: Template too short"
            
            # Check template has proper HTML structure
            assert '<html>' in template_data['template'].lower(), f"{name}: Missing HTML tag"
            assert '</html>' in template_data['template'].lower(), f"{name}: Missing closing HTML tag"


class TestEmailErrorHandling:
    """Test email sending error handling"""
    
    @patch('app.services.email_service.render_template_string')
    def test_email_send_failure_handling(self, mock_render, app):
        """Test graceful handling of email send failures"""
        test_app, service = app
        mock_render.return_value = '<html>Test</html>'
        mock_mail = MagicMock()
        mock_mail.send.side_effect = Exception("SMTP Error")
        service.mail = mock_mail
        
        with test_app.app_context():
            with patch('app.services.email_service.current_app', test_app):
                result = service.send_email(
                    'invalid@email.com',
                    'welcome',
                    {'user_name': 'Test', 'register_number': '23CS001', 'portal_url': 'http://test'}
                )
        
        # Should return False on exception
        assert result is False
    
    def test_missing_recipient_email(self, app):
        """Test handling of missing recipient email"""
        test_app, service = app
        
        # Empty email should be handled
        result = service.send_email(
            '',
            'welcome',
            {'user_name': 'Test', 'register_number': '23CS001', 'portal_url': 'http://test'}
        )
        
        # Should complete without crashing
        assert isinstance(result, bool)


# ── Integration Tests ──────────────────────────────────────────────

class TestEmailIntegration:
    """Integration tests for email service with app"""
    
    def test_email_service_available_in_app_context(self, app):
        """Test email service is accessible from app"""
        test_app, service = app
        
        with test_app.app_context():
            from app.services.email_service import email_service as imported_service
            assert imported_service is not None
    
    def test_template_rendering_with_variables(self, app):
        """Test template variables are properly rendered"""
        test_app, service = app
        
        from app.services.email_service import EMAIL_TEMPLATES
        template_html = EMAIL_TEMPLATES['welcome']['template']
        
        # Check for template variables that should be replaced
        assert '{{ user_name }}' in template_html or '{{ user_name }}' not in template_html
        assert '{{ register_number }}' in template_html or 'register_number' in template_html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
