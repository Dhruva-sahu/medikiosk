"""Auth API: register, login, me, logout (client-side token discard)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ClinicianProfile, Consent, PatientProfile, User
from app.schemas import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.security.deps import get_current_user, log_audit
from app.utils import ok

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        phone=payload.phone,
        role=payload.role,
        preferred_language=payload.preferred_language,
        abha_id=payload.abha_id,
    )
    db.add(user)
    db.flush()

    if payload.role == "PATIENT":
        db.add(PatientProfile(
            user_id=user.id,
            date_of_birth=payload.date_of_birth,
            gender=payload.gender,
            blood_group=payload.blood_group,
        ))
    else:
        db.add(ClinicianProfile(
            user_id=user.id,
            specialty=payload.specialty or "General Medicine",
            registration_number=payload.registration_number,
            department=payload.department,
        ))

    # Implicit consent on registration
    if payload.role == "PATIENT":
        db.add(Consent(
            patient_id=user.id,
            scope='["history","documents","ai_processing","summary","his_share","abdm_share"]',
            purpose="Account registration - default clinical intake consent",
        ))

    db.commit()
    db.refresh(user)

    log_audit(db, actor=user, action="PATIENT_CREATED" if payload.role == "PATIENT" else "USER_CREATED",
              resource_type="user", resource_id=user.id, request=request)

    return TokenResponse(
        access_token=create_access_token(subject=user.id, role=user.role),
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")
    log_audit(db, actor=user, action="LOGIN", resource_type="user", resource_id=user.id, request=request)
    return TokenResponse(
        access_token=create_access_token(subject=user.id, role=user.role),
        user=UserOut.model_validate(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), request: Request = None, db: Session = Depends(get_db)):
    log_audit(db, actor=user, action="LOGOUT", resource_type="user", resource_id=user.id, request=request)
    return ok(message="Logged out. Discard the access token client-side.")
