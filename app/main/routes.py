import datetime
import logging
import bleach
from flask import Blueprint, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app.utils import validate_date_range, validate_enum, normalize_department_name, escape_like
from app.extensions import limiter, db
from app.models import Request, AuditLog
from sqlalchemy import text, func

logger = logging.getLogger('mefportal')

# Get REQUESTS_PER_PAGE from config
from config import REQUESTS_PER_PAGE
from app.constants import MAX_LEAVE_DAYS_PER_MONTH

# ---------- ROOT ROUTE ----------
@bp.route('/')
def index():
    return render_template('welcome.html')

# ---------- HEALTH CHECK ----------
@bp.route('/healthz')
def healthz():
    try:
        from app.extensions import db
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
        return jsonify({"status": "ok"})
    except Exception:
        logger.exception("Health check failed")
        return jsonify({"status": "error"}), 500

# ---------- DASHBOARD (Date Filter) ----------
@bp.route('/dashboard')
@login_required
def dashboard():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    user_id = session['id']
    selected_date = request.args.get('date')

    try:
        if selected_date:
            requests_data = db.session.query(
                Request.id, Request.user_id, Request.type, Request.reason, 
                Request.from_date, Request.to_date, Request.status,
                func.coalesce(Request.updated_at, Request.created_at).label('updation'),
                Request.student_name, Request.department
            ).filter(
                Request.user_id == user_id,
                func.date(Request.created_at) == selected_date
            ).order_by(Request.created_at.desc()).all()
        else:
            requests_data = db.session.query(
                Request.id, Request.user_id, Request.type, Request.reason, 
                Request.from_date, Request.to_date, Request.status,
                func.coalesce(Request.updated_at, Request.created_at).label('updation'),
                Request.student_name, Request.department
            ).filter(
                Request.user_id == user_id
            ).order_by(Request.created_at.desc()).limit(5).all()

        # Stats aggregation
        total = db.session.query(Request).filter_by(user_id=user_id).count()
        pending = db.session.query(Request).filter_by(user_id=user_id, status='Pending').count()
        approved = db.session.query(Request).filter_by(user_id=user_id, status='Approved').count()
        rejected = db.session.query(Request).filter_by(user_id=user_id, status='Rejected').count()

        recent_updates = db.session.query(
            Request.id, Request.type, Request.status,
            func.coalesce(Request.updated_at, Request.created_at).label('activity_time'),
            Request.student_name
        ).filter(
            Request.user_id == user_id
        ).order_by(func.coalesce(Request.updated_at, Request.created_at).desc()).limit(4).all()

        # Build tuples to maintain backward compatibility with templates
        formatted_requests = [
            (r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status, 
             r.updation.strftime('%Y-%m-%d %H:%M') if r.updation else '', 
             r.student_name, r.department)
            for r in requests_data
        ]
        
        formatted_updates = [
            (r.id, r.type, r.status, r.activity_time, r.student_name)
            for r in recent_updates
        ]
        
    except Exception as e:
        logger.exception("Database error in dashboard")
        flash("Error loading dashboard data", "danger")
        return render_template('dashboard_professional.html', 
                               requests=[], 
                               selected_date=selected_date, 
                               stats={'total_requests': 0, 'pending_requests': 0, 'approved_requests': 0, 'rejected_requests': 0},
                               recent_updates=[])

    stats = {
        'total_requests':    total,
        'pending_requests':  pending,
        'approved_requests': approved,
        'rejected_requests': rejected,
    }

    return render_template('dashboard_professional.html', 
                           requests=formatted_requests, 
                           selected_date=selected_date, 
                           stats=stats,
                           recent_updates=formatted_updates)

