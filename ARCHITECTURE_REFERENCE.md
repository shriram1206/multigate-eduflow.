# MEF Portal - Architecture Reference Document
**Version**: 1.0  
**Date**: April 6, 2026  
**Status**: Active - Production Ready

---

## SYSTEM ARCHITECTURE OVERVIEW

### 1. 3-Tier Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                          TIER 1: PRESENTATION               │
│                      (Web Browser / Mobile)                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ • Login Page (login.html)                             │  │
│  │ • Student Dashboard (dashboard.html)                  │  │
│  │ • Request Form (request_form.html)                    │  │
│  │ • Status Tracking (status.html)                       │  │
│  │ • Mentor/Advisor/HOD approval interfaces              │  │
│  │ • Static assets (CSS, JS, mobile-responsive)          │  │
│  └───────────────────────────────────────────────────────┘  │
│                              ↓↑ HTTPS/TLS 1.2+              │
├─────────────────────────────────────────────────────────────┤
│                   TIER 2: APPLICATION LOGIC                 │
│                    (Flask backend + Gunicorn)               │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ app/__init__.py (Flask app factory)                   │  │
│  │ ┌──────────────────────────────────────────────────┐  │  │
│  │ │ app/auth/ - Authentication & Authorization       │  │  │
│  │ │   ├── Login (password validation)                │  │  │
│  │ │   ├── Register (new user)                        │  │  │
│  │ │   └── Logout (session cleanup)                   │  │  │
│  │ ├──────────────────────────────────────────────────┤  │  │
│  │ │ app/main/ - Student-facing features              │  │  │
│  │ │   ├── Dashboard (request stats)                  │  │  │
│  │ │   ├── Submit request                             │  │  │
│  │ │   ├── View status                                │  │  │
│  │ │   └── Download PDF                               │  │  │
│  │ ├──────────────────────────────────────────────────┤  │  │
│  │ │ app/staff/ - Approval workflow                   │  │  │
│  │ │   ├── Mentor approval dashboard                  │  │  │
│  │ │   ├── Advisor approval dashboard                 │  │  │
│  │ │   └── HOD final approval                         │  │  │
│  │ ├──────────────────────────────────────────────────┤  │  │
│  │ │ app/requests/ - Request management               │  │  │
│  │ │   └── Request CRUD operations                    │  │  │
│  │ └──────────────────────────────────────────────────┘  │  │
│  │                                                      │  │
│  │ Core Modules:                                      │  │
│  │ • database.py (PostgreSQL connection + SQL trans)  │  │
│  │ • models.py (User, Request data models)            │  │
│  │ • extensions.py (Flask-Login, CSRF, Limiter)       │  │
│  │ • utils.py (Shared utilities)                      │  │
│  │                                                    │  │
│  │ Middleware:                                        │  │
│  │ • Password hashing (werkzeug)                      │  │
│  │ • Session management (Flask-Login)                 │  │
│  │ • CSRF protection (Flask-WTF)                      │  │
│  │ • Rate limiting (Flask-Limiter)                    │  │
│  │ • XSS prevention (Bleach sanitization)             │  │
│  │ • PDF generation (FPDF)                            │  │
│  └───────────────────────────────────────────────────┘  │
│                              ↓↑ psycopg2 binary            │
├─────────────────────────────────────────────────────────────┤
│                    TIER 3: DATA PERSISTENCE                 │
│               (PostgreSQL via Supabase - Cloud)             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ Database: postgres (Supabase Managed)                │  │
│  │                                                      │  │
│  │ Tables:                                              │  │
│  │ ├── users (id, email, password_hash, role, ...)     │  │
│  │ ├── requests (id, student_id, date_from, date_to,   │  │
│  │ │             reason, status, created_at)           │  │
│  │ ├── approvals (id, request_id, approver_id, level,  │  │
│  │ │              status, comment, created_at)         │  │
│  │ └── audit_log (id, user_id, action, timestamp, ...) │  │
│  │                                                      │  │
│  │ Security:                                            │  │
│  │ • Connection: SSL-required (sslmode='require')       │  │
│  │ • Backups: Daily automated (Supabase)               │  │
│  │ • Encryption: At-rest (Supabase managed)             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. REQUEST FLOW DIAGRAM

### Student Leave Request Approval Workflow

