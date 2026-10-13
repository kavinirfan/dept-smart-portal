"""Faculty self-reported availability. Every change is kept as history."""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FacultyState, FacultyStatus, Role, User
from ..security import audit, get_current_user, require_roles

router = APIRouter(prefix="/api/faculty", tags=["faculty"])
FACULTY_ROLES = (Role.teacher, Role.lab_incharge, Role.admin)


class StatusIn(BaseModel):
    status: FacultyState
    note: str | None = Field(default=None, max_length=200)


def latest_statuses(db: Session) -> dict[int, FacultyStatus]:
    latest = select(FacultyStatus.faculty_id, func.max(FacultyStatus.status_id).label("sid")).group_by(FacultyStatus.faculty_id).subquery()
    rows = db.scalars(select(FacultyStatus).join(latest, FacultyStatus.status_id == latest.c.sid))
    return {r.faculty_id: r for r in rows}


@router.get("")
def board(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    current = latest_statuses(db)
    faculty = db.scalars(select(User).where(User.role.in_(FACULTY_ROLES), User.is_active).order_by(User.name))
    out = []
    for f in faculty:
        s = current.get(f.user_id)
        out.append({
            "faculty_id": f.user_id, "name": f.name, "role": f.role,
            # Nobody has reported yet: say so rather than guessing.
            "status": s.status.value if s else None,
            "note": s.note if s else None,
            "updated_at": s.updated_at if s else None,
        })
    return out


@router.post("/status")
def set_my_status(body: StatusIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*FACULTY_ROLES))):
    row = FacultyStatus(faculty_id=user.user_id, status=body.status, note=(body.note or "").strip() or None)
    db.add(row)
    db.flush()
    audit(db, user, "status", "faculty_status", row.status_id, f"{body.status.value}{' - ' + row.note if row.note else ''}")
    db.commit()
    return {"status": row.status.value, "note": row.note, "updated_at": row.updated_at}


@router.get("/history/{faculty_id}")
def history(faculty_id: int, days: int = 7, db: Session = Depends(get_db), user: User = Depends(require_roles(*FACULTY_ROLES))):
    if user.role != Role.admin and user.user_id != faculty_id:
        raise HTTPException(status_code=403, detail="You can only see your own history")
    since = datetime.combine(date.today() - timedelta(days=max(days, 1) - 1), time.min)
    rows = db.scalars(
        select(FacultyStatus).where(FacultyStatus.faculty_id == faculty_id, FacultyStatus.updated_at >= since)
        .order_by(FacultyStatus.status_id.desc())
    )
    return [{"status": r.status.value, "note": r.note, "updated_at": r.updated_at} for r in rows]
