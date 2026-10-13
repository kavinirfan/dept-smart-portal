"""Lab availability and first-come-first-served booking."""
import threading
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Lab, LabBooking, LabStatus, Role, User, utcnow
from ..security import audit, get_current_user, notify, require_roles

router = APIRouter(prefix="/api/labs", tags=["labs"])
bookers = require_roles(Role.teacher, Role.lab_incharge, Role.admin)
MAX_BOOKING = timedelta(hours=8)
# Serialises the check-then-insert so two simultaneous requests cannot both win a slot.
# (On PostgreSQL the row lock below does the same job across processes.)
_booking_lock = threading.Lock()


class LabIn(BaseModel):
    lab_name: str = Field(min_length=1, max_length=80)
    capacity: int = Field(default=30, ge=1)
    incharge_id: int | None = None


class StatusIn(BaseModel):
    status: LabStatus


class BookingIn(BaseModel):
    lab_id: int
    start_time: datetime
    end_time: datetime
    purpose: str = Field(min_length=1, max_length=200)


def booking_out(b: LabBooking) -> dict:
    return {
        "booking_id": b.booking_id, "lab_id": b.lab_id, "lab_name": b.lab.lab_name,
        "booked_by": b.booked_by, "booked_by_name": b.booker.name,
        "start_time": b.start_time, "end_time": b.end_time, "purpose": b.purpose,
        "created_at": b.created_at,
    }


def active_bookings(db: Session, lab_id: int | None, start: datetime, end: datetime):
    """Non-cancelled bookings that overlap [start, end)."""
    q = select(LabBooking).where(
        LabBooking.cancelled.is_(False), LabBooking.start_time < end, LabBooking.end_time > start
    ).order_by(LabBooking.start_time)
    if lab_id is not None:
        q = q.where(LabBooking.lab_id == lab_id)
    return db.scalars(q).all()


@router.get("")
def list_labs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    now = datetime.now()
    end_of_day = datetime.combine(now.date(), datetime.max.time())
    out = []
    for lab in db.scalars(select(Lab).order_by(Lab.lab_name)):
        current = active_bookings(db, lab.lab_id, now, now + timedelta(seconds=1))
        upcoming = [b for b in active_bookings(db, lab.lab_id, now, end_of_day) if b.start_time > now]
        out.append({
            "lab_id": lab.lab_id, "lab_name": lab.lab_name, "capacity": lab.capacity,
            "incharge_id": lab.incharge_id, "incharge_name": lab.incharge.name if lab.incharge else None,
            "current_status": lab.current_status, "status_updated_at": lab.status_updated_at,
            "current_booking": booking_out(current[0]) if current else None,
            "next_booking": booking_out(upcoming[0]) if upcoming else None,
        })
    return out


@router.post("", status_code=201)
def create_lab(body: LabIn, db: Session = Depends(get_db), admin: User = Depends(require_roles(Role.admin))):
    if body.incharge_id is not None:
        inc = db.get(User, body.incharge_id)
        if inc is None or inc.role not in (Role.lab_incharge, Role.admin):
            raise HTTPException(status_code=422, detail="In-charge must be a lab in-charge")
    lab = Lab(**body.model_dump())
    db.add(lab)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A lab with that name exists")
    audit(db, admin, "create", "lab", lab.lab_id, lab.lab_name)
    db.commit()
    return {"lab_id": lab.lab_id}


@router.patch("/{lab_id}/status")
def set_status(lab_id: int, body: StatusIn, db: Session = Depends(get_db), user: User = Depends(require_roles(Role.lab_incharge, Role.admin))):
    lab = db.get(Lab, lab_id)
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    if user.role != Role.admin and lab.incharge_id != user.user_id:
        raise HTTPException(status_code=403, detail="Only this lab's in-charge can change its status")
    old = lab.current_status
    lab.current_status, lab.status_updated_at = body.status, utcnow()
    audit(db, user, "status", "lab", lab.lab_id, f"{lab.lab_name}: {old.value} -> {body.status.value}")
    if body.status == LabStatus.maintenance and old != LabStatus.maintenance:
        # Warn everyone holding an upcoming slot so they can move their class.
        now = datetime.now()
        for b in active_bookings(db, lab.lab_id, now, now + timedelta(days=30)):
            notify(db, [b.booked_by], "conflict",
                   f"{lab.lab_name} is under maintenance. Your booking {b.start_time:%d %b %H:%M} may need to move.",
                   "/labs", b.booking_id, skip=user.user_id)
    db.commit()
    return {"lab_id": lab.lab_id, "current_status": lab.current_status}