```
┌──────────┐
│ Student  │
└────┬─────┘
     │
     │ 1. Submits Request                    (student/routes.py)
     ↓
┌──────────────────────────────────────────────────────────┐
│ Request Form (request_form.html)                         │
│ • Date from, Date to                                     │
│ • Reason                                                 │
│ • Optional attachment                                    │
└────┬─────────────────────────────────────────────────────┘
     │ Validation (forms.py)
     ↓
┌──────────────────────────────────────────────────────────┐
│ Database Insert (app/database.py)                        │
│ INSERT INTO requests (student_id, date_from, date_to,    │
│              reason, status='pending_mentor')            │
└────┬─────────────────────────────────────────────────────┘
     │ Status: pending_mentor 
     ↓
┌──────────┐
│  Mentor  │──────→ Gets notification (email, Phase 1)
└────┬─────┘
     │
     │ 2. Reviews Request                    (staff/routes.py)
     │ clicks "Approve" or "Reject"
     ↓
┌──────────────────────────────────────────────────────────┐
│ Approval Record (app/database.py)                        │
│ INSERT INTO approvals (request_id, approver_id,          │
│              level='mentor', status='approved')          │
│ UPDATE requests SET status='pending_advisor'             │
└────┬─────────────────────────────────────────────────────┘
     │
     ↓
┌──────────┐
│  Advisor │──────→ Gets notification
└────┬─────┘
     │
     │ 3. Reviews & Approves                 (staff/routes.py)
     ↓
┌──────────────────────────────────────────────────────────┐
│ Approval Record                                          │
│ INSERT INTO approvals (... level='advisor')              │
│ UPDATE requests SET status='pending_hod'                 │
└────┬─────────────────────────────────────────────────────┘
     │
     ↓
┌──────────┐
│   HOD    │──────→ Gets notification
└────┬─────┘
     │
     │ 4. Final Approval                     (staff/routes.py)
     ↓
┌──────────────────────────────────────────────────────────┐
│ Final Approval Record                                    │
│ INSERT INTO approvals (... level='hod')                  │
│ UPDATE requests SET status='approved_final'              │
└────┬─────────────────────────────────────────────────────┘
     │
     ↓
┌──────────┐
│ Student  │──────→ Receives notification
└────┬─────┘       Can download PDF
     │
     │ 5. Downloads PDF                      (main/routes.py)
     ↓
┌──────────────────────────────────────────────────────────┐
│ PDF Generation (FPDF)                                    │
│ • Request details                                        │
│ • Approval chain with timestamps                         │
│ • Signature lines                                        │
│ • College letterhead                                     │
└────┬─────────────────────────────────────────────────────┘
     │ File: Request_<ID>_<Date>.pdf
     ↓
┌──────────┐
│ Student  │
│ has PDF  │
└──────────┘
```

---

## 3. MODULE DEPENDENCY GRAPH

```
┌───────────────────────────────────────┐
│    run.py (Application Entry Point)   │
│  • Checks dependencies                │
│  • Loads environment (.env)            │
│  • Creates Flask app                   │
│  • Starts Gunicorn server              │
└──────────────┬────────────────────────┘
               │
               ↓
┌───────────────────────────────────────┐
│  app/__init__.py (App Factory)         │
│  • Initialize extensions              │
│  • Register blueprints (auth, main,   │
│    staff, requests)                   │
│  • Configure error handlers            │
└──┬──────────────┬─────────────────┬──┘
   │              │                 │
   ↓              ↓                 ↓
┌──────────┐  ┌──────────┐  ┌──────────────┐
│ database │  │ models   │  │ extensions   │
│  (PG)    │  │ (ORM)    │  │ (flk-login)  │
└──────────┘  └──────────┘  └──────────────┘
   │ (uses)      │ (uses)      │ (uses)
   │             │             │
   └─────────────┼─────────────┘
                 ↓
┌───────────────────────────────────┐
│  Blueprints (Flask Modules)       │
│                                   │
│  auth/routes.py                   │
│  • POST /login                    │
│  • POST /register                 │
│  • GET /logout                    │
│                                   │
│  main/routes.py                   │
│  • GET / (dashboard)              │
│  • POST /request (submit)         │
│  • GET /status/<id>               │
│  • GET /download/<id> (PDF)       │
│                                   │
│  staff/routes.py                  │
│  • GET /mentor (dashboard)        │
│  • POST /approve/<id>             │
│  • POST /reject/<id>              │
│  • GET /advisor (dashboard)       │
│  • GET /hod (dashboard)           │
│                                   │
│  requests/routes.py               │
│  • GET/POST /request/<id>         │
│  • DELETE /request/<id>           │
└───────────────────────────────────┘
   │ (use)
   │
   └─→ utils.py (shared utilities)
       • Email sending
       • Date formatting
       • PDF generation
```

