# MEF Portal - AI Coding Instructions

## Architecture Overview
This is a **Flask-based educational leave management system** with MySQL backend, handling student-mentor workflow for leave requests. Core pattern: monolithic Flask app (`app.py`) with role-based routing and session management.

## Key Data Flow
1. **Authentication**: Register number + DOB → Session-based login → Role routing (Student/Mentor)
2. **Request Lifecycle**: Student creates → Mentor approves/rejects → PDF generation for approved
3. **Database Schema**: `users` (auth/profile) + `requests` (leave workflow)

## Critical Database Patterns
- **Connection Management**: Use `get_db()` function - stores in Flask's `g` object, auto-closes via `@app.teardown_appcontext`
- **Schema Evolution**: Tables auto-create via `init_db()`, columns added via try/catch ALTER TABLE pattern (see `update_db.py`)
- **Hard-coded Credentials**: `DB_CONFIG` in app.py uses localhost/ram/ram123 - NOT production ready

## Session Management
```python
# Always check login before protected routes
if 'username' not in session:
    flash("Please log in!", "warning")
    return redirect(url_for('login'))

# Session stores: id, username, name, register_number, email, role, department, year
```

## Role-Based Routing
- **Students**: `/dashboard` (stats), `/request` (submit), `/status` (view own)
- **Mentors**: `/mentor` (pending approvals), `/mentor_action` (approve/reject)
- **Root Route**: Force-clears session, always shows login

## PDF Generation Pattern
- Use `fpdf` library for approved leave documents
- Template: From/To format with college letterhead structure
- Return via `send_file()` with BytesIO stream

## Development Workflow
```bash
# Database setup (auto-runs on app start)
python app.py  # Calls init_db() automatically

# Manual DB schema updates
python update_db.py  # For adding new columns

# Debug routes for development
/test          # Flask health check
/test-db       # Database connectivity
/debug-users   # View user data
```

## Template Structure
- `base.html`: Common nav (login/dashboard/request/status/mentor)
- Form templates: `new_login.html`, `register.html`, `request_form.html`
- Status views: `dashboard.html`, `status.html`, `review.html`, `approved.html`
- Role-specific: `mentor.html` for approval workflow

## Error Handling Conventions
- Database failures → Return `None` from `get_db()`, check before cursor operations
- Flash messages with categories: "success", "danger", "warning", "info"
- All exceptions → Flash error message + redirect to safe page

## Security Notes
- **Session secret**: Hardcoded in app.py (change for production)
- **SQL Injection**: Properly parameterized queries used throughout
- **No CSRF protection**: Forms lack CSRF tokens
- **Password storage**: Plain text (NOT hashed)
