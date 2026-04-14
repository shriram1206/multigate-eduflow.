import logging
import re
import bleach
import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_required, current_user
from app.staff import bp
from app.extensions import db, limiter
from app.models import Request, User, LeaveLimitRule, AuditLog
from app.utils import normalize_department_name
from sqlalchemy import text

logger = logging.getLogger('mefportal')

# ---------- MENTOR ----------
@bp.route('/mentor')
@login_required
def mentor():
    if 'username' not in session or session.get('role') != 'Mentor':
        return redirect(url_for('auth.login'))

    mentor_dept = normalize_department_name(session.get('department'))
    logger.debug(f"Mentor dashboard loaded for dept: {mentor_dept}")
    
    try:
        # Case-insensitive, trimmed department match using parameterised raw SQL to maintain Postgres replacement logic
        requests_data = db.session.execute(text("""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(to_char(updated_at, 'YYYY-MM-DD HH24:MI'), to_char(created_at, 'YYYY-MM-DD HH24:MI')) as updation,
                   student_name, department, created_at
            FROM requests
            WHERE 
                (
                    LOWER(TRIM(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            department,
                            'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                            'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                    ))
                ) = :dept
                AND status='Pending'
            ORDER BY created_at DESC
        """), {"dept": mentor_dept}).fetchall()
        
        logger.debug(f"Fetched requests for mentor: {len(requests_data)} rows")
        
        return render_template('mentor.html', requests=requests_data)
    except Exception as e:
        logger.exception("Database error in mentor dashboard")
        flash("Error loading mentor dashboard", "danger")
        return render_template('mentor.html', requests=[])

