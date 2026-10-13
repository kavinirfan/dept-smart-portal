"""Split marks: teachers holding a subject credential enter question-wise marks;
students see only their own breakdown, staff can look up any student."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Mark, MarkComponent, Role, Subject, SubjectCredential, User
from ..schemas import SubjectOut
from ..security import audit, get_current_user, notify, require_roles

router = APIRouter(prefix="/api/marks", tags=["marks"])
markers = require_roles(Role.teacher, Role.admin)


class ComponentIn(BaseModel):
    subject_id: int
    name: str = Field(min_length=1, max_length=60)
    question_max: list[float] = Field(min_length=1, max_length=30)
    weightage: float = Field(gt=0, le=100)


class ComponentOut(BaseModel):
    component_id: int
    subject_id: int
    name: str
    question_max: list[float]
    max_marks: float
    weightage: float


class SheetEntry(BaseModel):
    student_id: int
    question_marks: list[float | None]
    absent: bool = False


class SheetRow(BaseModel):
    student_id: int
    name: str
    roll_no: str | None
    question_marks: list[float | None] | None
    marks_obtained: float | None
    absent: bool


def component_out(c: MarkComponent) -> ComponentOut:
    return ComponentOut(
        component_id=c.component_id, subject_id=c.subject_id, name=c.name,
        question_max=c.question_max, max_marks=c.max_marks, weightage=c.weightage,
    )


def credentialed_subject_ids(db: Session, user: User) -> set[int] | None:
    """Subjects this user may enter marks for. None means all (admin)."""
    if user.role == Role.admin:
        return None
    if user.role != Role.teacher:
        return set()
    return set(db.scalars(select(SubjectCredential.subject_id).where(SubjectCredential.user_id == user.user_id)))


def require_credential(db: Session, user: User, subject_id: int):
    allowed = credentialed_subject_ids(db, user)
    if allowed is not None and subject_id not in allowed:
        raise HTTPException(status_code=403, detail="You do not hold the marks credential for this subject")


@router.get("/my-subjects", response_model=list[SubjectOut])
def my_subjects(db: Session = Depends(get_db), user: User = Depends(markers)):
    allowed = credentialed_subject_ids(db, user)
    query = select(Subject).order_by(Subject.subject_code)
    if allowed is not None:
        query = query.where(Subject.subject_id.in_(allowed))
    return db.scalars(query).all()


@router.get("/components", response_model=list[ComponentOut])
def list_components(subject_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.scalars(select(MarkComponent).where(MarkComponent.subject_id == subject_id).order_by(MarkComponent.component_id))
    return [component_out(c) for c in rows]


@router.post("/components", response_model=ComponentOut, status_code=201)
def create_component(body: ComponentIn, db: Session = Depends(get_db), user: User = Depends(markers)):
    require_credential(db, user, body.subject_id)
    if any(q <= 0 for q in body.question_max):
        raise HTTPException(status_code=422, detail="Every question needs a maximum above zero")
    comp = MarkComponent(**body.model_dump())
    db.add(comp)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This subject already has a component with that name")
    audit(db, user, "create", "mark_component", comp.component_id, f"{body.name} ({comp.max_marks:g} marks, {body.weightage:g}%)")
    db.commit()
    return component_out(comp)


@router.get("/sheet/{component_id}", response_model=list[SheetRow])
def get_sheet(component_id: int, db: Session = Depends(get_db), user: User = Depends(markers)):
    comp = db.get(MarkComponent, component_id) or _404()
    require_credential(db, user, comp.subject_id)
    students = db.scalars(select(User).where(User.role == Role.student, User.is_active).order_by(User.roll_no))
    marks = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.component_id == component_id))}
    rows = []
    for s in students:
        m = marks.get(s.user_id)
        rows.append(SheetRow(
            student_id=s.user_id, name=s.name, roll_no=s.roll_no,
            question_marks=m.question_marks if m else None,
            marks_obtained=m.marks_obtained if m else None,
            absent=m.absent if m else False,
        ))
    return rows


@router.put("/sheet/{component_id}")
def save_sheet(component_id: int, entries: list[SheetEntry], db: Session = Depends(get_db), user: User = Depends(markers)):
    comp = db.get(MarkComponent, component_id) or _404()
    require_credential(db, user, comp.subject_id)
    student_ids = set(db.scalars(select(User.user_id).where(User.role == Role.student)))
    existing = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.component_id == component_id))}
    saved = 0
    changed: list[tuple[int, float, bool]] = []
    for e in entries:
        if e.student_id not in student_ids:
            raise HTTPException(status_code=422, detail=f"User {e.student_id} is not a student")
        if e.absent:
            qm = [None] * len(comp.question_max)
        else:
            if len(e.question_marks) != len(comp.question_max):
                raise HTTPException(status_code=422, detail=f"Expected {len(comp.question_max)} question marks")
            for i, (got, mx) in enumerate(zip(e.question_marks, comp.question_max), start=1):
                if got is not None and not 0 <= got <= mx:
                    raise HTTPException(status_code=422, detail=f"Q{i} must be between 0 and {mx:g}")
            qm = e.question_marks
            if all(q is None for q in qm):
                continue  # nothing entered for this student yet
        total = float(sum(q for q in qm if q is not None))
        m = existing.get(e.student_id)
        if m is None:
            db.add(Mark(student_id=e.student_id, component_id=component_id, question_marks=qm,
                        marks_obtained=total, absent=e.absent, entered_by=user.user_id))
        elif m.question_marks == qm and m.absent == e.absent:
            continue
        else:
            audit(db, user, "update", "mark", m.mark_id,
                  f"student {e.student_id} {comp.name}: {m.marks_obtained:g} -> {total:g}")
            m.question_marks, m.marks_obtained, m.absent, m.entered_by = qm, total, e.absent, user.user_id
        saved += 1
        changed.append((e.student_id, total, e.absent))
    if saved:
        audit(db, user, "save", "mark_sheet", component_id, f"{comp.subject.subject_code} {comp.name}: {saved} rows")
    for sid, total, absent in changed:
        result = "marked absent" if absent else f"{total:g}/{comp.max_marks:g}"
        notify(db, [sid], "marks_confirmed", f"{comp.subject.subject_code} {comp.name} marks updated: {result}", "/marks", component_id)
    db.commit()
    return {"saved": saved}


@router.get("/student/{student_id}")
def student_report(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Full breakdown for one student, with the class average per component for comparison."""
    if user.role == Role.student and user.user_id != student_id:
        raise HTTPException(status_code=403, detail="Students can only see their own marks")
    if user.role == Role.lab_incharge:
        raise HTTPException(status_code=403, detail="Not allowed for your role")
    student = db.get(User, student_id)
    if student is None or student.role != Role.student:
        _404()
    visible = credentialed_subject_ids(db, user) if user.role == Role.teacher else None

    averages = dict(db.execute(
        select(Mark.component_id, func.avg(Mark.marks_obtained)).where(Mark.absent.is_(False)).group_by(Mark.component_id)
    ).all())
    marks = {m.component_id: m for m in db.scalars(select(Mark).where(Mark.student_id == student_id))}
    subjects = []
    for subj in db.scalars(select(Subject).order_by(Subject.subject_code)):
        if visible is not None and subj.subject_id not in visible:
            continue
        comps = db.scalars(select(MarkComponent).where(MarkComponent.subject_id == subj.subject_id).order_by(MarkComponent.component_id)).all()
        if not comps:
            continue
        items, internal, weight_done = [], 0.0, 0.0
        for c in comps:
            m = marks.get(c.component_id)
            weighted = None
            if m is not None:
                weighted = round(m.marks_obtained / c.max_marks * c.weightage, 2)
                internal += weighted
                weight_done += c.weightage
            items.append({
                **component_out(c).model_dump(),
                "question_marks": m.question_marks if m else None,
                "marks_obtained": m.marks_obtained if m else None,
                "absent": m.absent if m else False,
                "weighted": weighted,
                "class_average": round(averages[c.component_id], 2) if c.component_id in averages else None,
            })
        subjects.append({
            "subject": SubjectOut.model_validate(subj).model_dump(),
            "components": items,
            "internal": round(internal, 2),
            "internal_out_of": sum(c.weightage for c in comps),
            "assessed_out_of": weight_done,
        })
    return {"student": {"user_id": student.user_id, "name": student.name, "roll_no": student.roll_no}, "subjects": subjects}


def _404():
    raise HTTPException(status_code=404, detail="Not found")