---

## 4. DATABASE SCHEMA

```sql
-- Users Table
users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  full_name VARCHAR(255),
  role ENUM('student', 'mentor', 'advisor', 'hod', 'admin') NOT NULL,
  department VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Requests Table
requests (
  id SERIAL PRIMARY KEY,
  student_id INTEGER NOT NULL REFERENCES users(id),
  date_from DATE NOT NULL,
  date_to DATE NOT NULL,
  reason TEXT NOT NULL,
  status ENUM(
    'pending_mentor',
    'pending_advisor',
    'pending_hod',
    'approved_final',
    'rejected',
    'withdrawn'
  ) DEFAULT 'pending_mentor',
  attachment_path VARCHAR(255),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Approvals Table (Audit Trail)
approvals (
  id SERIAL PRIMARY KEY,
  request_id INTEGER NOT NULL REFERENCES requests(id),
  approver_id INTEGER NOT NULL REFERENCES users(id),
  level ENUM('mentor', 'advisor', 'hod') NOT NULL,
  status ENUM('approved', 'rejected') NOT NULL,
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Audit Log Table
audit_log (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  action VARCHAR(255) NOT NULL,
  entity_type VARCHAR(50),
  entity_id INTEGER,
  timestamp TIMESTAMP DEFAULT NOW(),
  ip_address VARCHAR(45)
);
```

---

## 5. AUTHENTICATION & AUTHORIZATION

### Authentication Flow

```
1. User enters credentials (login.html form)
   ↓
2. Flask receives POST /auth/login
   ↓
3. Hash password: bcrypt.hashpw(password, salt)
   ↓
4. Compare with database: users.password_hash
   ↓
5. Match? → flask-login creates session
   ↓
6. Session stored in encrypted cookie
   ↓
7. Subsequent requests include session cookie
   ↓
8. @login_required decorator verifies session
```

### Role-Based Access Control (RBAC)

```
Role               Permissions
───────────────────────────────────────────
student            • Submit request
                   • View own requests
                   • Download own PDFs

mentor             • View assigned requests
                   • Approve/reject (first level)
                   • Add comments

advisor            • View pending requests
                   • Approve/reject (second level)
                   • View all requests

hod                • View all requests
                   • Give final approval
                   • View all approvals
                   • Generate reports

admin              • User management
                   • System configuration
                   • View audit logs
                   • System settings
```

---

## 6. DEPLOYMENT ARCHITECTURE

### Local Development
```
Developer Machine
├── Python 3.9+
├── Flask app (run.py)
├── PostgreSQL (local or Supabase)
└── Gunicorn (4-8 workers)
```

### Production Deployment (Recommended)

```
┌──────────────────────────────────────────────────┐
│              Internet / Client Browsers           │
└────────────────┬─────────────────────────────────┘
                 │ HTTPS
                 ↓
        ┌────────────────┐
        │  Nginx Reverse │
        │     Proxy      │   (Load balancing,
        │  (Port 443)    │    SSL termination)
        └────────┬───────┘
                 │ HTTP
        ┌────────┴──────┬──────────┬────────┐
        ↓               ↓          ↓        ↓
    ┌────────┐   ┌────────┐  ┌────────┐ ┌────────┐
    │Gunicorn│   │Gunicorn│  │Gunicorn│ │Gunicorn│
    │Worker1 │   │Worker2 │  │Worker3 │ │Worker4 │
    │(port   │   │(port   │  │(port   │ │(port   │
    │8001)   │   │8002)   │  │8003)   │ │8004)   │
    └────┬───┘   └────┬───┘  └────┬───┘ └────┬───┘
         │             │           │          │
         └─────────────┼───────────┴──────────┘
                       │
                   PostgreSQL
                   (Supabase)
```

### Docker Deployment (Phase 2)

```
Dockerfile
├── Python 3.9 base image
├── Install dependencies (pip install -r requirements.txt)
├── Copy app code
├── Expose port 5000
└── CMD: gunicorn app:create_app()

docker-compose.yml
├── mefportal service
│   ├── Build: ./Dockerfile
│   ├── Ports: 5000:5000
│   ├── Environment: .env file
│   └── Volumes: ./app:/app
└── postgres service (optional local dev)
    ├── Image: postgres:12
    ├── Ports: 5432:5432
    └── Volumes: postgres_data:/var/lib/postgresql
```

