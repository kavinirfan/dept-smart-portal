from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AuditLog, Role, Subject, SubjectCredential, User
from ..schemas import (
    AuditOut,
    CredentialCreate,
    CredentialOut,
    SubjectCreate,
    SubjectOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..security import audit, get_current_user, hash_password, require_roles

router = APIRouter(prefix="/api", tags=["users"])
admin_only = require_roles(Role.admin)
staff = require_roles(Role.teacher, Role.lab_incharge, Role.admin)


# ---- Users -----------------------------------------------------------------

@router.get("/users", response_model=list[UserOut])
def list_users(role: Role | None = None, db: Session = Depends(get_db), _: User = Depends(staff)):
    query = select(User).order_by(User.role, User.name)
    if role:
        query = query.where(User.role == role)
    return db.scalars(query).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    if body.role == Role.student and not body.roll_no:
        raise HTTPException(status_code=422, detail="Students need a roll number")
    user = User(
        name=body.name,
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=body.role,
        roll_no=body.roll_no or None,
        department=body.department,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email or roll number already in use")
    audit(db, admin, "create", "user", user.user_id, f"{user.email} as {user.role.value}")
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = body.model_dump(exclude_unset=True)
    if user.user_id == admin.user_id and (changes.get("is_active") is False or changes.get("role", Role.admin) != Role.admin):
        raise HTTPException(status_code=400, detail="You cannot deactivate or demote yourself")
    for field, value in changes.items():
        setattr(user, field, value)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Roll number already in use")
    audit(db, admin, "update", "user", user.user_id, ", ".join(f"{k}={v}" for k, v in changes.items()))
    db.commit()
    db.refresh(user)
    return user


# ---- Subjects & subject-level credentials ------------------------------------

@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.scalars(select(Subject).order_by(Subject.semester, Subject.subject_code)).all()


@router.post("/subjects", response_model=SubjectOut, status_code=201)
def create_subject(body: SubjectCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    subject = Subject(**body.model_dump())
    db.add(subject)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Subject code already exists")
    audit(db, admin, "create", "subject", subject.subject_id, subject.subject_code)
    db.commit()
    db.refresh(subject)
    return subject


@router.get("/credentials", response_model=list[CredentialOut])
def list_credentials(user_id: int | None = None, db: Session = Depends(get_db), user: User = Depends(staff)):
    query = select(SubjectCredential)
    # Teachers only see their own credentials; admins can see anyone's.
    if user.role != Role.admin:
        query = query.where(SubjectCredential.user_id == user.user_id)
    elif user_id:
        query = query.where(SubjectCredential.user_id == user_id)
    return db.scalars(query).all()


@router.post("/credentials", response_model=CredentialOut, status_code=201)
def grant_credential(body: CredentialCreate, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    teacher = db.get(User, body.user_id)
    if teacher is None or teacher.role != Role.teacher:
        raise HTTPException(status_code=422, detail="Credentials can only be granted to teachers")
    if db.get(Subject, body.subject_id) is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    cred = SubjectCredential(user_id=body.user_id, subject_id=body.subject_id, granted_by=admin.user_id)
    db.add(cred)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Teacher already has this subject")
    audit(db, admin, "grant", "subject_credential", cred.credential_id, f"user {body.user_id} -> subject {body.subject_id}")
    db.commit()
    db.refresh(cred)
    return cred


@router.delete("/credentials/{credential_id}", status_code=204)
def revoke_credential(credential_id: int, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    cred = db.get(SubjectCredential, credential_id)
    if cred is None:
        raise HTTPException(status_code=404, detail="Credential not found")
    audit(db, admin, "revoke", "subject_credential", cred.credential_id, f"user {cred.user_id} -> subject {cred.subject_id}")
    db.delete(cred)
    db.commit()


# ---- Audit log ---------------------------------------------------------------

@router.get("/audit", response_model=list[AuditOut])
def audit_log(limit: int = 100, db: Session = Depends(get_db), _: User = Depends(admin_only)):
    return db.scalars(select(AuditLog).order_by(AuditLog.log_id.desc()).limit(min(limit, 500))).all()