# ---------- UNIFIED REQUEST FORM ----------
@bp.route('/unified_request', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour")
def unified_request():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        request_type = (request.form.get('request_type') or 'leave').strip().lower()
        ok, msg = validate_enum(request_type, ['leave', 'permission', 'apology', 'bonafide', 'od'], 'request type')
        if not ok:
            flash(msg, 'danger')
            return render_template('unified_request_form.html')

        # SECURITY FIX: Enforce identity from session token, preventing POST-body tampering
        student_name = session.get('name', 'Unknown Student')
        department = normalize_department_name(session.get('department', 'Unknown'))

        try:
            from app.extensions import db
            from app.models import Request, Permission
            from sqlalchemy import text
            
            if request_type == 'leave':
                # Handle leave request
                req_type = bleach.clean((request.form.get('type') or 'Leave').strip(), strip=True)[:50]
                reason = bleach.clean((request.form.get('reason') or '').strip(), strip=True)[:1000]
                from_date = (request.form.get('from_date') or '').strip()
                to_date = (request.form.get('to_date') or '').strip()
                if not all([req_type, reason, from_date, to_date]):
                    flash('All leave fields are required', 'danger')
                    return render_template('unified_request_form.html')
                ok, msg = validate_date_range(from_date, to_date)
                if not ok:
                    flash(msg, 'danger')
                    return render_template('unified_request_form.html')
                
                limit_exceeded = False
                if session.get('role', 'Student') == 'Student':
                    try:
                        result = db.session.execute(text("""
                            WITH requested_days AS (
                                SELECT generate_series(
                                    :from_date::date,
                                    :to_date::date,
                                    '1 day'::interval
                                )::date AS day
                            ),
                            requested_per_month AS (
                                SELECT to_char(day, 'YYYY-MM') AS month,
                                       COUNT(*) AS days
                                FROM requested_days
                                GROUP BY month
                            ),
                            existing_per_month AS (
                                SELECT to_char(d::date, 'YYYY-MM') AS month,
                                       COUNT(*) AS days
                                FROM requests,
                                     generate_series(
                                         :from_date::date,
                                         :to_date::date,
                                         '1 day'::interval
                                     ) d
                                WHERE user_id = :user_id
                                  AND request_type = 'Leave'
                                  AND status != 'Rejected'
                                GROUP BY month
                            )
                            SELECT r.month,
                                   COALESCE(r.days, 0) + COALESCE(e.days, 0) AS total
                            FROM requested_per_month r
                            LEFT JOIN existing_per_month e ON r.month = e.month
                            WHERE COALESCE(r.days, 0) + COALESCE(e.days, 0) > :max_days
                        """), {
                            "from_date": from_date,
                            "to_date": to_date,
                            "user_id": session['id'],
                            "max_days": MAX_LEAVE_DAYS_PER_MONTH
                        })
                        violations = result.fetchall()
                        if violations:
                            limit_exceeded = True
                    except Exception:
                        logger.exception("Error during leave limit validation")
                
                if limit_exceeded:
                    flash('You have reached your monthly leave limit (2 days).', 'danger')
                    return render_template('unified_request_form.html')

                db.session.add(Request(
                    user_id=session['id'], type=req_type, reason=reason,
                    from_date=from_date, to_date=to_date, status='Pending',
                    student_name=student_name, department=department, request_type='Leave'
                ))
                
            elif request_type == 'apology':
                apology_date = (request.form.get('apology_date') or '').strip()
                apology_reason = bleach.clean((request.form.get('apology_reason') or '').strip(), strip=True)[:1000]
                if not apology_date or not apology_reason:
                    flash('Apology date and reason are required', 'danger')
                    return render_template('unified_request_form.html')
                
                db.session.add(Request(
                    user_id=session['id'], type='Apology', reason=apology_reason,
                    from_date=apology_date, to_date=apology_date, status='Pending',
                    student_name=student_name, department=department, request_type='Apology'
                ))
                
            elif request_type == 'bonafide':
                purpose = bleach.clean((request.form.get('bonafide_purpose') or '').strip(), strip=True)[:100]
                details = bleach.clean((request.form.get('bonafide_details') or '').strip(), strip=True)[:500]
                if not purpose:
                    flash('Purpose is required for bonafide', 'danger')
                    return render_template('unified_request_form.html')
                
                cur_date = datetime.date.today().strftime("%Y-%m-%d")
                db.session.add(Request(
                    user_id=session['id'], type='Bonafide', 
                    reason=f"Bonafide Certificate - Purpose: {purpose}. Details: {details}",
                    from_date=cur_date, to_date=cur_date, status='Pending',
                    student_name=student_name, department=department, request_type='Bonafide'
                ))
                
            elif request_type == 'permission':
                custom_subject = bleach.clean((request.form.get('custom_subject') or '').strip(), strip=True)[:200]
                reason = bleach.clean((request.form.get('permission_reason') or '').strip(), strip=True)[:1000]
                from_date = (request.form.get('permission_from_date') or '').strip()
                to_date = (request.form.get('permission_to_date') or '').strip()
                if not all([custom_subject, reason, from_date, to_date]):
                    flash('All permission fields are required', 'danger')
                    return render_template('unified_request_form.html')
                ok, msg = validate_date_range(from_date, to_date)
                if not ok:
                    flash(msg, 'danger')
                    return render_template('unified_request_form.html')
                
                db.session.add(Request(
                    user_id=session['id'], type='Permission', reason=reason,
                    from_date=from_date, to_date=to_date, status='Pending',
                    student_name=student_name, department=department, request_type='Permission'
                ))
                
            elif request_type == 'od':
                event = bleach.clean((request.form.get('od_event') or '').strip(), strip=True)[:200]
                organization = bleach.clean((request.form.get('od_organization') or '').strip(), strip=True)[:200]
                from_date = (request.form.get('od_from_date') or '').strip()
                to_date = (request.form.get('od_to_date') or '').strip()
                od_reason = bleach.clean((request.form.get('od_reason') or '').strip(), strip=True)[:1000]
                if not all([event, organization, from_date, to_date, od_reason]):
                    flash('All on-duty fields are required', 'danger')
                    return render_template('unified_request_form.html')
                ok, msg = validate_date_range(from_date, to_date)
                if not ok:
                    flash(msg, 'danger')
                    return render_template('unified_request_form.html')
                
                db.session.add(Request(
                    user_id=session['id'], type='On Duty', 
                    reason=f"On Duty - Event: {event}, Organization: {organization}. Details: {od_reason}",
                    from_date=from_date, to_date=to_date, status='Pending',
                    student_name=student_name, department=department, request_type='OD'
                ))
            
            db.session.commit()

            # Audit log — submission event
            new_req = Request.query.filter_by(
                user_id=session['id']
            ).order_by(Request.created_at.desc()).first()
            if new_req:
                db.session.add(AuditLog(
                    request_id=new_req.id,
                    actor_id=session['id'],
                    actor_name=session.get('name', 'Student'),
                    actor_role='Student',
                    action='Submitted',
                ))
                db.session.commit()
                # Email confirmation to student
                from app.email_service import notify_submitted
                notify_submitted(session.get('email', ''), session.get('name', ''),
                                 request_type.title(), new_req.id)

            flash(f"{request_type.title()} request submitted successfully!", "success")
            return redirect(url_for('main.status'))
            
        except Exception as e:
            logger.exception(f"Error submitting {request_type} request")
            flash(f"Error submitting {request_type} request. Please try again.", "danger")
            return render_template('unified_request_form.html')

    return render_template('unified_request_form.html')

# ---------- PERMISSION FORM ----------
@bp.route('/permission_form', methods=['GET', 'POST'])
@login_required
@limiter.limit("20 per hour")
def permission_form():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        student_name = bleach.clean((request.form.get('student_name') or '').strip(), strip=True)[:100]
        department = (request.form.get('department') or '').strip().lower()
        custom_subject = bleach.clean((request.form.get('customSubject') or '').strip(), strip=True)[:200]
        reason = bleach.clean((request.form.get('reason') or '').strip(), strip=True)[:1000]
        from_date = (request.form.get('from_date') or '').strip()
        to_date = (request.form.get('to_date') or '').strip()

        if not all([student_name, department, custom_subject, reason, from_date, to_date]):
            flash("All fields are required", "danger")
            return render_template('permission_form.html')
        ok, msg = validate_date_range(from_date, to_date)
        if not ok:
            flash(msg, 'danger')
            return render_template('permission_form.html')

        try:
            from app.extensions import db
            from app.models import Permission
            
            new_permission = Permission(
                user_id=session['id'],
                student_name=student_name,
                department=department,
                custom_subject=custom_subject,
                reason=reason,
                from_date=from_date,
                to_date=to_date,
                status='Pending'
            )
            db.session.add(new_permission)
            db.session.commit()
            
            flash("Permission request submitted successfully!", "success")
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            logger.exception("Database error in permission form")
            db.session.rollback()
            flash("Error submitting permission request", "danger")
            return render_template('permission_form.html')

    return render_template('permission_form.html')

# ---------- STATUS ----------
@bp.route('/status')
@login_required
def status():
    if 'username' not in session:
        return redirect(url_for('auth.login'))
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = REQUESTS_PER_PAGE
    offset = (page - 1) * per_page
    
    # Get filter parameters
    date_filter = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '')
    
    try:
        from app.extensions import db
        from app.models import Request
        from sqlalchemy import func, or_

        query = db.session.query(Request).filter(Request.user_id == session['id'])

        if date_filter:
            query = query.filter(func.date(Request.created_at) == date_filter)
        
        if status_filter:
            query = query.filter(Request.status == status_filter)
            
        if search_query:
            safe_search = f"%{escape_like(search_query)}%"
            query = query.filter(or_(
                Request.type.ilike(safe_search),
                Request.reason.ilike(safe_search)
            ))

        total_requests = query.count()
        total_pages = (total_requests + per_page - 1) // per_page if per_page > 0 else 1
        has_prev = page > 1
        has_next = page < total_pages

        requests_data = query.order_by(Request.created_at.desc()).offset(offset).limit(per_page).all()

        requests_list = [
            (r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status,
             (r.updated_at or r.created_at).strftime('%Y-%m-%d %H:%M') if (r.updated_at or r.created_at) else '',
             r.student_name, r.department, r.created_at)
            for r in requests_data
        ]
    except Exception as e:
        logger.exception("Database error in status")
        flash("Error loading status data", "danger")
        return render_template('status.html', 
                               requests=[], 
                               pagination={'page': 1, 'per_page': per_page, 'total': 0, 'total_pages': 0, 'has_prev': False, 'has_next': False, 'prev_num': None, 'next_num': None},
                               date_filter=date_filter,
                               status_filter=status_filter,
                               search_query=search_query)
    
    # Pagination info
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_requests,
        'total_pages': total_pages,
        'has_prev': has_prev,
        'has_next': has_next,
        'prev_num': page - 1 if has_prev else None,
        'next_num': page + 1 if has_next else None
    }
    
    return render_template('status.html', 
                           requests=requests_list, 
                           pagination=pagination,
                           date_filter=date_filter,
                           status_filter=status_filter,
                           search_query=search_query)

