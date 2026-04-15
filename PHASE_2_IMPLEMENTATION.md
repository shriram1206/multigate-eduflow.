# Phase 2 Implementation Plan - MEF Portal

**Scope**: Email notifications, password reset, CSV export, audit logging, request history
**Estimated Duration**: 16-20 hours
**Start Date**: April 15, 2026

---

## Phase 2 Features Overview

### 1. Email Notifications System
**Goal**: Notify users of approval/rejection status via email
- **Trigger Points**: Request approved, request rejected, request submitted
- **Templates**: HTML email templates for each event
- **Service**: Flask-Mail integration with Supabase email backend
- **Estimated Time**: 4-5 hours

### 2. Password Reset via Email
**Goal**: Secure password recovery workflow
- **Flow**: Forgot password → Email token → Reset form → New password
- **Security**: Time-limited tokens (1 hour), CSRF protection
- **Templates**: Reset email, reset form
- **Estimated Time**: 3-4 hours

### 3. CSV Export Functionality
**Goal**: Bulk export of requests for analysis
- **Endpoints**: Export all requests, export by status, export by user
- **Format**: CSV with all relevant fields
- **Security**: Only authorized users can export
- **Estimated Time**: 2-3 hours

### 4. Audit Logging System
**Goal**: Track all important actions for compliance
- **Events**: Login, request creation, request approval, status changes, password changes
- **Storage**: Database table with timestamp, user, action, details
- **View**: Admin audit log viewer
- **Estimated Time**: 3-4 hours

### 5. Request History & Filtering
**Goal**: Enhanced request view with advanced filtering
- **Filters**: By status, date range, user, request type
- **Display**: Sortable table with pagination
- **Actions**: View details, download PDF, resubmit
- **Estimated Time**: 2-3 hours

### 6. Advanced Dashboard Analytics
**Goal**: Statistics and insights dashboard
- **Metrics**: Total requests, approval rate, average processing time
- **Charts**: Status distribution, trends over time
- **Reports**: By mentor, by department
- **Estimated Time**: 2-3 hours

---

## Implementation Order

1. **Phase 2.1**: Email Notifications (highest priority)
   - Email service setup
   - Notification templates
   - Event handlers

2. **Phase 2.2**: Password Reset (security critical)
   - Reset token generation
   - Reset endpoint
   - Email template

3. **Phase 2.3**: Audit Logging (compliance)
   - Audit table schema
   - Event logger service
   - Admin viewer

4. **Phase 2.4**: CSV Export (business value)
   - Export service
   - Auth checks
   - Endpoint

5. **Phase 2.5**: Request History (UX improvement)
   - Filtering logic
   - Pagination
   - UI enhancements

6. **Phase 2.6**: Analytics Dashboard (nice-to-have)
   - Metrics calculation
   - Chart rendering
   - Reports

---

## Technical Stack

- **Email Service**: Flask-Mail + Supabase SMTP or SendGrid
- **Task Queue**: Celery (optional, for background email sending)
- **Audit Logging**: Custom service + PostgreSQL
- **CSV Export**: Python csv module
- **Charts**: Chart.js or Plotly
- **Testing**: pytest with fixtures for email mocking

---

## Database Schema Changes

### New Table: audit_logs
```sql
CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
```

### New Table: email_templates
```sql
CREATE TABLE email_templates (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    subject VARCHAR(255),
    body_html TEXT,
    body_text TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Alter: users table
- Add: `password_reset_token`, `password_reset_expires`
- Add: `email_verified`, `email_verified_at`

---

## File Structure (New/Modified)

```
app/
├── services/
│   ├── email_service.py          [NEW] Email sending
│   ├── audit_service.py          [NEW] Audit logging
│   ├── export_service.py         [NEW] CSV export
│   └── password_service.py       [NEW] Password reset
├── models.py                      [MODIFIED] Add audit_logs, email_templates
├── requests/
│   ├── routes.py                 [MODIFIED] Add export endpoints
│   └── decorators.py             [NEW] Auth decorators
├── staff/
│   ├── routes.py                 [MODIFIED] Add audit viewer
│   └── analytics.py              [NEW] Analytics calculations
├── main/
│   └── routes.py                 [MODIFIED] Add password reset routes
├── auth/
│   └── routes.py                 [MODIFIED] Add forgot password route
├── templates/
│   ├── emails/                   [NEW]
│   │   ├── approval_notification.html
│   │   ├── rejection_notification.html
│   │   ├── password_reset.html
│   │   └── welcome.html
│   ├── password_reset.html       [NEW]
│   ├── request_history.html      [NEW]
│   ├── audit_logs.html           [NEW]
│   └── analytics_dashboard.html  [NEW]
├── static/
│   ├── analytics.js              [NEW] Chart rendering
│   └── filters.js                [NEW] Filter logic
└── migrations/
    └── 002_phase2_schema.sql    [NEW] Schema changes

tests/
├── test_email_service.py         [NEW]
├── test_password_reset.py        [NEW]
├── test_csv_export.py            [NEW]
├── test_audit_logging.py         [NEW]
└── test_analytics.py             [NEW]
```

---

## Success Criteria

- ✅ All Phase 2 features implemented and tested
- ✅ Email notifications sending successfully
- ✅ Password reset workflow secure and working
- ✅ CSV export generating correct data
- ✅ Audit logs recording all important events
- ✅ Request history with advanced filtering
- ✅ Analytics dashboard displaying metrics
- ✅ All tests passing (target: 150+ tests)
- ✅ CI/CD pipeline passing for all changes

---

## Next Steps

1. Start with Email Notifications (Phase 2.1)
2. Implement password reset (Phase 2.2)
3. Set up audit logging infrastructure (Phase 2.3)
4. Add CSV export capability (Phase 2.4)
5. Enhance request history view (Phase 2.5)
6. Build analytics dashboard (Phase 2.6)

**Ready to start Phase 2.1: Email Notifications?**
