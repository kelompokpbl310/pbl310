"""Security Audit Logging Module for Catering Batam.

This module provides a dedicated security audit logger that writes
structured JSON Lines events to a separate log file for future
Wazuh SIEM integration.
"""

import os
import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from typing import Optional, Any
from flask import has_request_context, request


def get_client_ip() -> Optional[str]:
    """Ambil IP asli klien dari header Cloudflare, fallback ke remote_addr."""
    if not has_request_context():
        return None
    ip = request.headers.get("CF-Connecting-IP")
    if ip:
        return ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr

class JSONAuditFormatter(logging.Formatter):
    """JSON formatter for security audit events.
    
    Generates valid JSON Lines output with all required fields.
    Handles missing values, escapes special characters, and prevents
    log injection.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Build the base audit event
        audit_event = {
            "timestamp": self._format_timestamp(record.created),
            "level": record.levelname,
            "event": getattr(record, "event", "unknown"),
            "user_id": getattr(record, "user_id", None),
            "username": getattr(record, "username", None),
            "role": getattr(record, "role", None),
            "srcip": getattr(record, "srcip", None),
            "http_method": getattr(record, "http_method", None),
            "request_path": getattr(record, "request_path", None),
            "user_agent": getattr(record, "user_agent", None),
            "status": getattr(record, "status", None),
            "reason": getattr(record, "reason", None),
        }
        
        # If we're in a request context and fields weren't explicitly set,
        # populate from the request
        if has_request_context():
            if audit_event["http_method"] is None:
                audit_event["http_method"] = request.method
            if audit_event["request_path"] is None:
                # Use path only, not full URL with query string
                audit_event["request_path"] = request.path
            if audit_event["srcip"] is None:
                audit_event["srcip"] = get_client_ip()
            if audit_event["user_agent"] is None:
                audit_event["user_agent"] = request.headers.get('User-Agent', '')
        
        # Remove None values for cleaner output (optional)
        # We keep them as null for schema consistency
        
        return json.dumps(audit_event, ensure_ascii=False, separators=(',', ':'))
    
    def _format_timestamp(self, created: float) -> str:
        """Format timestamp as ISO 8601 UTC with timezone."""
        dt = datetime.fromtimestamp(created, tz=timezone.utc)
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def create_security_audit_logger(app=None) -> logging.Logger:
    """Create and configure the dedicated security audit logger.
    
    Args:
        app: Optional Flask app for configuration. If provided,
             configures the logger with app's config.
    
    Returns:
        Configured security_audit logger instance.
    """
    logger = logging.getLogger('security_audit')
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't propagate to root logger
    
    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger
    
    # Determine log directory
    if app:
        log_dir = os.path.join(app.root_path, '..', 'logs')
    else:
        log_dir = os.path.join(os.getcwd(), 'logs')
    
    os.makedirs(log_dir, exist_ok=True)
    
    # Rotating file handler for JSON Lines audit log
    audit_log_path = os.path.join(log_dir, 'security_audit.json')
    
    file_handler = RotatingFileHandler(
        audit_log_path,
        maxBytes=10_000_000,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(JSONAuditFormatter())
    file_handler.setLevel(logging.INFO)
    
    logger.addHandler(file_handler)
    
    return logger


def get_security_audit_logger() -> logging.Logger:
    """Get the security audit logger instance.
    
    Creates it if it doesn't exist yet.
    """
    logger = logging.getLogger('security_audit')
    if not logger.handlers:
        return create_security_audit_logger()
    return logger


def log_auth_event(
    event: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    role: Optional[str] = None,
    srcip: Optional[str] = None,
    http_method: Optional[str] = None,
    request_path: Optional[str] = None,
    user_agent: Optional[str] = None,
    status: Optional[str] = None,
    reason: Optional[str] = None,
    level: int = logging.INFO
) -> None:
    """Log a security authentication event.
    
    This is a convenience function that creates a properly structured
    audit log entry with all required fields.
    
    Args:
        event: Event name (e.g., 'admin_login_success', 'user_login_success',
               'login_failed', 'user_logout')
        user_id: User ID
        username: Username
        role: User role (admin, customer, etc.)
        srcip: Source IP address
        http_method: HTTP method
        request_path: Request path
        user_agent: User-Agent string
        status: Event status (success, failure)
        reason: Failure reason (for login_failed events)
        level: Logging level
    """
    logger = get_security_audit_logger()
    
    # Sanitize username to prevent log injection
    safe_username = _sanitize_string(username) if username else None
    safe_user_agent = _sanitize_string(user_agent) if user_agent else None
    safe_reason = _sanitize_string(reason) if reason else None
    
    extra = {
        'event': event,
        'user_id': user_id,
        'username': safe_username,
        'role': role,
        'srcip': srcip,
        'http_method': http_method,
        'request_path': request_path,
        'user_agent': safe_user_agent,
        'status': status,
        'reason': safe_reason,
    }
    
    logger.log(level, event, extra=extra)


def _sanitize_string(value: Optional[str]) -> Optional[str]:
    """Sanitize string to prevent log injection.
    
    Removes control characters that could break JSON or
    be used for log injection attacks.
    """
    if value is None:
        return None
    # Remove control characters except normal whitespace
    return ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')