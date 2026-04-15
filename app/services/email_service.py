"""
Email Service for MEF Portal

Handles all email sending operations:
- Request notifications (submitted, approved, rejected)
- Password reset tokens
- Welcome emails
- Admin alerts
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from flask import render_template_string, current_app
from flask_mail import Mail, Message
import os

logger = logging.getLogger(__name__)

# Email templates (inline HTML)
EMAIL_TEMPLATES = {
    "request_submitted": {
        "subject": "📋 Request Submitted - MEF Portal",
        "template": """
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Request Submitted Successfully</h2>
                <p>Hi <strong>{{ student_name }}</strong>,</p>
                <p>Your request has been submitted successfully and is now pending approval.</p>
                <div style="background: #f5f5f5; padding: 15px; border-left: 4px solid #3498db;">
                    <p><strong>Request Details:</strong></p>
                    <ul>
                        <li><strong>Type:</strong> {{ request_type }}</li>
                        <li><strong>From:</strong> {{ date_from }}</li>
                        <li><strong>To:</strong> {{ date_to }}</li>
                        <li><strong>Status:</strong> <span style="color: #f39c12;">Pending</span></li>
                    </ul>
                </div>
                <p>Your mentor will review and respond shortly. You can track the status in your dashboard.</p>
                <p style="color: #7f8c8d; font-size: 12px;">
                    © MEF Portal | Generated on {{ timestamp }}
                </p>
            </div>
        </body>
        </html>
        """
    },
    "request_approved": {
        "subject": "✅ Request Approved - MEF Portal",
        "template": """
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #27ae60;">Request Approved!</h2>
                <p>Hi <strong>{{ student_name }}</strong>,</p>
                <p>Great news! Your request has been <strong style="color: #27ae60;">APPROVED</strong> by your mentor.</p>
                <div style="background: #d5f4e6; padding: 15px; border-left: 4px solid #27ae60;">
                    <p><strong>Request Details:</strong></p>
                    <ul>
                        <li><strong>Type:</strong> {{ request_type }}</li>
                        <li><strong>From:</strong> {{ date_from }}</li>
                        <li><strong>To:</strong> {{ date_to }}</li>
                        <li><strong>Status:</strong> <span style="color: #27ae60;">✅ Approved</span></li>
                    </ul>
                    {% if mentor_comment %}
                    <p><strong>Mentor Comment:</strong> {{ mentor_comment }}</p>
                    {% endif %}
                </div>
                <p>You can now download the approval letter from your dashboard.</p>
                <p style="color: #7f8c8d; font-size: 12px;">
                    © MEF Portal | Generated on {{ timestamp }}
                </p>
            </div>
        </body>
        </html>
        """
    },
    "request_rejected": {
        "subject": "❌ Request Rejected - MEF Portal",
        "template": """
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #e74c3c;">Request Rejected</h2>
                <p>Hi <strong>{{ student_name }}</strong>,</p>
                <p>Your request has been <strong style="color: #e74c3c;">REJECTED</strong> by your mentor.</p>
                <div style="background: #fadbd8; padding: 15px; border-left: 4px solid #e74c3c;">
                    <p><strong>Request Details:</strong></p>
                    <ul>
                        <li><strong>Type:</strong> {{ request_type }}</li>
                        <li><strong>From:</strong> {{ date_from }}</li>
                        <li><strong>To:</strong> {{ date_to }}</li>
                        <li><strong>Status:</strong> <span style="color: #e74c3c;">❌ Rejected</span></li>
                    </ul>
                    {% if mentor_comment %}
                    <p><strong>Rejection Reason:</strong></p>
                    <p>{{ mentor_comment }}</p>
                    {% endif %}
                </div>
                <p>You can resubmit your request after addressing the feedback. Visit your dashboard to try again.</p>
                <p style="color: #7f8c8d; font-size: 12px;">
                    © MEF Portal | Generated on {{ timestamp }}
                </p>
            </div>
        </body>
        </html>
        """
    },
    "password_reset": {
        "subject": "🔐 Reset Your MEF Portal Password",
        "template": """
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Password Reset Request</h2>
                <p>Hi <strong>{{ user_name }}</strong>,</p>
                <p>We received a request to reset your MEF Portal password. Click the button below to create a new password:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ reset_link }}" style="
                        background: #3498db;
                        color: white;
                        padding: 12px 30px;
                        text-decoration: none;
                        border-radius: 5px;
                        display: inline-block;
                    ">Reset Password</a>
                </div>
                <p style="color: #e74c3c;"><strong>⚠️ Security Note:</strong></p>
                <ul>
                    <li>This link expires in <strong>1 hour</strong></li>
                    <li>If you didn't request this, ignore this email</li>
                    <li>Never share this link with anyone</li>
                </ul>
                <p style="color: #7f8c8d; font-size: 12px;">
                    © MEF Portal | Generated on {{ timestamp }}
                </p>
            </div>
        </body>
        </html>
        """
    },
    "welcome": {
        "subject": "👋 Welcome to MEF Portal",
        "template": """
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Welcome to MEF Portal!</h2>
                <p>Hi <strong>{{ user_name }}</strong>,</p>
                <p>Your account has been successfully created. You can now log in and start using MEF Portal to manage your requests.</p>
                <div style="background: #f5f5f5; padding: 15px; border-left: 4px solid #3498db;">
                    <p><strong>Your Login Details:</strong></p>
                    <ul>
                        <li><strong>Register Number:</strong> {{ register_number }}</li>
                        <li><strong>Portal URL:</strong> <a href="{{ portal_url }}">{{ portal_url }}</a></li>
                    </ul>
                </div>
                <p><strong>Quick Start:</strong></p>
                <ol>
                    <li>Log in to your account</li>
                    <li>Update your profile (optional)</li>
                    <li>Submit your first request</li>
                    <li>Track its status in real-time</li>
                </ol>
                <p>Need help? Contact our support team or check the FAQ section.</p>
                <p style="color: #7f8c8d; font-size: 12px;">
                    © MEF Portal | Generated on {{ timestamp }}
                </p>
            </div>
        </body>
        </html>
        """
    }
}


class EmailService:
    """Service for sending emails in MEF Portal"""
    
    def __init__(self, app=None):
        self.mail = Mail()
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize Flask-Mail with app"""
        self.mail.init_app(app)
        self.app = app
    
    def send_email(
        self,
        to_email: str,
        template_name: str,
        context: Dict,
        subject: Optional[str] = None
    ) -> bool:
        """
        Send an email using a template
        
        Args:
            to_email: Recipient email address
            template_name: Name of template (key in EMAIL_TEMPLATES)
            context: Dictionary with template variables
            subject: Override subject (uses template subject if not provided)
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            if template_name not in EMAIL_TEMPLATES:
                logger.error(f"Template not found: {template_name}")
                return False
            
            template_data = EMAIL_TEMPLATES[template_name]
            
            # Add timestamp to context
            context['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Render template with context
            html_content = render_template_string(
                template_data['template'],
                **context
            )
            
            # Create message
            msg = Message(
                subject=subject or template_data['subject'],
                recipients=[to_email],
                html=html_content,
                sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@mefportal.edu')
            )
            
            # Send email
            self.mail.send(msg)
            logger.info(f"Email sent successfully to {to_email} (template: {template_name})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_request_submitted(self, to_email: str, student_name: str, request_data: Dict) -> bool:
        """Notify student that request was submitted"""
        context = {
            'student_name': student_name,
            'request_type': request_data.get('request_type', 'Leave Request'),
            'date_from': request_data.get('date_from', 'N/A'),
            'date_to': request_data.get('date_to', 'N/A'),
        }
        return self.send_email(to_email, 'request_submitted', context)
    
    def send_request_approved(
        self,
        to_email: str,
        student_name: str,
        request_data: Dict,
        mentor_comment: Optional[str] = None
    ) -> bool:
        """Notify student that request was approved"""
        context = {
            'student_name': student_name,
            'request_type': request_data.get('request_type', 'Leave Request'),
            'date_from': request_data.get('date_from', 'N/A'),
            'date_to': request_data.get('date_to', 'N/A'),
            'mentor_comment': mentor_comment or '',
        }
        return self.send_email(to_email, 'request_approved', context)
    
    def send_request_rejected(
        self,
        to_email: str,
        student_name: str,
        request_data: Dict,
        mentor_comment: Optional[str] = None
    ) -> bool:
        """Notify student that request was rejected"""
        context = {
            'student_name': student_name,
            'request_type': request_data.get('request_type', 'Leave Request'),
            'date_from': request_data.get('date_from', 'N/A'),
            'date_to': request_data.get('date_to', 'N/A'),
            'mentor_comment': mentor_comment or 'No reason provided',
        }
        return self.send_email(to_email, 'request_rejected', context)
    
    def send_password_reset(self, to_email: str, user_name: str, reset_link: str) -> bool:
        """Send password reset link"""
        context = {
            'user_name': user_name,
            'reset_link': reset_link,
        }
        return self.send_email(to_email, 'password_reset', context)
    
    def send_welcome(
        self,
        to_email: str,
        user_name: str,
        register_number: str,
        portal_url: str
    ) -> bool:
        """Send welcome email to new user"""
        context = {
            'user_name': user_name,
            'register_number': register_number,
            'portal_url': portal_url,
        }
        return self.send_email(to_email, 'welcome', context)


# Initialize service (to be called in app factory)
email_service = EmailService()