# ---------- DOWNLOAD STATUS (PDF) ----------
@bp.route('/download_status')
@login_required
def download_status():
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    # Get filter parameters from query string
    date_filter = request.args.get('date', '')
    status_filter = request.args.get('status', '')
    search_query = request.args.get('search', '')
    
    try:
        from app.extensions import db
        from app.models import Request
        from sqlalchemy import func, or_

        query = db.session.query(Request).filter(Request.user_id == session['id'])

        if date_filter:
            query = query.filter(func.date(Request.created_at) == date_filter)
        if status_filter:
            query = query.filter(Request.status == status_filter)
        if search_query:
            safe_search = f"%{escape_like(search_query)}%"
            query = query.filter(or_(
                Request.type.ilike(safe_search),
                Request.reason.ilike(safe_search)
            ))

        requests_data = query.order_by(Request.created_at.desc()).all()

        requests_list = [
            (r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status,
             (r.updated_at or r.created_at).strftime('%Y-%m-%d %H:%M') if (r.updated_at or r.created_at) else '',
             r.student_name, r.department, r.created_at)
            for r in requests_data
        ]
        
        if not requests_list:
            flash("No requests found to download", "info")
            return redirect(url_for('main.status'))
        
        # Generate PDF using FPDF
        try:
            from fpdf import FPDF
            
            # Create PDF instance
            pdf = FPDF()
            
            for request_data in requests_list:
                pdf.add_page()
                
                # Set font
                pdf.set_font("Arial", size=12)
                
                # Add header
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(200, 10, txt="REQUEST STATUS REPORT", ln=1, align='C')
                pdf.ln(5)
                
                # Add application details
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(200, 10, txt="REQUEST DETAILS", ln=1, align='L')
                pdf.ln(5)
                
                pdf.set_font("Arial", size=12)
                details = [
                    ("Application ID", f"LEV-2025-{request_data[0]}"),
                    ("Student Name", request_data[8] or session.get('name', 'N/A')),
                    ("Department", request_data[9] or session.get('department', 'N/A')),
                    ("Request Type", request_data[2]),
                    ("Duration", f"{request_data[4]} to {request_data[5]}"),
                    ("Status", request_data[6]),
                    ("Reason", str(request_data[3]).encode('latin-1', 'replace').decode('latin-1')),
                    ("Submitted Date", str(request_data[10]) if len(request_data) > 10 else "N/A"),
                    ("Last Updated", request_data[7] if len(request_data) > 7 else "N/A")
                ]
                
                for label, value in details:
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(50, 8, txt=f"{label}:", ln=0)
                    pdf.set_font("Arial", size=12)
                    pdf.cell(0, 8, txt=str(value), ln=1)
                
                pdf.ln(10)
                
                # Add separator for multiple requests
                if requests_list.index(request_data) < len(requests_list) - 1:
                    pdf.set_draw_color(200, 200, 200)
                    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
                    pdf.ln(10)
            
            # Add summary page
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, txt="REQUEST SUMMARY", ln=1, align='C')
            pdf.ln(10)
            
            pdf.set_font("Arial", size=12)
            summary_stats = [
                ("Total Requests", len(requests_list)),
                ("Approved Requests", len([r for r in requests_list if r[6] == 'Approved'])),
                ("Pending Requests", len([r for r in requests_list if r[6] == 'Pending'])),
                ("Rejected Requests", len([r for r in requests_list if r[6] == 'Rejected'])),
                ("Mentor Approved", len([r for r in requests_list if r[6] == 'Mentor Approved'])),
                ("Advisor Approved", len([r for r in requests_list if r[6] == 'Advisor Approved']))
            ]
            
            for label, value in summary_stats:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(60, 8, txt=f"{label}:", ln=0)
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 8, txt=str(value), ln=1)
            
            pdf.ln(10)
            
            # Add footer
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(0, 10, txt=f"Generated by MEF Portal - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=1, align='C')
            
            # Generate PDF content
            pdf_output = pdf.output(dest='S').encode('latin1')
            
            # Create response with PDF
            from flask import Response
            response = Response(pdf_output)
            response.headers['Content-Type'] = 'application/pdf'
            
            # Create filename with filters
            filename_parts = ["requests_report"]
            if date_filter:
                filename_parts.append(f"date_{date_filter}")
            if status_filter:
                filename_parts.append(f"status_{status_filter.lower()}")
            if search_query:
                filename_parts.append(f"search_{search_query[:10]}")
            
            filename = f"{'_'.join(filename_parts)}.pdf"
            response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except ImportError:
            flash("PDF generation library not available", "danger")
            return redirect(url_for('main.status'))
        except Exception as e:
            logger.exception("PDF generation error")
            flash("Error generating PDF report", "danger")
            return redirect(url_for('main.status'))
            
    except Exception as e:
        logger.exception("Database error in download status")
        if 'cur' in locals():
            cur.close()
        flash("Error loading requests data", "danger")
        return redirect(url_for('main.status'))

# ---------- APPROVED REQUEST VIEW ----------
@bp.route('/approved/<int:req_id>')
@login_required
def approved(req_id):
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    try:
        from app.extensions import db
        from app.models import Request
        r = db.session.query(Request).filter_by(id=req_id, user_id=session['id']).first()
        
        if r:
            request_data = (
                r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status,
                r.updated_at.strftime('%Y-%m-%d %H:%M') if r.updated_at else '',
                r.student_name, r.department, r.created_at
            )
        else:
            request_data = None
            
    except Exception as e:
        logger.exception("Database error in approved view")
        flash("Error loading request details", "danger")
        return redirect(url_for('main.dashboard'))
    
    if not request_data:
        flash("Request not found", "danger")
        return redirect(url_for('main.dashboard'))
    
    if request_data[6] != 'Approved':  # Status is at index 6
        flash("Request is not approved", "warning")
        return redirect(url_for('main.dashboard'))
    
    return render_template('approved.html', request_data=request_data)

# ---------- DOWNLOAD APPROVED REQUEST PDF ----------
@bp.route('/download_approved/<int:req_id>')
@login_required
def download_single_approved(req_id):
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    try:
        from app.extensions import db
        from app.models import Request
        r = db.session.query(Request).filter_by(id=req_id, user_id=session['id'], status='Approved').first()
        
        if r:
            request_data = (
                r.id, r.user_id, r.type, r.reason, r.from_date, r.to_date, r.status,
                r.updated_at.strftime('%Y-%m-%d %H:%M') if r.updated_at else '',
                r.student_name, r.department, r.created_at
            )
        else:
            request_data = None
            
    except Exception as e:
        logger.exception("Database error in download approved")
        flash("Error loading approved request", "danger")
        return redirect(url_for('main.dashboard'))
    
    if not request_data:
        flash("Approved request not found", "danger")
        return redirect(url_for('main.dashboard'))
    
    # Generate PDF using FPDF
    try:
        from fpdf import FPDF
        
        # Create PDF instance
        pdf = FPDF()
        pdf.add_page()
        
        # Set font
        pdf.set_font("Arial", size=12)
        
        # Add header
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, txt="LEAVE APPLICATION - APPROVED", ln=1, align='C')
        pdf.ln(10)
        
        # Add application details
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="APPLICATION DETAILS", ln=1, align='L')
        pdf.ln(5)
        
        pdf.set_font("Arial", size=12)
        details = [
            ("Application ID", f"LEV-2025-{request_data[0]}"),
            ("Student Name", request_data[8] or session.get('name', 'N/A')),
            ("Department", request_data[9] or session.get('department', 'N/A')),
            ("Leave Type", request_data[2]),
            ("Duration", f"{request_data[4]} to {request_data[5]}"),
            ("Status", request_data[6]),
            ("Reason", str(request_data[3]).encode('latin-1', 'replace').decode('latin-1')),
            ("Submitted Date", str(request_data[10]) if len(request_data) > 10 else "N/A")
        ]
        
        for label, value in details:
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(50, 8, txt=f"{label}:", ln=0)
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 8, txt=str(value), ln=1)
        
        pdf.ln(10)
        
        # Add approval section
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(200, 10, txt="APPROVAL INFORMATION", ln=1, align='L')
        pdf.ln(5)
        
        pdf.set_font("Arial", size=12)
        pdf.multi_cell(0, 8, txt=f"This application has been officially approved by the Head of Department. The request was processed and approved on {request_data[7] if len(request_data) > 7 else 'N/A'}.")
        
        pdf.ln(10)
        
        # Add footer
        pdf.set_font("Arial", 'I', 10)
        pdf.cell(0, 10, txt="Generated by MEF Portal - Selvam College of Technology", ln=1, align='C')
        
        # Generate PDF content
        pdf_output = pdf.output(dest='S').encode('latin1')
        
        # Create response with PDF
        from flask import Response
        response = Response(pdf_output)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename="approved_leave_{request_data[0]}.pdf"'
        
        return response
        
    except ImportError:
        flash("PDF generation library not available", "danger")
        return redirect(url_for('main.status'))
    except Exception as e:
        logger.exception("PDF generation error")
        flash("Error generating PDF", "danger")
        return redirect(url_for('main.status'))

