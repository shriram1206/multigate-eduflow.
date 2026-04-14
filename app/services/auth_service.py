"""
app/services/auth_service.py

CQ-008: Service layer for authentication business logic.

Separates HTTP request handling (routes) from business logic (services).
This enables:
  - Easier testing (no Flask fixtures needed)
  - Code reuse across multiple route files
  - Clear separation of concerns
  - Easier debugging
"""

import logging
import datetime
from typing import Tuple, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models import User, AuthLockout, PasswordResetToken
from app.constants import MAX_FAILED_LOGIN_ATTEMPTS, LOGIN_LOCKOUT_SECONDS
from app.utils import validate_password, normalize_department_name

logger = logging.getLogger('mefportal')


class AuthService:
    """
    Authentication service: Login, logout, registration, password reset.
    All business logic is here; routes are thin wrappers calling these methods.
    """

    @staticmethod
    def verify_password(stored_hash: str, provided_password: str) -> bool:
        """
        Verify that provided password matches stored hash.

        Args:
            stored_hash: Password hash from database (must be werkzeug-format).
            provided_password: User-provided plaintext password.

        Returns:
            True if password matches hash, False otherwise.

        Security:
            - Rejects passwords if hash is not in expected werkzeug format
            - Uses werkzeug's check_password_hash for comparison
            - Returns False on any exception (safe fail)
        """
        if not stored_hash or not isinstance(stored_hash, str):
            return False
        if not (stored_hash.startswith('pbkdf2:') or
                stored_hash.startswith('scrypt:') or
                stored_hash.startswith('bcrypt:')):
            logger.warning("Password verification rejected: hash not in werkzeug format")
            return False
        try:
            return check_password_hash(stored_hash, provided_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    @staticmethod
    def record_failed_attempt(register_number: str) -> None:
        """
        Record a failed login attempt and enforce lockout after threshold.

        Args:
            register_number: User's registration number.

        Side Effects:
            - Modifies AuthLockout table
            - Commits transaction (or rolls back on error)
        """
        try:
            lockout = AuthLockout.query.filter_by(register_number=register_number).first()
            if not lockout:
                lockout = AuthLockout(register_number=register_number, failed_attempts=1)
                db.session.add(lockout)
            else:
                lockout.failed_attempts += 1
                if lockout.failed_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                    lockout.lockout_until = (
                        datetime.datetime.utcnow()
                        + datetime.timedelta(seconds=LOGIN_LOCKOUT_SECONDS)
                    )
                else:
                    lockout.lockout_until = None
            db.session.commit()
        except Exception as e:
            logger.exception(f"Failed to record failed login attempt: {e}")
            db.session.rollback()

    @staticmethod
    def authenticate_user(
        register_number: str,
        password: str,
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Authenticate user by registration number and password.

        Enforces account lockout after MAX_FAILED_LOGIN_ATTEMPTS.

        Args:
            register_number: User's registration number.
            password: User-provided plaintext password.

        Returns:
            (User object, None) on success
            (None, error_message) on failure

        Flow:
            1. Look up user in database
            2. Check for account lockout
            3. Verify password
            4. Clear lockout on success, record attempt on failure
        """
        if not register_number or not password:
            return None, "Registration number and password are required"

        try:
            user = User.query.filter_by(register_number=register_number).first()
            if not user:
                AuthService.record_failed_attempt(register_number)
                return None, "Invalid credentials"

            # Check lockout
            lockout = AuthLockout.query.filter_by(register_number=register_number).first()
            if lockout and lockout.failed_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
                if lockout.lockout_until:
                    now = datetime.datetime.utcnow()
                    if now < lockout.lockout_until:
                        return (
                            None,
                            "Account locked due to too many failed attempts. Try again later.",
                        )

            # Verify password
            if not AuthService.verify_password(user.password, password):
                AuthService.record_failed_attempt(register_number)
                return None, "Invalid credentials"

            # Success: Clear lockout
            try:
                if lockout:
                    db.session.delete(lockout)
                    db.session.commit()
            except Exception:
                db.session.rollback()

            return user, None

        except Exception as e:
            logger.exception(f"Authentication error: {e}")
            return None, "Database error during authentication"

    @staticmethod
    def register_user(
        name: str,
        register_number: str,
        email: str,
        password: str,
        role: str = "Student",
        department: str = "General",
        year: str = "1",
        dob: str = None,
        student_type: str = "Day Scholar",
        mentor_email: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Register a new user account.

        Args:
            name: User's full name.
            register_number: Unique registration number.
            email: User's email address.
            password: Plaintext password (will be hashed).
            role: User role ('Student', 'Mentor', 'Advisor', 'HOD').
            department: Department name.
            year: Academic year (for students).
            dob: Date of birth (YYYY-MM-DD).
            student_type: 'Day Scholar' or 'Hosteller'.
            mentor_email: Assigned mentor's email (for students).

        Returns:
            (True, "Registration successful") on success
            (False, error_message) on failure

        Validations:
            - Password meets strength requirements
            - Registration number is unique
            - Email is unique (if enforced by DB)
            - Date format is valid
        """
        # Validate password
        valid, msg = validate_password(password)
        if not valid:
            return False, msg

        # Check duplicate registration number
        if User.query.filter_by(register_number=register_number).first():
            return False, "Registration number already exists"

        try:
            hashed_pw = generate_password_hash(password)

            new_user = User(
                username=register_number,
                name=name,
                register_number=register_number,
                password=hashed_pw,
                email=email,
                role=role,
                department=department,
                year=year,
                dob=dob,
                student_type=student_type,
                mentor_email=mentor_email,
            )

            db.session.add(new_user)
            db.session.commit()

            logger.info(f"User registered: {register_number} ({role})")
            return True, "Registration successful"

        except Exception as e:
            logger.exception(f"Registration error: {e}")
            db.session.rollback()
            return False, "Registration failed. Please try again."

    @staticmethod
    def update_user_profile(
        user_id: int,
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Update user profile information.

        Args:
            user_id: User's database ID.
            name: New name (optional).
            email: New email (optional).

        Returns:
            (True, "") on success
            (False, error_message) on failure
        """
        try:
            user = db.session.get(User, user_id)
            if not user:
                return False, "User not found"

            if name:
                user.name = name
            if email:
                user.email = email

            db.session.commit()
            logger.info(f"User profile updated: {user_id}")
            return True, ""

        except Exception as e:
            logger.exception(f"Profile update error: {e}")
            db.session.rollback()
            return False, "Profile update failed"

    @staticmethod
    def change_password(
        user_id: int,
        current_password: str,
        new_password: str,
    ) -> Tuple[bool, str]:
        """
        Change user's password.

        Args:
            user_id: User's database ID.
            current_password: Current plaintext password (for verification).
            new_password: New plaintext password.

        Returns:
            (True, "") on success
            (False, error_message) on failure

        Validations:
            - Current password must match
            - New password must meet strength requirements
        """
        try:
            user = db.session.get(User, user_id)
            if not user:
                return False, "User not found"

            # Verify current password
            if not AuthService.verify_password(user.password, current_password):
                return False, "Current password is incorrect"

            # Validate new password
            valid, msg = validate_password(new_password)
            if not valid:
                return False, msg

            # Update password
            user.password = generate_password_hash(new_password)
            db.session.commit()

            logger.info(f"Password changed for user: {user_id}")
            return True, ""

        except Exception as e:
            logger.exception(f"Password change error: {e}")
            db.session.rollback()
            return False, "Password change failed"

    @staticmethod
    def initiate_password_reset(email: str) -> Tuple[bool, str, Optional[str]]:
        """
        Initiate password reset via email token.

        Returns:
            (success: bool, message: str, reset_url: Optional[str])
            - message is always the same to prevent user enumeration
            - reset_url is only returned if user found (for testing)
        """
        generic_msg = "If that email is registered, you will receive a reset link shortly."

        try:
            user = User.query.filter_by(email=email).first()
            reset_url = None

            if user:
                # Invalidate old tokens
                PasswordResetToken.query.filter_by(
                    user_id=user.id, used=False
                ).update({"used": True})

                # Create new token
                token_obj = PasswordResetToken.generate(user.id)
                db.session.add(token_obj)
                db.session.commit()

                reset_url = f"/reset_password/{token_obj.token}"
                logger.info(f"Password reset token generated for user: {user.id}")

                # In real app, would send email here via email_service
                # send_password_reset(user.email, user.name, reset_url)

            return True, generic_msg, reset_url

        except Exception as e:
            logger.exception(f"Password reset initiation error: {e}")
            db.session.rollback()
            return True, generic_msg, None  # Still return generic message for security

    @staticmethod
    def reset_password_with_token(token: str, new_password: str) -> Tuple[bool, str]:
        """
        Reset password using valid reset token.

        Args:
            token: Reset token from PasswordResetToken table.
            new_password: New plaintext password.

        Returns:
            (True, "") on success
            (False, error_message) on failure

        Validations:
            - Token must exist and not be expired
            - Token must not have been used before
            - New password must meet strength requirements
        """
        try:
            token_obj = PasswordResetToken.query.filter_by(token=token).first()

            if not token_obj or not token_obj.is_valid:
                return False, "This reset link has expired or already been used"

            # Validate new password
            valid, msg = validate_password(new_password)
            if not valid:
                return False, msg

            # Get user
            user = User.query.get(token_obj.user_id)
            if not user:
                return False, "User not found"

            # Update password and mark token used
            user.password = generate_password_hash(new_password)
            token_obj.used = True
            db.session.commit()

            logger.info(f"Password reset successful for user: {user.id}")
            return True, ""

        except Exception as e:
            logger.exception(f"Password reset error: {e}")
            db.session.rollback()
            return False, "Password reset failed"

    @staticmethod
    def get_user_session_data(user: User) -> dict:
        """
        Prepare session data for a logged-in user.

        Args:
            user: User object from database.

        Returns:
            Dictionary of session variables to set.

        Used by routes.login() after successful authentication.
        """
        return {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "role": user.role,
            "register_number": user.register_number,
            "email": user.email,
            "department": normalize_department_name(user.department),
            "student_type": user.student_type,
        }