@router.get("/bookings")
def list_bookings(day: date | None = None, lab_id: int | None = None, mine: bool = False,
                  db: Session = Depends(get_db), user: User = Depends(bookers)):
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    rows = active_bookings(db, lab_id, start, start + timedelta(days=1))
    if mine:
        rows = [b for b in rows if b.booked_by == user.user_id]
    return [booking_out(b) for b in rows]


@router.post("/bookings", status_code=201)
def create_booking(body: BookingIn, db: Session = Depends(get_db), user: User = Depends(bookers)):
    start, end = body.start_time.replace(tzinfo=None, second=0, microsecond=0), body.end_time.replace(tzinfo=None, second=0, microsecond=0)
    if end <= start:
        raise HTTPException(status_code=422, detail="End time must be after start time")
    if end - start > MAX_BOOKING:
        raise HTTPException(status_code=422, detail="A booking can be at most 8 hours")
    if end <= datetime.now():
        raise HTTPException(status_code=422, detail="That time has already passed")
    with _booking_lock:
        return _book(db, user, body.lab_id, start, end, body.purpose)


def _book(db: Session, user: User, lab_id: int, start: datetime, end: datetime, purpose: str):
    lab = db.scalar(select(Lab).where(Lab.lab_id == lab_id).with_for_update())
    if lab is None:
        raise HTTPException(status_code=404, detail="Lab not found")
    if lab.current_status == LabStatus.maintenance:
        raise HTTPException(status_code=409, detail=f"{lab.lab_name} is under maintenance")
    # First come, first served: whoever saved first holds the slot.
    clash = active_bookings(db, lab.lab_id, start, end)
    if clash:
        c = clash[0]
        raise HTTPException(status_code=409, detail=(
            f"{lab.lab_name} is already booked {c.start_time:%H:%M}-{c.end_time:%H:%M} by {c.booker.name}"
        ))
    booking = LabBooking(lab_id=lab.lab_id, booked_by=user.user_id, start_time=start, end_time=end, purpose=purpose)
    db.add(booking)
    db.flush()
    audit(db, user, "book", "lab_booking", booking.booking_id, f"{lab.lab_name} {start:%d %b %H:%M}-{end:%H:%M}")
    if lab.incharge_id:
        notify(db, [lab.incharge_id], "booking_approved",
               f"{user.name} booked {lab.lab_name} {start:%d %b %H:%M}-{end:%H:%M}: {purpose}", "/labs", booking.booking_id,
               skip=user.user_id)
    db.commit()
    db.refresh(booking)
    return booking_out(booking)


@router.delete("/bookings/{booking_id}", status_code=204)
def cancel_booking(booking_id: int, db: Session = Depends(get_db), user: User = Depends(bookers)):
    b = db.get(LabBooking, booking_id)
    if b is None or b.cancelled:
        raise HTTPException(status_code=404, detail="Booking not found")
    if user.role != Role.admin and user.user_id not in (b.booked_by, b.lab.incharge_id):
        raise HTTPException(status_code=403, detail="Only the person who booked, the lab in-charge or admin can cancel")
    b.cancelled = True
    notify(db, [b.booked_by], "booking_cancelled",
           f"{user.name} cancelled your {b.lab.lab_name} booking {b.start_time:%d %b %H:%M}", "/labs", b.booking_id, skip=user.user_id)
    audit(db, user, "cancel", "lab_booking", b.booking_id, f"{b.lab.lab_name} {b.start_time:%d %b %H:%M}")
    db.commit()