# ---------- SAVE PUSH SUBSCRIPTION ----------
@bp.route('/save-subscription', methods=['POST'])
@login_required
def save_subscription():
    sub = request.get_json(force=True, silent=True) or {}
    endpoint = sub.get('endpoint')
    keys = (sub.get('keys') or {}) if isinstance(sub.get('keys'), dict) else {}
    p256dh = keys.get('p256dh')
    auth_key = keys.get('auth')
    if not endpoint:
        return jsonify({'error': 'Invalid subscription'}), 400
    try:
        from app.extensions import db
        from app.models import PushSubscription
        
        sub_obj = PushSubscription.query.filter_by(user_id=current_user.id, endpoint=endpoint).first()
        if sub_obj:
            sub_obj.p256dh = p256dh
            sub_obj.auth = auth_key
        else:
            sub_obj = PushSubscription(
                user_id=current_user.id, 
                endpoint=endpoint, 
                p256dh=p256dh, 
                auth=auth_key
            )
            db.session.add(sub_obj)
            
        db.session.commit()
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        return jsonify({'error': 'DB error'}), 500


# ---------- REQUEST HISTORY / AUDIT TRAIL ----------
@bp.route('/history/<int:req_id>')
@login_required
def request_history(req_id):
    """Show full approval chain history for one request (student can only see their own)."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    try:
        req = Request.query.filter_by(id=req_id, user_id=session['id']).first()
        if not req:
            flash("Request not found or access denied.", "danger")
            return redirect(url_for('main.status'))

        audit_entries = AuditLog.query.filter_by(
            request_id=req_id
        ).order_by(AuditLog.created_at.asc()).all()

        return render_template('audit_trail.html', req=req, audit_entries=audit_entries)
    except Exception:
        logger.exception("Error loading audit trail for request %d", req_id)
        flash("Error loading request history.", "danger")
        return redirect(url_for('main.status'))


# ---------- CSV EXPORT (student — own requests) ----------
@bp.route('/export_my_csv')
@login_required
@limiter.limit("10 per hour")
def export_my_csv():
    """Download own requests as CSV."""
    if 'username' not in session:
        return redirect(url_for('auth.login'))

    import csv
    import io
    from flask import Response

    status_filter = request.args.get('status', '')

    try:
        query = Request.query.filter_by(user_id=session['id'])
        if status_filter:
            query = query.filter(Request.status == status_filter)
        rows = query.order_by(Request.created_at.desc()).all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'ID', 'Request Type', 'Type', 'Reason',
            'From Date', 'To Date', 'Status',
            'Submitted At', 'Last Updated'
        ])
        for r in rows:
            writer.writerow([
                r.id, r.request_type, r.type, r.reason,
                r.from_date, r.to_date, r.status,
                r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '',
                r.updated_at.strftime('%Y-%m-%d %H:%M') if r.updated_at else '',
            ])

        output.seek(0)
        filename = f"my_requests_{session.get('register_number', 'student')}.csv"
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception:
        logger.exception("Error exporting student CSV")
        flash("Error generating CSV export.", "danger")
        return redirect(url_for('main.status'))
