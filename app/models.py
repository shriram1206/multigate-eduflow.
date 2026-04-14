from flask_login import UserMixin
from typing import Optional
from app.extensions import db
from datetime import datetime
import secrets

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    role = db.Column(db.String, default='Student')
    password = db.Column(db.String)
    register_number = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    department = db.Column(db.String, nullable=False)
    year = db.Column(db.String, default='1')
    dob = db.Column(db.String, nullable=False)
    student_type = db.Column(db.String, default='Day Scholar')
    mentor_email = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    requests = db.relationship('Request', backref='user', lazy=True, cascade='all, delete-orphan')
    permissions = db.relationship('Permission', backref='user', lazy=True, cascade='all, delete-orphan')

class Request(db.Model):
    __tablename__ = 'requests'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    type = db.Column(db.String, nullable=False)
    reason = db.Column(db.String, nullable=False)
    from_date = db.Column(db.String, nullable=False)
    to_date = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default='Pending')
    student_name = db.Column(db.String, nullable=False)
    department = db.Column(db.String, nullable=False)
    request_type = db.Column(db.String, default='Leave')
    advisor_note = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime)

class Permission(db.Model):
    __tablename__ = 'permissions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    student_name = db.Column(db.String, nullable=False)
    department = db.Column(db.String, nullable=False)
    custom_subject = db.Column(db.String, nullable=False)
    reason = db.Column(db.String, nullable=False)
    from_date = db.Column(db.String, nullable=False)
    to_date = db.Column(db.String, nullable=False)
    status = db.Column(db.String, default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AuthLockout(db.Model):
    __tablename__ = 'auth_lockouts'

    id = db.Column(db.Integer, primary_key=True)
    register_number = db.Column(db.String, unique=True, nullable=False)
    failed_attempts = db.Column(db.Integer, nullable=False, default=0)
    lockout_until = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    endpoint = db.Column(db.String, nullable=False)
    p256dh = db.Column(db.String)
    auth = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LeaveLimitRule(db.Model):
    __tablename__ = 'leave_limit_rules'
    id = db.Column(db.Integer, primary_key=True)
    department = db.Column(db.String, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    from_day = db.Column(db.Integer, nullable=False, default=1)
    to_day = db.Column(db.Integer, nullable=False, default=31)
    max_days = db.Column(db.Integer, nullable=False, default=0)
    set_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AuditLog(db.Model):
    """
    Immutable audit trail for every status change on a Request.
    One row is inserted whenever a student submits, a mentor/advisor/HOD acts,
    or a request is rejected. Never updated — append-only.
    """
    __tablename__ = 'audit_logs'

    id          = db.Column(db.Integer, primary_key=True)
    request_id  = db.Column(db.Integer, db.ForeignKey('requests.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_id    = db.Column(db.Integer, db.ForeignKey('users.id',    ondelete='SET NULL'), nullable=True)
    actor_name  = db.Column(db.String, nullable=False)   # denormalised — preserved even if user deleted
    actor_role  = db.Column(db.String, nullable=False)
    action      = db.Column(db.String, nullable=False)   # e.g. 'Submitted', 'Mentor Approved', 'Rejected'
    note        = db.Column(db.String)                   # optional reviewer comment
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class PasswordResetToken(db.Model):
    """
    Single-use, time-limited tokens for password reset via email.
    Tokens expire after 30 minutes and are marked `used=True` once consumed.
    """
    __tablename__ = 'password_reset_tokens'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token      = db.Column(db.String(64), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used       = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def generate(cls, user_id: int) -> 'PasswordResetToken':
        """Create a fresh 30-minute token. Does NOT commit — caller must commit."""
        from datetime import timedelta
        return cls(
            user_id    = user_id,
            token      = secrets.token_urlsafe(48),
            expires_at = datetime.utcnow() + timedelta(minutes=30),
        )

    @property
    def is_valid(self) -> bool:
        return not self.used and datetime.utcnow() < self.expires_at


def load_user(user_id: int) -> Optional[User]:
    """
    Flask-Login callback: restore user object from session.
    Delegates to SQLAlchemy.
    """
    try:
        return db.session.get(User, int(user_id))
    except Exception:
        return None