---

## 7. SECURITY ARCHITECTURE

```
┌────────────────────────────────────────────┐
│         Client Request (HTTPS)              │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│      1. TLS 1.2+ (HTTPS Encryption)       │
│      • Protects in-transit data            │
│      • Certificate pinning (future)        │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   2. WAF Rules (Web Application Firewall)  │
│   • Nginx ModSecurity (future)              │
│   • Cloudflare WAF (if used)                │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   3. CSRF Token Check                      │
│   • Flask-WTF validates CSRF tokens        │
│   • Token required on POST/PUT/DELETE      │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   4. Authentication                        │
│   • Session-based (Flask-Login)            │
│   • Password hash: werkzeug (bcrypt)       │
│   • Session timeout: 8 hours (configurable)│
│   • Rate limiting: 5 attempts/5 min        │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   5. Authorization (RBAC)                  │
│   • @login_required decorator              │
│   • Role checks before action              │
│   • Database reads own data only           │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   6. Input Validation                      │
│   • Form validation (Flask-WTF)            │
│   • Type hints & annotations               │
│   • Date range validation                  │
│   • File upload checks                     │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   7. SQL Injection Prevention               │
│   • Parameterized queries (psycopg2)       │
│   • No string concatenation in SQL         │
│   • ORM migration (future: SQLAlchemy)     │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   8. XSS Prevention                         │
│   • Jinja2 template auto-escaping           │
│   • Bleach sanitization for user input      │
│   • Content-Security-Policy headers        │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   9. Encryption at Rest                    │
│   • Database: Supabase (managed encryption)│
│   • Files: S3 with KMS (future)             │
└─────────────┬──────────────────────────────┘
              │
              ↓
┌────────────────────────────────────────────┐
│   10. Audit Logging                         │
│   • All actions logged to audit_log        │
│   • User ID, action, timestamp              │
│   • IP address captured                     │
│   • No modification of logs possible        │
└────────────────────────────────────────────┘
```

---

## 8. SCALABILITY ARCHITECTURE (Phase 3+)

### Vertical Scaling (Single Machine)
```
• Increase: CPU cores, RAM, SSD storage
• PostgreSQL: Add indexes, query optimization
• Flask: Increase worker count (worker_class=gevent)
```

### Horizontal Scaling (Multiple Machines)
```
┌─────────────────────────────────────────┐
│     Load Balancer (nginx, HAProxy)      │
│     • Distribute traffic across servers  │
│     • Health checks                      │
│     • Sticky sessions (or Redis)         │
└────┬──────────────────────┬─────────────┘
     │                      │
     ↓                      ↓
┌──────────────────┐  ┌──────────────────┐
│   Server 1       │  │   Server 2       │
│  - Gunicorn      │  │  - Gunicorn      │
│  - Nginx         │  │  - Nginx         │
│  - App instances │  │  - App instances │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         └─────────┬───────────┘
                   │
                   ↓
         ┌──────────────────┐
         │   PostgreSQL     │
         │   (Supabase)     │
         │  - Read replicas │
         │  - Auto-scaling  │
         │  - Backups       │
         └──────────────────┘

         ↖─────────────────────────────╱
          Caching Layer (Redis)
          • Session storage
          • View caching
          • Rate limiting state
```

---

## 9. MONITORING & OBSERVABILITY

```
┌──────────────────────────────────────────┐
│    Application Metrics (Prometheus)      │
│  • Request count & latency                │
│  • Error rate                             │
│  • Database connection pool               │
│  • Worker health                          │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│    Visualization (Grafana)                │
│  • Real-time dashboards                   │
│  • Historical trends                      │
│  • Alert status                           │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│    Error Tracking (Sentry)                │
│  • Exception aggregation                  │
│  • Stack traces                           │
│  • User context                           │
│  • Release tracking                       │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────┐
│    Log Aggregation (ELK / Datadog)       │
│  • Centralized logging                    │
│  • Search & filtering                     │
│  • Alerting on log patterns               │
└────────┬─────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────────┐
│    Alert Management                          │
│  • PagerDuty / Slack integration             │
│  • Escalation policies                       │
│  • On-call rotation                          │
└──────────────────────────────────────────────┘
```