@bp.route('/mentor_action', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def mentor_action():
    if 'username' not in session or session.get('role') != 'Mentor':
        return redirect(url_for('auth.login'))

    req_id = request.form['request_id']
    action = request.form['action']
    status_value = 'Mentor Approved' if action == 'Approve' else 'Mentor Rejected'

    try:
        req = Request.query.get(req_id)
        if req:
            req.status = status_value
            req.updated_at = datetime.datetime.utcnow()
            db.session.add(AuditLog(
                request_id=req.id,
                actor_id=current_user.id,
                actor_name=current_user.name,
                actor_role='Mentor',
                action=status_value,
            ))
            db.session.commit()
            # Email notification to student
            from app.email_service import notify_status_changed
            student = User.query.get(req.user_id)
            if student:
                notify_status_changed(student.email, student.name, req.type, req.id,
                                      status_value, current_user.name)
            flash(f"Request #{req_id} {status_value}", "success")
        else:
            flash(f"Request #{req_id} not found", "danger")
        return redirect(url_for('staff.mentor'))
    except Exception as e:
        logger.exception("Database error in mentor action")
        db.session.rollback()
        flash("Error updating request status", "danger")
        return redirect(url_for('staff.mentor'))

# ---------- ADVISOR ----------
@bp.route('/advisor')
@login_required
def advisor():
    if 'username' not in session or session.get('role') != 'Advisor':
        return redirect(url_for('auth.login'))

    advisor_dept = normalize_department_name(session.get('department'))

    try:
        mentors_res = db.session.execute(text("""
            SELECT name FROM users
            WHERE role='Mentor' AND (
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                ))
            ) = :dept
            ORDER BY name ASC
        """), {"dept": advisor_dept}).fetchall()
        mentors_in_dept = [row[0] for row in mentors_res]

        students_list = db.session.execute(text("""
            SELECT name, register_number, year, email FROM users
            WHERE role='Student' AND (
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                ))
            ) = :dept
            ORDER BY name ASC
        """), {"dept": advisor_dept}).fetchall()

        requests_data = db.session.execute(text("""
            SELECT id, user_id, type, reason, from_date, to_date, status,
                   COALESCE(to_char(updated_at, 'YYYY-MM-DD HH24:MI'), to_char(created_at, 'YYYY-MM-DD HH24:MI')) as updation,
                   student_name, department, created_at
            FROM requests
            WHERE 
                (
                    LOWER(TRIM(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            department,
                            'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                            'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                    ))
                ) = :dept
                AND status='Mentor Approved'
            ORDER BY created_at DESC
        """), {"dept": advisor_dept}).fetchall()

        return render_template('advisor.html', requests=requests_data, students_list=students_list, mentors_in_dept=mentors_in_dept)
    except Exception as e:
        logger.exception("Database error in advisor dashboard")
        flash("Error loading advisor dashboard", "danger")
        return render_template('advisor.html', requests=[], students_list=[], mentors_in_dept=[])

@bp.route('/advisor_action', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def advisor_action():
    if 'username' not in session or session.get('role') != 'Advisor':
        return redirect(url_for('auth.login'))

    req_id = request.form['request_id']
    action = request.form['action']
    advisor_note = request.form.get('advisor_note', '').strip()
    status_value = 'Advisor Approved' if action == 'Approve' else 'Advisor Rejected'

    try:
        req = Request.query.get(req_id)
        if req:
            req.status = status_value
            req.advisor_note = advisor_note
            req.updated_at = datetime.datetime.utcnow()
            db.session.add(AuditLog(
                request_id=req.id,
                actor_id=current_user.id,
                actor_name=current_user.name,
                actor_role='Advisor',
                action=status_value,
                note=advisor_note or None,
            ))
            db.session.commit()
            from app.email_service import notify_status_changed
            student = User.query.get(req.user_id)
            if student:
                notify_status_changed(student.email, student.name, req.type, req.id,
                                      status_value, current_user.name, advisor_note or None)
        return redirect(url_for('staff.advisor'))
    except Exception as e:
        logger.exception("Database error in advisor action")
        db.session.rollback()
        flash("Error updating request status", "danger")
        return redirect(url_for('staff.advisor'))

# ---------- HOD ----------
@bp.route('/hod')
@login_required
def hod():
    if 'username' not in session or session.get('role') != 'HOD':
        return redirect(url_for('auth.login'))

    hod_dept = normalize_department_name(session.get('department'))

    try:
        requests_data = db.session.execute(text("""
            SELECT r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status,
                   COALESCE(to_char(r.updated_at, 'YYYY-MM-DD HH24:MI'), to_char(r.created_at, 'YYYY-MM-DD HH24:MI')) as updation,
                   r.student_name, r.department, r.created_at, r.advisor_note
            FROM requests r
            WHERE 
                (
                    LOWER(TRIM(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            r.department,
                            'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                            'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                    ))
                ) = :dept
            ORDER BY r.created_at DESC
        """), {"dept": hod_dept}).fetchall()

        mentors_data = db.session.execute(text("""
            SELECT name, email FROM users
            WHERE role='Mentor' AND (
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                ))
            ) = :dept
            ORDER BY name ASC
        """), {"dept": hod_dept}).fetchall()
        mentors = [{'name': m[0], 'email': m[1]} for m in mentors_data]

        # Use ORM model — no raw DDL, works on both Supabase and SQLite
        rules_raw = LeaveLimitRule.query.filter(
            db.func.lower(db.func.trim(LeaveLimitRule.department)) == hod_dept
        ).order_by(LeaveLimitRule.month, LeaveLimitRule.from_day).all()

        leave_rules = [
            {'id': r.id, 'department': r.department, 'month': r.month,
             'from_day': r.from_day, 'to_day': r.to_day, 'max_days': r.max_days}
            for r in rules_raw
        ]

        return render_template('hodd.html', requests=requests_data, mentors=mentors, leave_rules=leave_rules)
    except Exception as e:
        logger.exception("Database error in HOD dashboard")
        flash("Error loading HOD dashboard", "danger")
        return render_template('hodd.html', requests=[], mentors=[], leave_rules=[])

@bp.route('/hod_action', methods=['POST'])
@login_required
@limiter.limit("30 per hour")
def hod_action():
    if 'username' not in session or session.get('role') != 'HOD':
        return redirect(url_for('auth.login'))

    req_id = request.form['request_id']
    action = request.form['action']
    status_value = 'Approved' if action == 'Approve' else 'Rejected'

    try:
        req = Request.query.get(req_id)
        if req:
            req.status = status_value
            req.updated_at = datetime.datetime.utcnow()
            db.session.add(AuditLog(
                request_id=req.id,
                actor_id=current_user.id,
                actor_name=current_user.name,
                actor_role='HOD',
                action=status_value,
            ))
            db.session.commit()
            from app.email_service import notify_status_changed
            student = User.query.get(req.user_id)
            if student:
                notify_status_changed(student.email, student.name, req.type, req.id,
                                      status_value, current_user.name)
            flash(f"Request #{req_id} {status_value}", "success")
        return redirect(url_for('staff.hod'))
    except Exception as e:
        logger.exception("Database error in HOD action")
        db.session.rollback()
        flash("Error updating request status", "danger")
        return redirect(url_for('staff.hod'))

# ---------- USER MANAGEMENT ----------
@bp.route('/user_management')
@login_required
def user_management():
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can access user management.", "danger")
        return redirect(url_for('main.dashboard'))

    dept_filter = request.args.get('department', '')
    role_filter = request.args.get('role', '')
    search_query = request.args.get('search', '')
    user_dept = normalize_department_name(session.get('department'))
    
    try:
        where_conditions = []
        params = {}
        
        if session.get('role') == 'HOD':
            where_conditions.append("""
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                )) = :user_dept
            """)
            params['user_dept'] = user_dept
        
        if dept_filter:
            where_conditions.append("""
                LOWER(TRIM(
                    REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                        department,
                        'iv-', ''), 'IV-', ''), 'v-', ''), 'V-', ''),
                        'iv ', ''), 'IV ', ''), 'v ', ''), 'V ', '')
                )) = :dept_filter
            """)
            params['dept_filter'] = normalize_department_name(dept_filter)
        
        if role_filter:
            where_conditions.append("role = :role_filter")
            params['role_filter'] = role_filter
        
        if search_query:
            where_conditions.append("(name ILIKE :search OR register_number ILIKE :search OR email ILIKE :search)")
            params['search'] = f"%{search_query}%"
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        query = f"""
            SELECT id, username, name, role, register_number, email, department, year, dob, student_type, mentor_email
            FROM users 
            WHERE {where_clause}
            ORDER BY role, department, name
        """
        users_data = db.session.execute(text(query), params).fetchall()
        
        departments_res = db.session.execute(text("SELECT DISTINCT department FROM users WHERE department IS NOT NULL ORDER BY department")).fetchall()
        departments = [row[0] for row in departments_res]
        
        return render_template('user_management.html', 
                               users=users_data, 
                               departments=departments,
                               current_dept_filter=dept_filter,
                               current_role_filter=role_filter,
                               current_search=search_query)
        
    except Exception as e:
        logger.exception("Database error in user management")
        flash("Error loading user management data", "danger")
        return render_template('user_management.html', users=[], departments=[])

@bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can edit users.", "danger")
        return redirect(url_for('main.dashboard'))

    try:
        user = User.query.get(user_id)
        if not user:
            flash("User not found", "danger")
            return redirect(url_for('staff.user_management'))
        
        if session.get('role') == 'HOD':
            user_dept = normalize_department_name(session.get('department'))
            target_dept = str(user.department).strip().lower()
            target_dept = re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', target_dept)
            
            if user_dept != target_dept:
                flash("You can only edit users from your department", "danger")
                return redirect(url_for('staff.user_management'))
        
        if request.method == 'POST':
            name = bleach.clean(request.form['name'], strip=True)
            email = bleach.clean(request.form['email'], strip=True)
            role = bleach.clean(request.form['role'], strip=True)
            department = bleach.clean(request.form['department'], strip=True)
            year = bleach.clean(request.form.get('year', ''), strip=True)
            student_type = bleach.clean(request.form.get('student_type', 'Day Scholar'), strip=True)
            mentor_email = bleach.clean(request.form.get('mentor_email', ''), strip=True) or None
            
            if not all([name, email, role, department]):
                # Fallback format for template compatibility
                u_tuple = (user.id, user.username, user.name, user.role, None, user.register_number, user.email, user.department, user.year, user.dob, user.student_type, user.mentor_email)
                flash("Name, email, role, and department are required", "danger")
                return render_template('edit_user.html', user=u_tuple)
            
            user.name = name
            user.email = email
            user.role = role
            user.department = department
            user.year = year
            user.student_type = student_type
            user.mentor_email = mentor_email
            user.updated_at = datetime.datetime.utcnow()
            db.session.commit()
            
            flash(f"User {name} updated successfully", "success")
            return redirect(url_for('staff.user_management'))
        
        u_tuple = (user.id, user.username, user.name, user.role, None, user.register_number, user.email, user.department, user.year, user.dob, user.student_type, user.mentor_email)
        return render_template('edit_user.html', user=u_tuple)
        
    except Exception as e:
        logger.exception("Database error in edit user")
        flash("Error loading user details", "danger")
        return redirect(url_for('staff.user_management'))

@bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def delete_user(user_id):
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can delete users.", "danger")
        return redirect(url_for('staff.user_management'))

    try:
        user = User.query.get(user_id)
        if not user:
            flash("User not found", "danger")
            return redirect(url_for('staff.user_management'))
        
        if session.get('role') == 'HOD':
            user_dept = normalize_department_name(session.get('department'))
            target_dept = str(user.department).strip().lower()
            target_dept = re.sub(r'^(iv[\s-]*|IV[\s-]*|v[\s-]*|V[\s-]*)', '', target_dept)
            
            if user_dept != target_dept:
                flash("You can only delete users from your department", "danger")
                return redirect(url_for('staff.user_management'))
        
        if user_id == session.get('id'):
            flash("You cannot delete your own account", "danger")
            return redirect(url_for('staff.user_management'))
        
        name = user.name
        db.session.delete(user)
        db.session.commit()
        
        flash(f"User {name} deleted successfully", "success")
        return redirect(url_for('staff.user_management'))
        
    except Exception as e:
        logger.exception("Database error in delete user")
        flash("Error deleting user", "danger")
        return redirect(url_for('staff.user_management'))

# ---------- LEAVE RULES (HOD only) ----------
@bp.route('/add_leave_rule', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def add_leave_rule():
    if 'username' not in session or session.get('role') != 'HOD':
        flash("Access denied", "danger")
        return redirect(url_for('main.dashboard'))

    month = request.form.get('rule_month', '').strip()
    max_days = request.form.get('rule_max_days', '').strip()
    from_day = request.form.get('rule_from_day', '').strip()
    to_day = request.form.get('rule_to_day', '').strip()

    if not all([month, max_days, from_day, to_day]):
        flash("All rule fields are required", "danger")
        return redirect(url_for('staff.hod'))

    try:
        month = int(month)
        max_days = int(max_days)
        from_day = int(from_day)
        to_day = int(to_day)
        if not (1 <= month <= 12 and 1 <= from_day <= 31 and 1 <= to_day <= 31 and 0 <= max_days <= 31):
            raise ValueError("Out of range")
    except (ValueError, TypeError):
        flash("Invalid rule values", "danger")
        return redirect(url_for('staff.hod'))

    hod_dept = normalize_department_name(session.get('department'))

    try:
        rule = LeaveLimitRule(
            department=hod_dept,
            month=month,
            from_day=from_day,
            to_day=to_day,
            max_days=max_days,
            set_by=current_user.id,
        )
        db.session.add(rule)
        db.session.commit()
        flash("Leave rule added", "success")
    except Exception:
        logger.exception("Error adding leave rule")
        db.session.rollback()
        flash("Error adding leave rule", "danger")

    return redirect(url_for('staff.hod'))

@bp.route('/delete_leave_rule/<int:rule_id>', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def delete_leave_rule(rule_id):
    if 'username' not in session or session.get('role') != 'HOD':
        flash("Access denied", "danger")
        return redirect(url_for('main.dashboard'))

    hod_dept = normalize_department_name(session.get('department'))

    try:
        rule = LeaveLimitRule.query.filter(
            LeaveLimitRule.id == rule_id,
            db.func.lower(db.func.trim(LeaveLimitRule.department)) == hod_dept
        ).first()
        if rule:
            db.session.delete(rule)
            db.session.commit()
            flash("Leave rule deleted", "success")
        else:
            flash("Leave rule not found or not in your department", "danger")
    except Exception:
        logger.exception("Error deleting leave rule")
        db.session.rollback()
        flash("Error deleting leave rule", "danger")

    return redirect(url_for('staff.hod'))


# ---------- CSV EXPORT (HOD / Admin) ----------
@bp.route('/export_csv')
@login_required
@limiter.limit("20 per hour")
def export_csv():
    """Download all department requests as a CSV file."""
    if 'username' not in session or session.get('role') not in ['HOD', 'Admin']:
        flash("Access denied. Only HODs and Admins can export data.", "danger")
        return redirect(url_for('main.dashboard'))

    import csv
    import io
    from flask import Response

    dept = normalize_department_name(session.get('department', ''))
    status_filter = request.args.get('status', '')
    date_from     = request.args.get('date_from', '')
    date_to       = request.args.get('date_to', '')

    try:
        query = Request.query
        if session.get('role') == 'HOD':
            query = query.filter(
                db.func.lower(db.func.trim(Request.department)) == dept
            )
        if status_filter:
            query = query.filter(Request.status == status_filter)
        if date_from:
            query = query.filter(Request.from_date >= date_from)
        if date_to:
            query = query.filter(Request.to_date <= date_to)

        rows = query.order_by(Request.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Student Name', 'Department', 'Request Type', 'Type',
            'Reason', 'From Date', 'To Date', 'Status', 'Advisor Note',
            'Submitted At', 'Last Updated'
        ])
        for r in rows:
            writer.writerow([
                r.id, r.student_name, r.department, r.request_type, r.type,
                r.reason, r.from_date, r.to_date, r.status,
                r.advisor_note or '',
                r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                r.updated_at.strftime('%Y-%m-%d %H:%M') if r.updated_at else '',
            ])

        output.seek(0)
        filename = f"requests_{dept}_{date_from or 'all'}.csv"
        logger.info("CSV export: dept=%s rows=%d user=%s", dept, len(rows), session.get('username'))
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    except Exception:
        logger.exception("CSV export error")
        flash("Error generating CSV export", "danger")
        return redirect(url_for('staff.hod'))
