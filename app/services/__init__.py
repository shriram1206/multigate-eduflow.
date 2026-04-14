"""
app/services/

CQ-008: Service layer for MEF Portal.

Services abstract business logic from Flask routes, enabling:
  - Testability (no Flask context needed)
  - Code reuse
  - Clear separation of concerns
  - Easier debugging and maintenance

Modules:
  - auth_service: Authentication, registration, password reset
  - request_service: Request creation, approval workflow
  - audit_service: Audit logging and trails
"""

from .auth_service import AuthService
from .request_service import RequestService
from .audit_service import AuditService

__all__ = ['AuthService', 'RequestService', 'AuditService']
