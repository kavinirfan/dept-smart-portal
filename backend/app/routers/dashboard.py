"""HOD real-time overview (Section 4.7). No tables of its own: it only aggregates the other modules."""
from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (AuditLog, ChatMessage, IdCardRegistration, Lab, LabBooking, LabStatus, Mark, MarkComponent,
                      Notice, RegistrationStatus, Role, Subject, User)
from ..security import require_roles
from .chat import hub
from .faculty import FACULTY_ROLES, latest_statuses

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
AT_RISK_BELOW = 50.0  # % of the internal assessed so far
WORKING_HOURS_PER_DAY = 8


@router.get("")
def overview(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.admin))):
    now = datetime.now()
    today = date.today()
    users = db.scalars(select(User).where(User.is_active)).all()
    by_role = defaultdict(int)
    for u in users:
        by_role[u.role.value] += 1
    names = {u.user_id: u for u in users}

    # Labs: live status plus booked hours this week (Mon-Sat).
    week_start = datetime.combine(today - timedelta(days=today.weekday()), time.min)
    week_end = week_start + timedelta(days=6)
    labs_out, lab_status = [], defaultdict(int)
    for lab in db.scalars(select(Lab).order_by(Lab.lab_name)):
        live = db.scalar(select(LabBooking).where(LabBooking.lab_id == lab.lab_id, LabBooking.cancelled.is_(False),
                                                  LabBooking.start_time <= now, LabBooking.end_time > now))
        status = "maintenance" if lab.current_status == LabStatus.maintenance else ("occupied" if live or lab.current_status == LabStatus.occupied else "free")
        lab_status[status] += 1
        week = db.scalars(select(LabBooking).where(LabBooking.lab_id == lab.lab_id, LabBooking.cancelled.is_(False),
                                                   LabBooking.start_time >= week_start, LabBooking.start_time < week_end)).all()
        hours = sum((b.end_time - b.start_time).total_seconds() for b in week) / 3600
        labs_out.append({"lab_id": lab.lab_id, "lab_name": lab.lab_name, "status": status,
                         "booked_hours_week": round(hours, 1),
                         "utilisation_week": round(hours / (6 * WORKING_HOURS_PER_DAY) * 100, 1)})
    day_start = datetime.combine(today, time.min)
    bookings_today = db.scalar(select(func.count()).where(LabBooking.cancelled.is_(False), LabBooking.start_time >= day_start,
                                                          LabBooking.start_time < day_start + timedelta(days=1)))

    # Faculty presence right now.
    current = latest_statuses(db)
    faculty_counts = defaultdict(int)
    for u in users:
        if u.role in FACULTY_ROLES:
            s = current.get(u.user_id)
            faculty_counts[s.status.value if s else "Not reported"] += 1

    # Marks: average internal per subject and students below the at-risk line.
    comps = db.scalars(select(MarkComponent)).all()
    comp_by_id = {c.component_id: c for c in comps}
    marks = db.scalars(select(Mark)).all()
    per_student = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # subject -> student -> [weighted, weight]
    for m in marks:
        c = comp_by_id[m.component_id]
        acc = per_student[c.subject_id][m.student_id]
        acc[0] += m.marks_obtained / c.max_marks * c.weightage
        acc[1] += c.weightage
    subjects_out, at_risk = [], []
    for subj in db.scalars(select(Subject).order_by(Subject.subject_code)):
        sc = [c for c in comps if c.subject_id == subj.subject_id]
        entered = {m.component_id for m in marks if comp_by_id[m.component_id].subject_id == subj.subject_id}
        pcts = []
        for sid, (w, wt) in per_student[subj.subject_id].items():
            if wt:
                p = w / wt * 100
                pcts.append(p)
                if p < AT_RISK_BELOW and sid in names:
                    at_risk.append({"student_id": sid, "name": names[sid].name, "roll_no": names[sid].roll_no,
                                    "subject_code": subj.subject_code, "percent": round(p, 1)})
        subjects_out.append({"subject_code": subj.subject_code, "subject_name": subj.subject_name,
                             "average_percent": round(sum(pcts) / len(pcts), 1) if pcts else None,
                             "tests_entered": len(entered), "tests_total": len(sc)})
    at_risk.sort(key=lambda r: r["percent"])

    # Notices
    active = db.scalars(select(Notice).where((Notice.deadline.is_(None)) | (Notice.deadline >= today))).all()
    closing = sorted([n for n in active if n.deadline and n.deadline <= today + timedelta(days=7)], key=lambda n: n.deadline)

    # Chat & verification
    pending_ids = db.scalar(select(func.count()).where(IdCardRegistration.status == RegistrationStatus.pending))
    reported = db.scalar(select(func.count()).where(ChatMessage.reported.is_(True), ChatMessage.hidden.is_(False)))
    messages_today = db.scalar(select(func.count()).where(ChatMessage.sent_at >= datetime.combine(today, time.min)))

    recent = db.scalars(select(AuditLog).order_by(AuditLog.log_id.desc()).limit(8)).all()
    return {
        "generated_at": now.isoformat(),
        "people": dict(by_role),
        "labs": labs_out,
        "lab_status": dict(lab_status),
        "bookings_today": bookings_today,
        "faculty": dict(faculty_counts),
        "subjects": subjects_out,
        "at_risk": at_risk[:15],
        "at_risk_threshold": AT_RISK_BELOW,
        "notices_active": len(active),
        "notices_closing": [{"notice_id": n.notice_id, "title": n.title, "company": n.company, "deadline": n.deadline} for n in closing],
        "chat": {"pending_ids": pending_ids, "reported": reported, "messages_today": messages_today, "online": hub.online()},
        "recent": [{"when": a.created_at, "who": names[a.user_id].name if a.user_id in names else None,
                    "action": a.action, "entity": a.entity, "details": a.details} for a in recent],
    }
