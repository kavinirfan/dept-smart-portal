"""Create demo users, subjects, marks, labs, faculty status, notices, ID cards, chat and notifications. Run with: python -m app.seed  (add --reset to wipe first)."""
import random
import struct
import sys
import uuid
import zlib
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import (
    ChatMessage, FacultyState, FacultyStatus, IdCardRegistration, Lab, LabBooking, Mark, MarkComponent, Notice,
    NoticeType, Notification, RegistrationStatus, Role, Subject, SubjectCredential, User,
)
from .security import hash_password

DEMO_PASSWORD = "portal123"

USERS = [
    ("Dr. Meena Raghavan", "hod@dept.edu", Role.admin, None),
    ("Prof. Arjun Kumar", "arjun@dept.edu", Role.teacher, None),
    ("Prof. Lakshmi Iyer", "lakshmi@dept.edu", Role.teacher, None),
    ("Prof. Rahul Menon", "rahul@dept.edu", Role.teacher, None),
    ("Mr. Suresh Babu", "labincharge@dept.edu", Role.lab_incharge, None),
    ("Kavin S", "kavin@dept.edu", Role.student, "21CS001"),
    ("Priya R", "priya@dept.edu", Role.student, "21CS002"),
    ("Aditya N", "aditya@dept.edu", Role.student, "21CS003"),
    ("Divya M", "divya@dept.edu", Role.student, "21CS004"),
    ("Farhan A", "farhan@dept.edu", Role.student, "21CS005"),
    ("Gayathri K", "gayathri@dept.edu", Role.student, "21CS006"),
]

SUBJECTS = [
    ("CS501", "Database Management Systems", 5),
    ("CS502", "Computer Networks", 5),
    ("CS503", "Machine Learning", 5),
    ("CS504", "Software Engineering", 5),
]

# teacher email -> subject codes they may enter marks for
CREDENTIALS = {
    "arjun@dept.edu": ["CS501", "CS504"],
    "lakshmi@dept.edu": ["CS502"],
    "rahul@dept.edu": ["CS503"],
}


# name, per-question max marks, weightage (% of the internal)
COMPONENTS = [
    ("CAT-1", [10, 10, 10, 10, 10], 15),
    ("CAT-2", [10, 10, 10, 10, 10], 15),
    ("Assignment", [5, 5], 10),
]

LABS = [("Programming Lab 1", 40), ("Programming Lab 2", 40), ("Networks Lab", 30)]

NOTICES = [
    (NoticeType.internship, "Summer Data Science Intern", "Zoho", 25, "https://careers.zohocorp.com",
     "8-week internship on analytics dashboards. Python and SQL required. Stipend provided."),
    (NoticeType.job, "Graduate Software Engineer", "Freshworks", 40, "https://www.freshworks.com/company/careers/",
     "Full-time role for 2026 graduates. Two coding rounds and one system design round."),
    (NoticeType.internship, "ML Research Intern", "IIT Madras - RBCDSAI", 12, None,
     "Research internship on medical imaging. Send CV and a one-page statement to the department office."),
    (NoticeType.internship, "Web Development Intern (remote)", "Local startup via alumni cell", 6, None,
     "React + FastAPI internship, 3 months, remote. Contact the placement coordinator."),
    (NoticeType.job, "Associate Network Engineer", "Tata Communications", -3, None,
     "Campus drive notice (deadline passed; kept to show expired notices are hidden by default)."),
]


