"""Job and internship notice board: anyone signed in can read and post."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Notice, NoticeType, Role, User
from ..security import audit, get_current_user, notify

router = APIRouter(prefix="/api/notices", tags=["notices"])


class NoticeIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    company: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=5000)
    type: NoticeType
    deadline: date | None = None
    link: HttpUrl | None = None


def notice_out(n: Notice) -> dict:
    return {
        "notice_id": n.notice_id, "title": n.title, "company": n.company, "description": n.description,
        "type": n.type, "deadline": n.deadline, "link": n.link, "posted_on": n.posted_on,
        "posted_by": n.posted_by, "posted_by_name": n.poster.name, "posted_by_role": n.poster.role,
        "expired": bool(n.deadline and n.deadline < date.today()),
    }


@router.get("")
def list_notices(type: NoticeType | None = None, q: str | None = None, include_expired: bool = False,
                 db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = select(Notice).order_by(Notice.posted_on.desc())
    if type:
        query = query.where(Notice.type == type)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Notice.title.ilike(like), Notice.company.ilike(like), Notice.description.ilike(like)))
    if not include_expired:
        query = query.where(or_(Notice.deadline.is_(None), Notice.deadline >= date.today()))
    return [notice_out(n) for n in db.scalars(query)]


@router.post("", status_code=201)
def create_notice(body: NoticeIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if body.deadline and body.deadline < date.today():
        raise HTTPException(status_code=422, detail="Deadline is already past")
    data = body.model_dump()
    data["link"] = str(body.link) if body.link else None
    n = Notice(**data, posted_by=user.user_id)
    db.add(n)
    db.flush()
    audit(db, user, "create", "notice", n.notice_id, f"{n.type.value}: {n.title} @ {n.company}")
    everyone = db.scalars(select(User.user_id).where(User.is_active))
    notify(db, everyone, "new_notice", f"New {n.type.value}: {n.title} at {n.company}", "/notices", n.notice_id, skip=user.user_id)
    db.commit()
    db.refresh(n)
    return notice_out(n)


@router.delete("/{notice_id}", status_code=204)
def delete_notice(notice_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notice, notice_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Notice not found")
    if user.role != Role.admin and n.posted_by != user.user_id:
        raise HTTPException(status_code=403, detail="Only the poster or admin can remove a notice")
    audit(db, user, "delete", "notice", n.notice_id, f"{n.title} @ {n.company}")
    db.delete(n)
    db.commit()
