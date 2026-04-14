import logging
import re
import datetime
from flask import render_template, redirect, url_for, flash, request, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import bleach

from app.auth import bp
from app.extensions import db, limiter
from app.models import User, AuthLockout, Request, PasswordResetToken
from app.utils import validate_password, normalize_department_name
from app.services import AuthService
from sqlalchemy import func

logger = logging.getLogger('mefportal')


@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """
    User login endpoint with brute-force protection.
    
    GET: Display login form.
    POST: Authenticate user against database.
    
    Flow:
        1. Receives registration_number + password
        2. Looks up user in database
        3. Checks for account lockout
        4. Verifies password hash
        5. On success: Clears lockout, sets session, redirects by role
        6. On failure: Records failed attempt, shows error
        
    Security:
        - Rate limited to 5 requests/minute per IP
        - Account locked after 5 failed attempts for 15 minutes
        - Passwords must be werkzeug-hashed in database
        - Session variables normalized (e.g., department lowercased)
        
    Returns:
        GET: Rendered login.html template
        POST (success): Redirect to role-specific dashboard
        POST (failure): Re-render login.html with error message
        
    Status Codes:
        - 200: Render login form or show error
        - 302: Redirect on successful authentication
    """
    if request.method == 'GET':
        return render_template('login.html')

    register_number = bleach.clean(request.form.get('register_number', '').strip(), strip=True)
    password = request.form.get('password', '')
    if not register_number or not password:
        flash("Registration number and password are required", "danger")
        return render_template('login.html')

    # Use AuthService for authentication (delegates to service layer)
    user, error = AuthService.authenticate_user(register_number, password)
    
    if error:
        flash(error, "danger")
        return render_template('login.html')

    # Successful login - set session data
    try:
        login_user(user)

        session['id'] = user.id
        session['username'] = user.username
        session['name'] = user.name
        session['role'] = user.role
        session['register_number'] = user.register_number
        session['email'] = user.email
        session['department'] = normalize_department_name(user.department)
        session['student_type'] = user.student_type

        logger.info(f"User {register_number} logged in successfully")
        
        # Redirect by role
        role = user.role
        if role == "Mentor":
            return redirect(url_for('staff.mentor'))
        elif role == "Advisor":
            return redirect(url_for('staff.advisor'))
        elif role == "HOD":
            return redirect(url_for('staff.hod'))
        return redirect(url_for('main.dashboard'))
    except Exception as e:
        logger.exception(f"Error setting session after login: {e}")
        flash("Session error. Please try again.", "danger")
        return render_template('login.html')


@bp.route('/logout')
def logout():
    """
    Logout the current user and clear session.
    
    Returns:
        Redirect to login page
        
    Side Effects:
        - Calls Flask-Login's logout_user()
        - Clears Flask session dictionary
        - Shows "Logged out successfully" flash message
    """
    try:
        logout_user()
    except Exception:
        pass
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for('auth.login'))


@bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    """
    User registration endpoint with role-based account creation.
    
    GET: Display registration form with list of mentors.
    POST: Create new user account in database.
    
    Features:
        - Student registration with mentor assignment
        - Staff registration (Mentor, Advisor, HOD) — restricted to HOD/Admin
        - Auto-generated staff registration numbers: MENSOR(N), ADV(N), HOD(N)
        - Student validation: Department, year, DOB, student type (Day Scholar / Hosteller)
        - Password strength validation (CQ-001 with type hints, CQ-005 comprehensive docstrings)
        
    Security:
        - Rate limited to 5 registrations/hour per IP
        - Input sanitized with bleach.clean()
        - Passwords validated per policy
        - Duplicate registration number rejected
        - Role creation restricted to authorized users
        
    Returns:
        GET: Rendered register.html with mentor list
        POST (success): registration_success.html for staff (with credentials), redirect to login for students
        POST (failure): Re-render register.html with error message
        
    Raises:
        No exceptions — all errors shown as flash messages
    """
    try:
        mentors_query = User.query.filter_by(role='Mentor').order_by(User.department, User.name).all()
        mentors = [
            {
                'name': m.name,
                'email': m.email,
                'department': normalize_department_name(m.department).upper()
            }
            for m in mentors_query
        ]
    except Exception:
        logger.exception("Database error fetching mentors")
        flash("Error loading form", "danger")
        return render_template('register.html', mentors=[])

    if request.method == 'POST':
        name = bleach.clean(request.form['name'], strip=True)
        role = bleach.clean(request.form.get('role', 'Student'), strip=True)

        from app.constants import STAFF_ROLES
        if role in STAFF_ROLES:
            if session.get('role') not in ('HOD', 'Admin'):
                flash("Staff accounts can only be created by HOD or Admin.", "danger")
                return render_template('register.html', mentors=mentors)
                
        if role == 'Mentor':
            count = User.query.filter_by(role='Mentor').count()
            register_number = f"MEN{count + 1:03d}"
        elif role == 'Advisor':
            count = User.query.filter_by(role='Advisor').count()
            register_number = f"ADV{count + 1:03d}"
        elif role == 'HOD':
            count = User.query.filter_by(role='HOD').count()
            register_number = f"HOD{count + 1:03d}"
        else:
            register_number = bleach.clean(request.form['register_number'], strip=True)
            
        password = request.form['password']
        confirm = request.form['confirm_password']
        email = bleach.clean(request.form['email'], strip=True)
        dept = bleach.clean(request.form.get('department', 'General').strip().lower(), strip=True)
        dept = re.sub(r'^(iv-|v-)', '', dept)
        year = bleach.clean(request.form.get('year', '1'), strip=True)
        dob = bleach.clean(request.form['dob'], strip=True)

        if role == 'Student':
            student_type = bleach.clean(request.form.get('student_type', 'Day Scholar'), strip=True)
            st_lower = student_type.lower()
            if 'day' in st_lower:
                student_type = 'Day Scholar'
            elif 'hostel' in st_lower:
                student_type = 'Hosteller'
        else:
            student_type = 'Day Scholar'
            
        mentor_email = bleach.clean(request.form.get('mentor'), strip=True) if request.form.get('mentor') else None

        if password != confirm:
            flash("Passwords do not match", "danger")
            return render_template('register.html', mentors=mentors)

        valid, msg = validate_password(password)
        if not valid:
            flash(msg, "danger")
            return render_template('register.html', mentors=mentors)

        try:
            if User.query.filter_by(register_number=register_number).first():
                flash("Registration number already exists", "danger")
                return render_template('register.html', mentors=mentors)
        except Exception:
            flash("Database error", "danger")
            return render_template('register.html', mentors=mentors)

        try:
            hashed_pw = generate_password_hash(password)
            date_obj = datetime.datetime.strptime(dob, "%Y-%m-%d")
            formatted_dob = date_obj.strftime("%Y-%m-%d")

            new_user = User(
                username=register_number,
                name=name,
                register_number=register_number,
                password=hashed_pw,
                email=email,
                role=role,
                department=dept,
                year=year,
                dob=formatted_dob,
                student_type=student_type,
                mentor_email=mentor_email
            )
            
            db.session.add(new_user)
            db.session.commit()
            
            if role in ['Mentor', 'Advisor', 'HOD']:
                user_data = {
                    'name': name,
                    'register_number': register_number,
                    'email': email,
                    'department': dept.upper(),
                    'role': role
                }
                return render_template('registration_success.html', user_data=user_data)
            else:
                flash("Registration successful! Please log in.", "success")
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            logger.exception("Registration error")
            flash("Registration failed (DB Error). Try again.", "danger")
            db.session.rollback()
            return render_template('register.html', mentors=mentors)

    return render_template('register.html', mentors=mentors)


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    User profile management endpoint.
    
    GET: Display user profile with request statistics.
    POST: Update profile information or change password.
    
    Features:
        - View personal information (name, email, department, etc.)
        - Update name and email
        - Change password (with validation of current password)
        - Display request statistics (total, pending, approved, rejected)
        - Role-specific display (Staff roles show different info)
        
    Security:
        - Requires login (@login_required)
        - Password changes require current password verification
        - New passwords must pass strength validation
        - All input sanitized with bleach.clean()
        
    Returns:
        GET: Rendered profile.html with user data and statistics
        POST: Redirect to profile with success/error message
        
    Actions (POST):
        - 'update_profile': Update name/email
        - 'change_password': Change password with verification
    """
    if 'id' not in session:
        return redirect(url_for('auth.login'))
    
    user_id = session['id']
    user = User.query.get(user_id)
    if not user:
        flash("User not found", "danger")
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action', '')
        
        if action == 'update_profile':
            name = bleach.clean(request.form.get('name', '').strip(), strip=True)
            email = bleach.clean(request.form.get('email', '').strip(), strip=True)
            
            if not name or not email:
                flash("Name and email are required", "danger")
                return redirect(url_for('auth.profile'))
            
            try:
                user.name = name
                user.email = email
                db.session.commit()
                
                session['name'] = name
                session['email'] = email
                flash("Profile updated successfully!", "success")
            except Exception as e:
                logger.exception("Error updating profile")
                flash("Error updating profile", "danger")
                db.session.rollback()
            
            return redirect(url_for('auth.profile'))
        
        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')
            
            if not current_password or not new_password or not confirm_password:
                flash("All password fields are required", "danger")
                return redirect(url_for('auth.profile'))
            
            if new_password != confirm_password:
                flash("New passwords do not match", "danger")
                return redirect(url_for('auth.profile'))
            
            valid, msg = validate_password(new_password)
            if not valid:
                flash(msg, "danger")
                return redirect(url_for('auth.profile'))
            
            try:
                if not _verify_password(user.password, current_password):
                    flash("Current password is incorrect", "danger")
                    return redirect(url_for('auth.profile'))
                
                user.password = generate_password_hash(new_password)
                db.session.commit()
                
                flash("Password changed successfully!", "success")
            except Exception as e:
                logger.exception("Error changing password")
                flash("Error changing password", "danger")
                db.session.rollback()
            
            return redirect(url_for('auth.profile'))
    
    try:
        total = Request.query.filter_by(user_id=user_id).count()
        pending = Request.query.filter_by(user_id=user_id, status='Pending').count()
        approved = Request.query.filter_by(user_id=user_id, status='Approved').count()
        rejected = Request.query.filter_by(user_id=user_id, status='Rejected').count()
        
        stats = {
            'total_requests':    total,
            'pending_requests':  pending,
            'approved_requests': approved,
            'rejected_requests': rejected,
        }
        
        # Emulate the legacy 11-element tuple query for backward-compatibility with profile.html
        user_tuple = (
            user.id, user.username, user.name, user.role, user.register_number, 
            user.email, user.department, user.year, user.dob, user.student_type, user.mentor_email
        )
        return render_template('profile.html', user=user_tuple, stats=stats)
        
    except Exception as e:
        logger.exception("Error loading profile")
        flash("Error loading profile", "danger")
        return redirect(url_for('main.dashboard'))


# ---------- FORGOT PASSWORD ----------
@bp.route('/forgot_password', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def forgot_password():
    """
    Initiate password reset via email token.
    
    GET: Display forgot password form.
    POST: Send reset link to registered email address.
    
    Security:
        - Prevents user enumeration: Always shows same message
        - Email-based verification (token must be clicked)
        - Tokens expire after 30 minutes
        - Old tokens invalidated when new reset requested
        - Rate limited to 5 requests/hour
        
    Flow:
        1. User submits email address
        2. System checks if user exists (silently if not)
        3. Generates 30-minute reset token
        4. Sends reset URL via email
        5. Shows generic success message (hides if user exists)
        
    Returns:
        GET: Rendered forgot_password.html form
        POST: Redirect to login with generic success message
        
    Side Effects:
        - Creates PasswordResetToken in database
        - Sends email via email_service.send_password_reset()
        - Logs reset requests to logger
    """
    if request.method == 'GET':
        return render_template('forgot_password.html')

    email = bleach.clean(request.form.get('email', '').strip(), strip=True)
    if not email:
        flash("Email address is required.", "danger")
        return render_template('forgot_password.html')

    # Always show the same message to prevent user enumeration
    generic_msg = "If that email is registered, you will receive a reset link shortly."

    try:
        user = User.query.filter_by(email=email).first()
        if user:
            # Invalidate any existing tokens for this user
            PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({'used': True})
            token_obj = PasswordResetToken.generate(user.id)
            db.session.add(token_obj)
            db.session.commit()

            reset_url = url_for('auth.reset_password', token=token_obj.token, _external=True)
            from app.email_service import send_password_reset
            send_password_reset(user.email, user.name, reset_url)
            logger.info("Password reset email dispatched for user_id=%d", user.id)
    except Exception:
        logger.exception("Error in forgot_password")
        db.session.rollback()

    flash(generic_msg, "info")
    return redirect(url_for('auth.login'))


# ---------- RESET PASSWORD ----------
@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def reset_password(token: str):
    """
    Reset user password via token from forgot password email.
    
    GET: Display password reset form (validates token).
    POST: Set new password and mark token as used.
    
    Security:
        - Validates token exists and hasn't expired (30 minutes)
        - Validates new password meets strength requirements
        - Marks token as used (prevents reuse)
        - Rate limited to 10 requests/hour
        - Confirms passwords match before submission
        
    Flow:
        1. User clicks link from email with token
        2. GET validates token is valid (not expired, not used)
        3. User submits new password
        4. POST validates password strength
        5. Password hashed and saved
        6. Token marked as used
        7. Redirect to login
        
    Args:
        token: URL-safe reset token from PasswordResetToken table
        
    Returns:
        GET: Rendered reset_password.html with token
        POST: Redirect to login on success, re-render with error on failure
        
    Status Codes:
        - 200: Show form or error
        - 302: Redirect on success
        
    Side Effects:
        - Updates User.password with hash
        - Sets PasswordResetToken.used = True
    """
    try:
        token_obj = PasswordResetToken.query.filter_by(token=token).first()
    except Exception:
        logger.exception("DB error looking up reset token")
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('auth.login'))

    if not token_obj or not token_obj.is_valid:
        flash("This reset link has expired or already been used. Please request a new one.", "danger")
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'GET':
        return render_template('reset_password.html', token=token)

    new_password = request.form.get('new_password', '')
    confirm      = request.form.get('confirm_password', '')

    if new_password != confirm:
        flash("Passwords do not match.", "danger")
        return render_template('reset_password.html', token=token)

    valid, msg = validate_password(new_password)
    if not valid:
        flash(msg, "danger")
        return render_template('reset_password.html', token=token)

    try:
        user = User.query.get(token_obj.user_id)
        if not user:
            flash("User not found.", "danger")
            return redirect(url_for('auth.login'))

        user.password    = generate_password_hash(new_password)
        token_obj.used   = True
        db.session.commit()
        logger.info("Password reset successful for user_id=%d", user.id)
        flash("Password reset successful! Please log in with your new password.", "success")
        return redirect(url_for('auth.login'))
    except Exception:
        logger.exception("Error resetting password")
        db.session.rollback()
        flash("Error resetting password. Please try again.", "danger")
        return render_template('reset_password.html', token=token)