def _seed_modules(db, users, subjects):
    rng = random.Random(7)
    admin = users["hod@dept.edu"]
    students = [u for u in users.values() if u.role == Role.student]
    teacher_for = {code: email for email, codes in CREDENTIALS.items() for code in codes}

    # Marks: CAT-1 and the assignment for every subject, CAT-2 only for the first two.
    for i, (code, subject) in enumerate(subjects.items()):
        teacher = users[teacher_for[code]]
        for name, qmax, weight in COMPONENTS:
            comp = MarkComponent(subject_id=subject.subject_id, name=name, question_max=qmax, weightage=weight)
            db.add(comp)
            db.flush()
            if name == "CAT-2" and i >= 2:
                continue  # not conducted yet
            for s in students:
                skill = 0.45 + (sum(map(ord, s.email)) % 40) / 100  # each student has a consistent ability level
                if rng.random() < 0.04:
                    db.add(Mark(student_id=s.user_id, component_id=comp.component_id, question_marks=[None] * len(qmax),
                                marks_obtained=0, absent=True, entered_by=teacher.user_id))
                    continue
                qm = [min(q, max(0, round(q * (skill + rng.uniform(-0.2, 0.25)) * 2) / 2)) for q in qmax]
                db.add(Mark(student_id=s.user_id, component_id=comp.component_id, question_marks=qm,
                            marks_obtained=float(sum(qm)), entered_by=teacher.user_id))

    # Labs and a few bookings around today.
    incharge = users["labincharge@dept.edu"]
    labs = []
    for name, cap in LABS:
        lab = Lab(lab_name=name, capacity=cap, incharge_id=incharge.user_id)
        db.add(lab)
        labs.append(lab)
    db.flush()
    today = date.today()
    at = lambda d, h, m=0: datetime.combine(today + timedelta(days=d), time(h, m))
    for lab, d, start, end, email, purpose in [
        (labs[0], 0, 9, 11, "arjun@dept.edu", "DBMS lab - batch A"),
        (labs[0], 0, 14, 16, "rahul@dept.edu", "ML lab - model training"),
        (labs[1], 0, 11, 13, "arjun@dept.edu", "Software Engineering project review"),
        (labs[2], 0, 10, 12, "lakshmi@dept.edu", "Networks lab - packet tracer"),
        (labs[2], 1, 9, 11, "lakshmi@dept.edu", "Networks lab - batch B"),
        (labs[1], 1, 13, 15, "rahul@dept.edu", "Extra ML session"),
    ]:
        db.add(LabBooking(lab_id=lab.lab_id, booked_by=users[email].user_id, start_time=at(d, start), end_time=at(d, end), purpose=purpose))

    # Faculty status history for the last week, ending with a current status.
    now = datetime.now(timezone.utc)
    faculty = [u for u in users.values() if u.role in (Role.teacher, Role.lab_incharge, Role.admin)]
    for f in faculty:
        for back in range(6, 0, -1):
            day = now - timedelta(days=back)
            if day.weekday() == 6:
                continue
            state = FacultyState.on_leave if rng.random() < 0.1 else FacultyState.available
            db.add(FacultyStatus(faculty_id=f.user_id, status=state, updated_at=day.replace(hour=3, minute=30)))
            if state == FacultyState.available and rng.random() < 0.6:
                db.add(FacultyStatus(faculty_id=f.user_id, status=FacultyState.in_class, note="Lecture", updated_at=day.replace(hour=5)))
    current = {
        "hod@dept.edu": (FacultyState.available, "In HOD office till 4 pm"),
        "arjun@dept.edu": (FacultyState.in_class, "CS501 - Room 204"),
        "lakshmi@dept.edu": (FacultyState.available, "Staff room 2"),
        "rahul@dept.edu": (FacultyState.on_leave, "Back on Monday"),
        "labincharge@dept.edu": (FacultyState.available, "Programming Lab 1"),
    }
    for email, (state, note) in current.items():
        db.add(FacultyStatus(faculty_id=users[email].user_id, status=state, note=note, updated_at=now - timedelta(minutes=20)))

    # Notices
    posters = [admin, users["arjun@dept.edu"], users["priya@dept.edu"]]
    for i, (kind, title, company, due, link, desc) in enumerate(NOTICES):
        db.add(Notice(type=kind, title=title, company=company, deadline=today + timedelta(days=due), link=link,
                      description=desc, posted_by=posters[i % len(posters)].user_id,
                      posted_on=now - timedelta(days=len(NOTICES) - i)))