---

## 10. TECHNOLOGY DECISION MATRIX

| Decision | Choice | Alternative | Reason |
|----------|--------|-----------|--------|
| **Backend** | Flask | Django, FastAPI | Lightweight, WSGI compatible, fine-grained control |
| **Database** | PostgreSQL | MySQL, MongoDB | Relational integrity, ACID guarantees, Supabase managed |
| **Driver** | psycopg2 | mysql-connector | PostgreSQL native, better performance |
| **ORM** | Raw SQL | SQLAlchemy, ORM | Simpler migration path, can upgrade later |
| **Server** | Gunicorn | uWSGI, Waitress | WSGI standard, reliable, easy to scale |
| **Reverse Proxy** | Nginx | Apache, Caddy | Performance, minimal resource usage |
| **Frontend** | Jinja2 | React, Vue | Server-side rendering, no JS build step |
| **Styling** | CSS | SCSS/Sass, Tailwind | Vanilla CSS keeps dependencies low initially |
| **Session** | Flask-Login | Custom | Reference implementation, battle-tested |
| **PDF** | FPDF | ReportLab,Weasyprint | Lightweight, works well for simple docs |
| **Auth** | Session-based | JWT, OAuth2 | Sessions simpler for web app, upgrade possible |
| **Cloud DB** | Supabase | AWS RDS, Azure SQL | PostgreSQL managed, built-in backups, SSL |
| **Container** | Docker | Podman, LXC | Industry standard, ecosystem mature |
| **CI/CD** | GitHub Actions | GitLab CI, CircleCI | Free tier sufficient, integrated with repo |

---

## 11. RISK MITIGATION STRATEGIES

| Risk | Impact | Mitigation |
|------|--------|-----------|
| **Database outage** | Critical | Read replicas, auto-failover (Phase 3), backups tested weekly |
| **DDoS attack** | High | CDN, rate limiting, WAF rules, Cloudflare (future) |
| **Data breach** | Critical | SSL-required connections, encryption at rest, 2FA, audit logs |
| **Code injection** | Critical | Parameterized queries, input validation, SAST scanning |
| **Session hijacking** | High | Secure cookies, HTTPS-only, session rotation |
| **Weak passwords** | Medium | Password policy, bcrypt hashing, 2FA option |
| **Single point of failure** | High | Horizontal scaling (Phase 3), distributed system |
| **Unpatched vulnerabilities** | Medium | Monthly dependency audits, security scanning |
| **Data loss** | Critical | Daily backups, Supabase replication, RTO <4h |
| **Compliance violation** | High | Privacy policy, GDPR compliance plan, audit logs |

---

## 12. DEPLOYMENT CHECKLIST

Before production release, verify:

```
INFRASTRUCTURE
☐ Nginx configured (SSL, reverse proxy)
☐ Gunicorn configured (4+ workers)
☐ PostgreSQL connection pooling enabled
☐ Firewall rules configured (ports 80, 443)
☐ Monitoring & alerting active
☐ Log aggregation working
☐ Backup system tested

SECURITY
☐ SSL certificate installed & valid
☐ HTTPS enforced on all endpoints
☐ Security headers configured (CSP, X-Frame-Options, etc.)
☐ Rate limiting thresholds set
☐ CSRF tokens working
☐ XSS filtering enabled
☐ SQL injection prevention verified
☐ No hardcoded secrets in code

PERFORMANCE
☐ Page load <3s on 3G
☐ Database indexes created
☐ Query optimization completed
☐ Static asset caching enabled
☐ CDN configured (if applicable)
☐ Compression enabled (gzip)

TESTING
☐ Unit tests >80% coverage
☐ Integration tests passing
☐ End-to-end tests passing
☐ Load test: 100 concurrent users
☐ Security scan: No critical CVEs
☐ Manual smoke test: All core workflows

DOCUMENTATION
☐ Deployment guide created
☐ Runbook for incidents
☐ API documentation complete
☐ Architecture documented
☐ Data backup procedure documented
☐ Disaster recovery plan written

COMMUNICATION
☐ Team trained on deployment
☐ Stakeholders notified of go-live
☐ Support contact information shared
☐ Incident response plan in place
```

---

**Document Status**: READY FOR IMPLEMENTATION  
**Next Update**: After Sprint 1  
**Architecture Review**: Weekly with tech team

