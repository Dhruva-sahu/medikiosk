"""FastAPI dependencies for authentication and RBAC."""
from __future__ import annotations

from typing import Iterable, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, User
from app.security import decode_access_token


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}") from exc

    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_roles(*allowed: str):
    allowed_set = {r.upper() for r in allowed}

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role.upper() not in allowed_set:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden for this role")
        return user

    return _dep


def log_audit(
    db: Session,
    *,
    actor: Optional[User],
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    detail: Optional[str] = None,
    request: Optional[Request] = None,
) -> None:
    """Persist an audit log entry."""
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_role=actor.role if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=request.client.host if request and request.client else None,
    )
    db.add(entry)
    db.commit()


def client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


# Common role guards
require_patient = require_roles("PATIENT")
require_clinician = require_roles("CLINICIAN", "ADMIN")
require_admin = require_roles("ADMIN")
require_any_user = require_roles("PATIENT", "CLINICIAN", "ADMIN")