def _id_card_png(seed: int) -> bytes:
    """A plain placeholder ID-card picture (header band, photo box, text lines) without any image library."""
    w, h = 340, 214
    rng = random.Random(seed)
    band = (40 + rng.randint(0, 30), 80 + rng.randint(0, 40), 180 + rng.randint(0, 40))
    rows = []
    for y in range(h):
        row = bytearray([0])
        for x in range(w):
            if y < 46:
                px = band
            elif 64 <= y < 184 and 18 <= x < 108:
                px = (205, 210, 220)
            elif 112 <= x < 310 and any(70 + 26 * i <= y < 80 + 26 * i for i in range(4)) and x < 310 - 30 * (y % 3):
                px = (120, 128, 140)
            else:
                px = (248, 249, 252)
            row += bytes(px)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _seed_chat(db, users):
    from .routers.chat import UPLOAD_DIR

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    admin = users["hod@dept.edu"]
    now = datetime.now(timezone.utc)
    regs = {
        "kavin@dept.edu": (RegistrationStatus.approved, None),
        "priya@dept.edu": (RegistrationStatus.approved, None),
        "farhan@dept.edu": (RegistrationStatus.approved, None),
        "arjun@dept.edu": (RegistrationStatus.approved, None),
        "aditya@dept.edu": (RegistrationStatus.pending, None),
        "divya@dept.edu": (RegistrationStatus.rejected, "Photo is blurry, roll number not readable"),
    }
    for i, (email, (status, note)) in enumerate(regs.items()):
        u = users[email]
        name = f"{uuid.uuid4().hex}.png"
        (UPLOAD_DIR / name).write_bytes(_id_card_png(i))
        reviewed = status != RegistrationStatus.pending
        db.add(IdCardRegistration(
            user_id=u.user_id, id_card_image_ref=name, id_number=u.roll_no or f"STAFF-{u.user_id:03d}", status=status,
            submitted_on=now - timedelta(days=2, hours=i), review_note=note,
            reviewed_by=admin.user_id if reviewed else None, reviewed_on=now - timedelta(days=1) if reviewed else None,
        ))
    for minutes, email, text, flagged_by in [
        (180, "arjun@dept.edu", "Reminder: CAT-2 for DBMS is on Monday, syllabus is units 3 and 4.", None),
        (150, "kavin@dept.edu", "Sir, will normalisation questions be included?", None),
        (148, "arjun@dept.edu", "Yes, up to BCNF.", None),
        (95, "priya@dept.edu", "Anyone forming a team for the Zoho internship? Need one ML person.", None),
        (90, "kavin@dept.edu", "I'm in! DM me after class.", None),
        (40, "farhan@dept.edu", "Selling last year's CAT answer scripts, 200 each", "priya@dept.edu"),
        (12, "hod@dept.edu", "Please keep this space academic. Reported messages are reviewed by the department.", None),
    ]:
        db.add(ChatMessage(sender_id=users[email].user_id, message_text=text, sent_at=now - timedelta(minutes=minutes),
                           reported=flagged_by is not None, reported_by=users[flagged_by].user_id if flagged_by else None))
    for email, kind, msg, link, mins in [
        ("kavin@dept.edu", "marks_confirmed", "CS501 CAT-2 marks updated: 39/50", "/marks", 300),
        ("kavin@dept.edu", "new_notice", "New internship: Web Development Intern (remote) at Local startup via alumni cell", "/notices", 200),
        ("kavin@dept.edu", "status_change", "Your ID card was approved. You can now unlock campus chat.", "/chat", 1440),
        ("hod@dept.edu", "id_submitted", "Aditya N submitted an ID card for chat access", "/admin/verification", 2880),
        ("hod@dept.edu", "chat_report", "Priya R reported a chat message from Farhan A", "/admin/verification", 38),
        ("labincharge@dept.edu", "booking_approved", "Prof. Rahul Menon booked Programming Lab 2 tomorrow 13:00-15:00: Extra ML session", "/labs", 60),
    ]:
        db.add(Notification(user_id=users[email].user_id, type=kind, message=msg, link=link, created_at=now - timedelta(minutes=mins)))


def seed(reset: bool = False):
    if reset:
        Base.metadata.drop_all(bind=engine)
        from .routers.chat import UPLOAD_DIR

        for f in UPLOAD_DIR.glob("*") if UPLOAD_DIR.exists() else []:
            f.unlink()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.scalar(select(User).limit(1)):
            print("Database already has data; use --reset to start over.")
            return
        pw = hash_password(DEMO_PASSWORD)
        users = {}
        for name, email, role, roll in USERS:
            users[email] = User(name=name, email=email, password_hash=pw, role=role, roll_no=roll)
            db.add(users[email])
        subjects = {}
        for code, name, sem in SUBJECTS:
            subjects[code] = Subject(subject_code=code, subject_name=name, semester=sem)
            db.add(subjects[code])
        db.flush()
        admin = users["hod@dept.edu"]
        for email, codes in CREDENTIALS.items():
            for code in codes:
                db.add(SubjectCredential(user_id=users[email].user_id, subject_id=subjects[code].subject_id, granted_by=admin.user_id))
        _seed_modules(db, users, subjects)
        _seed_chat(db, users)
        db.commit()
        print(f"Seeded {len(USERS)} users, {len(SUBJECTS)} subjects, marks, {len(LABS)} labs, faculty status, notices, ID cards and chat. "
              f"Password for every demo account: {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
