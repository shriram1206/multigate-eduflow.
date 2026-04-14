"""
app/services/audit_service.py

CQ-008: Service layer for audit logging.

Provides interface for:
  - Audit trail retrieval
  - CSV export of audit logs
  - Compliance reporting
"""

import logging
import csv
import io
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from app.extensions import db
from app.models import AuditLog, Request
from sqlalchemy import and_

logger = logging.getLogger('mefportal')


class AuditService:
    """Service for audit log operations."""

    @staticmethod
    def get_audit_trail(
        request_id: int,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail for a specific request.

        Args:
            request_id: ID of request.

        Returns:
            List of audit log entries (sorted by timestamp).
            Each entry contains: timestamp, actor_name, actor_role, action, note.
        """
        try:
            logs = AuditLog.query.filter_by(request_id=request_id).order_by(
                AuditLog.created_at
            ).all()

            return [
                {
                    "timestamp": log.created_at.isoformat(),
                    "actor_name": log.actor_name,
                    "actor_role": log.actor_role,
                    "action": log.action,
                    "note": log.note or "",
                }
                for log in logs
            ]

        except Exception as e:
            logger.exception(f"Error retrieving audit trail for request {request_id}: {e}")
            return []

    @staticmethod
    def get_user_audit_history(
        user_id: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve requests and audit entries for a user.

        Args:
            user_id: ID of user.
            limit: Maximum number of requests to retrieve.

        Returns:
            List of requests with their audit trails.
        """
        try:
            requests = Request.query.filter_by(
                user_id=user_id
            ).order_by(Request.created_at.desc()).limit(limit).all()

            result = []
            for req in requests:
                audit_logs = AuditLog.query.filter_by(request_id=req.id).order_by(
                    AuditLog.created_at
                ).all()

                result.append({
                    "request_id": req.id,
                    "type": req.request_type,
                    "status": req.status,
                    "created_at": req.created_at.isoformat(),
                    "reason": req.reason,
                    "from_date": req.from_date,
                    "to_date": req.to_date,
                    "audit_trail": [
                        {
                            "timestamp": log.created_at.isoformat(),
                            "actor": log.actor_name,
                            "role": log.actor_role,
                            "action": log.action,
                            "note": log.note or "",
                        }
                        for log in audit_logs
                    ],
                })

            return result

        except Exception as e:
            logger.exception(f"Error retrieving audit history for user {user_id}: {e}")
            return []

    @staticmethod
    def export_audit_to_csv(
        user_id: int,
        limit: int = 100,
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Export user's audit history as CSV.

        Args:
            user_id: ID of user.
            limit: Maximum requests to export.

        Returns:
            (success: bool, message: str, csv_content: Optional[str])

        CSV Format:
            request_id, type, status, created_at, reason, from_date, to_date,
            action_1_timestamp, action_1_actor, action_1_role, action_1_note, ...
        """
        try:
            audit_history = AuditService.get_user_audit_history(user_id, limit)

            if not audit_history:
                return False, "No requests found", None

            # Create CSV in memory
            output = io.StringIO()
            
            # Determine headers (request fields + up to 20 actions)
            headers = [
                "Request ID",
                "Type",
                "Status",
                "Created At",
                "Reason",
                "From Date",
                "To Date",
            ]

            # Add action columns
            max_actions = max(len(r.get("audit_trail", [])) for r in audit_history) if audit_history else 0
            for i in range(1, max_actions + 1):
                headers.extend([
                    f"Action {i} Timestamp",
                    f"Action {i} Actor",
                    f"Action {i} Role",
                    f"Action {i} Note",
                ])

            writer = csv.writer(output)
            writer.writerow(headers)

            # Write data rows
            for record in audit_history:
                row = [
                    record["request_id"],
                    record["type"],
                    record["status"],
                    record["created_at"],
                    record["reason"],
                    record["from_date"],
                    record["to_date"],
                ]

                # Add audit trail data
                for action in record.get("audit_trail", []):
                    row.extend([
                        action["timestamp"],
                        action["actor"],
                        action["role"],
                        action["note"],
                    ])

            csv_content = output.getvalue()
            logger.info(f"Exported {len(audit_history)} requests for user {user_id}")
            return True, "CSV exported successfully", csv_content

        except Exception as e:
            logger.exception(f"Error exporting CSV for user {user_id}: {e}")
            return False, f"Export failed: {str(e)}", None

    @staticmethod
    def get_department_audit_history(
        department: str,
        status: str = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all requests for a department (for staff review).

        Args:
            department: Department name (normalized).
            status: Optional status filter ('Pending', 'Approved', etc.).
            limit: Maximum number of requests to retrieve.

        Returns:
            List of requests with audit trails.
        """
        try:
            query = Request.query.filter_by(department=department)

            if status:
                query = query.filter_by(status=status)

            requests = query.order_by(Request.created_at.desc()).limit(limit).all()

            result = []
            for req in requests:
                audit_logs = AuditLog.query.filter_by(request_id=req.id).order_by(
                    AuditLog.created_at
                ).all()

                result.append({
                    "request_id": req.id,
                    "student_name": req.student_name,
                    "type": req.request_type,
                    "status": req.status,
                    "created_at": req.created_at.isoformat(),
                    "reason": req.reason,
                    "from_date": req.from_date,
                    "to_date": req.to_date,
                    "audit_trail": [
                        {
                            "timestamp": log.created_at.isoformat(),
                            "actor": log.actor_name,
                            "role": log.actor_role,
                            "action": log.action,
                            "note": log.note or "",
                        }
                        for log in audit_logs
                    ],
                })

            return result

        except Exception as e:
            logger.exception(f"Error retrieving department audit history: {e}")
            return []

    @staticmethod
    def log_action(
        request_id: int,
        actor_id: int,
        actor_name: str,
        actor_role: str,
        action: str,
        note: str = None,
    ) -> Tuple[bool, str]:
        """
        Create an audit log entry.

        Args:
            request_id: ID of request being acted upon.
            actor_id: ID of user performing action.
            actor_name: Name of user (denormalized).
            actor_role: Role of user (denormalized).
            action: Action name (e.g., 'Approved', 'Rejected').
            note: Optional comment.

        Returns:
            (success: bool, message: str)

        Note:
            This is typically called by request_service.update_request_status(),
            not directly by routes.
        """
        try:
            log_entry = AuditLog(
                request_id=request_id,
                actor_id=actor_id,
                actor_name=actor_name,
                actor_role=actor_role,
                action=action,
                note=note,
            )

            db.session.add(log_entry)
            db.session.commit()

            logger.info(f"Audit logged: request {request_id}, action {action} by {actor_name}")
            return True, ""

        except Exception as e:
            logger.exception(f"Error creating audit log: {e}")
            db.session.rollback()
            return False, "Failed to log action"
