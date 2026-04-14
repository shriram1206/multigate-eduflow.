"""
app/services/request_service.py

CQ-008: Service layer for request management.

Handles business logic for:
  - Creating new requests
  - Updating request status
  - Approval workflows
  - Retrieving request information
"""

import logging
from typing import Tuple, Optional, List, Dict, Any
import datetime

from app.extensions import db
from app.models import Request, User, AuditLog
from app.constants import MAX_LEAVE_DAYS_PER_MONTH, REQUEST_STATUSES

logger = logging.getLogger('mefportal')


class RequestService:
    """Service for request management operations."""

    @staticmethod
    def create_request(
        user_id: int,
        request_type: str,
        reason: str,
        from_date: str,
        to_date: str,
        department: str,
        student_name: str,
        custom_subject: Optional[str] = None,
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Create a new request.

        Args:
            user_id: ID of requesting user.
            request_type: Type of request ('leave', 'permission', 'bonafide', etc.).
            reason: Reason for request.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            department: User's department.
            student_name: Full name of student.
            custom_subject: Custom subject (for permission requests).

        Returns:
            (success: bool, message: str, request_id: Optional[int])

        Validations:
            - from_date <= to_date
            - Leave requests don't exceed monthly limits
            - All required fields present
        """
        try:
            # Parse dates
            try:
                from_dt = datetime.datetime.strptime(from_date, "%Y-%m-%d").date()
                to_dt = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()
            except ValueError:
                return False, "Invalid date format (use YYYY-MM-DD)", None

            if to_dt < from_dt:
                return False, "To date must be same or after From date", None

            # Check leave limit
            if request_type.lower() == "leave":
                # Count existing approved leave days this month
                month_start = from_dt.replace(day=1)
                if from_dt.month == 12:
                    month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - datetime.timedelta(days=1)
                else:
                    month_end = month_start.replace(month=month_start.month + 1, day=1) - datetime.timedelta(days=1)

                # Count days in request
                delta = to_dt - from_dt
                days_requested = delta.days + 1

                # Count existing approved leave in month
                existing_approved = Request.query.filter(
                    Request.user_id == user_id,
                    Request.request_type == "leave",
                    Request.status.in_(["Approved", "Mentor Approved"]),
                    Request.from_date >= month_start.isoformat(),
                    Request.to_date <= month_end.isoformat(),
                ).count()

                if existing_approved + days_requested > MAX_LEAVE_DAYS_PER_MONTH:
                    return (
                        False,
                        f"Leave limit exceeded: {existing_approved + days_requested} days requested "
                        f"(max {MAX_LEAVE_DAYS_PER_MONTH} per month)",
                        None,
                    )

            # Create request
            new_request = Request(
                user_id=user_id,
                type=request_type,
                reason=reason,
                from_date=from_date,
                to_date=to_date,
                status="Pending",
                student_name=student_name,
                department=department,
                request_type=request_type.capitalize(),
            )

            db.session.add(new_request)
            db.session.flush()  # Get ID without committing

            # Create audit log entry
            user = db.session.get(User, user_id)
            if user:
                audit = AuditLog(
                    request_id=new_request.id,
                    actor_id=user_id,
                    actor_name=user.name,
                    actor_role=user.role,
                    action="Submitted",
                    note=None,
                )
                db.session.add(audit)

            db.session.commit()
            logger.info(f"Request created: {new_request.id} (user: {user_id}, type: {request_type})")
            return True, "Request submitted successfully", new_request.id

        except Exception as e:
            logger.exception(f"Request creation error: {e}")
            db.session.rollback()
            return False, "Failed to create request", None

    @staticmethod
    def update_request_status(
        request_id: int,
        new_status: str,
        actor_id: int,
        note: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Update request status (approve, reject, etc.).

        Args:
            request_id: ID of request to update.
            new_status: New status ('Approved', 'Rejected', 'Mentor Approved', etc.).
            actor_id: ID of user making change.
            note: Optional comment from reviewer.

        Returns:
            (success: bool, message: str)

        Side Effects:
            - Updates Request.status
            - Creates AuditLog entry
            - Updates Request.updated_at
        """
        try:
            request_obj = db.session.get(Request, request_id)
            if not request_obj:
                return False, "Request not found"

            if new_status not in REQUEST_STATUSES:
                return False, f"Invalid status: {new_status}"

            # Update status
            request_obj.status = new_status
            request_obj.updated_at = datetime.datetime.utcnow()

            # Create audit log
            actor = db.session.get(User, actor_id)
            if actor:
                audit = AuditLog(
                    request_id=request_id,
                    actor_id=actor_id,
                    actor_name=actor.name,
                    actor_role=actor.role,
                    action=new_status,
                    note=note,
                )
                db.session.add(audit)

            db.session.commit()
            logger.info(f"Request {request_id} status updated to {new_status} by user {actor_id}")
            return True, ""

        except Exception as e:
            logger.exception(f"Request status update error: {e}")
            db.session.rollback()
            return False, "Failed to update request"

    @staticmethod
    def get_request_with_audit_trail(request_id: int) -> Optional[Dict[str, Any]]:
        """
        Get request details with full audit trail.

        Args:
            request_id: ID of request.

        Returns:
            Dictionary with request data and audit entries, or None if not found.
        """
        try:
            request_obj = db.session.get(Request, request_id)
            if not request_obj:
                return None

            audit_logs = AuditLog.query.filter_by(request_id=request_id).order_by(
                AuditLog.created_at
            ).all()

            return {
                "request": request_obj,
                "audit_trail": [
                    {
                        "timestamp": log.created_at.isoformat(),
                        "actor": log.actor_name,
                        "role": log.actor_role,
                        "action": log.action,
                        "note": log.note,
                    }
                    for log in audit_logs
                ],
            }

        except Exception as e:
            logger.exception(f"Error retrieving request audit trail: {e}")
            return None

    @staticmethod
    def get_user_requests(
        user_id: int,
        status: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Get paginated list of requests for a user.

        Args:
            user_id: ID of user.
            status: Optional status filter.
            limit: Pagination limit.
            offset: Pagination offset.

        Returns:
            (list of request dicts, total count)
        """
        try:
            query = Request.query.filter_by(user_id=user_id)

            if status:
                query = query.filter_by(status=status)

            total = query.count()
            requests_data = query.order_by(Request.created_at.desc()).limit(limit).offset(offset).all()

            return (
                [
                    {
                        "id": r.id,
                        "type": r.request_type,
                        "reason": r.reason,
                        "from_date": r.from_date,
                        "to_date": r.to_date,
                        "status": r.status,
                        "created_at": r.created_at.isoformat(),
                    }
                    for r in requests_data
                ],
                total,
            )

        except Exception as e:
            logger.exception(f"Error retrieving user requests: {e}")
            return [], 0
