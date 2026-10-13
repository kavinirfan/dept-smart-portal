"""In-app notifications: each user sees only their own."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notification, User
from ..security import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def my_notifications(limit: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(
        select(Notification).where(Notification.user_id == user.user_id)
        .order_by(Notification.notification_id.desc()).limit(min(limit, 100))
    )
    unread = db.scalar(select(func.count()).where(Notification.user_id == user.user_id, Notification.is_read.is_(False)))
    return {
        "unread": unread,
        "items": [{
            "notification_id": n.notification_id, "type": n.type, "message": n.message, "link": n.link,
            "is_read": n.is_read, "created_at": n.created_at,
        } for n in rows],
    }


@router.post("/{notification_id}/read", status_code=204)
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.is_read = True
    db.commit()


@router.post("/read-all", status_code=204)
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.execute(update(Notification).where(Notification.user_id == user.user_id).values(is_read=True))
    db.commit()
