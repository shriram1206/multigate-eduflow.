"""
app/constants.py — Single source of truth for all magic numbers and enum values.
CQ-003 FIX: No more hardcoded literals scattered across the codebase.
"""

# ── Authentication ──────────────────────────────────────────────────────────────
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS      = 15 * 60        # 15 minutes
SESSION_LIFETIME_SECONDS   = 8  * 60 * 60   # 8 hours

# ── Password Policy ─────────────────────────────────────────────────────────────
PASSWORD_MIN_LENGTH           = 8
PASSWORD_REQUIRE_UPPERCASE    = True
PASSWORD_REQUIRE_LOWERCASE    = True
PASSWORD_REQUIRE_DIGIT        = True
PASSWORD_REQUIRE_SPECIAL_CHAR = True

# ── File Uploads ────────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES       = 16 * 1024 * 1024   # 16 MB
ALLOWED_EXTENSIONS     = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

# ── Pagination ──────────────────────────────────────────────────────────────────
REQUESTS_PER_PAGE = 10
USERS_PER_PAGE    = 20
DASHBOARD_RECENT  = 5   # recent items shown on dashboard

# ── Requests ────────────────────────────────────────────────────────────────────
VALID_REQUEST_TYPES = ['leave', 'permission', 'apology', 'bonafide', 'od']

REQUEST_STATUSES = [
    'Pending',
    'Mentor Approved', 'Mentor Rejected',
    'Advisor Approved', 'Advisor Rejected',
    'Approved', 'Rejected',
]

MAX_LEAVE_DAYS_PER_MONTH = 2

# ── User Roles ──────────────────────────────────────────────────────────────────
ROLE_STUDENT  = 'Student'
ROLE_MENTOR   = 'Mentor'
ROLE_ADVISOR  = 'Advisor'
ROLE_HOD      = 'HOD'
ROLE_ADMIN    = 'Admin'

STAFF_ROLES   = {ROLE_MENTOR, ROLE_ADVISOR, ROLE_HOD, ROLE_ADMIN}
