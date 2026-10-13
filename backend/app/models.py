"""Database tables. Mirrors Section 7 of the capstone report.

Users, subjects, credentials and the audit log, plus the marks, lab, faculty-status
notice-board, chat and notification tables.
"""
import enum
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores UTC and always hands back timezone-aware values (SQLite drops the zone),
    so the browser shows times in the viewer's local zone."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(self, value, dialect):
        return value.replace(tzinfo=timezone.utc) if value is not None else None


class Role(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    lab_incharge = "lab_incharge"
    admin = "admin"  # Department admin / HOD


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role))
    roll_no: Mapped[str | None] = mapped_column(String(40), unique=True, nullable=True)
    department: Mapped[str] = mapped_column(String(120), default="Computer Science")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    credentials: Mapped[list["SubjectCredential"]] = relationship(
        back_populates="user", foreign_keys="SubjectCredential.user_id"
    )


class Subject(Base):
    __tablename__ = "subjects"

    subject_id: Mapped[int] = mapped_column(primary_key=True)
    subject_code: Mapped[str] = mapped_column(String(20), unique=True)
    subject_name: Mapped[str] = mapped_column(String(120))
    semester: Mapped[int]
    department: Mapped[str] = mapped_column(String(120), default="Computer Science")


class SubjectCredential(Base):
    """Grants a teacher the right to enter/confirm marks for one subject."""

    __tablename__ = "subject_credentials"
    __table_args__ = (UniqueConstraint("user_id", "subject_id"),)

    credential_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    granted_on: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="credentials", foreign_keys=[user_id])
    subject: Mapped[Subject] = relationship()


class AuditLog(Base):
    """Who changed what, and when (Section 8)."""

    __tablename__ = "audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


# ---- Marks (Section 7.2) ------------------------------------------------------
# The prototype enters marks manually per question; OCR scan tables come later.

class MarkComponent(Base):
    """An assessment within a subject, e.g. CAT-1 (5 questions x 10) worth 15% of the internal."""

    __tablename__ = "mark_components"
    __table_args__ = (UniqueConstraint("subject_id", "name"),)

    component_id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.subject_id"))
    name: Mapped[str] = mapped_column(String(60))
    question_max: Mapped[list[float]] = mapped_column(JSON)  # max marks per question, e.g. [10, 10, 15]
    weightage: Mapped[float]  # contribution to the internal total
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    subject: Mapped[Subject] = relationship()

    @property
    def max_marks(self) -> float:
        return float(sum(self.question_max))


class Mark(Base):
    __tablename__ = "marks"
    __table_args__ = (UniqueConstraint("student_id", "component_id"),)

    mark_id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    component_id: Mapped[int] = mapped_column(ForeignKey("mark_components.component_id"), index=True)
    question_marks: Mapped[list[float | None]] = mapped_column(JSON)  # None = not attempted
    marks_obtained: Mapped[float]
    absent: Mapped[bool] = mapped_column(default=False)
    entered_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    entered_on: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    component: Mapped[MarkComponent] = relationship()


# ---- Labs (Section 7.3) -------------------------------------------------------

class LabStatus(str, enum.Enum):
    free = "free"
    occupied = "occupied"
    maintenance = "maintenance"


class Lab(Base):
    __tablename__ = "labs"

    lab_id: Mapped[int] = mapped_column(primary_key=True)
    lab_name: Mapped[str] = mapped_column(String(80), unique=True)
    capacity: Mapped[int] = mapped_column(default=30)
    incharge_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    current_status: Mapped[LabStatus] = mapped_column(Enum(LabStatus), default=LabStatus.free)
    status_updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    incharge: Mapped[User | None] = relationship()


class LabBooking(Base):
    """Times are department-local wall-clock times (naive datetimes)."""

    __tablename__ = "lab_bookings"

    booking_id: Mapped[int] = mapped_column(primary_key=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.lab_id"), index=True)
    booked_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    purpose: Mapped[str] = mapped_column(String(200))
    cancelled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)  # enforces FCFS

    lab: Mapped[Lab] = relationship()
    booker: Mapped[User] = relationship()


# ---- Faculty availability (Section 7.4) ---------------------------------------

class FacultyState(str, enum.Enum):
    available = "Available"
    in_class = "In Class"
    on_leave = "On Leave"
    unavailable = "Unavailable"


class FacultyStatus(Base):
    """One row per status change; the latest row per faculty is their current status.
    Keeping every row gives the attendance-style history the report asks for."""

    __tablename__ = "faculty_status"

    status_id: Mapped[int] = mapped_column(primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    status: Mapped[FacultyState] = mapped_column(Enum(FacultyState, values_callable=lambda e: [m.value for m in e]))
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    faculty: Mapped[User] = relationship()


# ---- Notice board (Section 7.5) -----------------------------------------------

class NoticeType(str, enum.Enum):
    job = "job"
    internship = "internship"


class Notice(Base):
    __tablename__ = "notices"

    notice_id: Mapped[int] = mapped_column(primary_key=True)
    posted_by: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    title: Mapped[str] = mapped_column(String(160))
    company: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[NoticeType] = mapped_column(Enum(NoticeType))
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    link: Mapped[str | None] = mapped_column(String(300), nullable=True)
    posted_on: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    poster: Mapped[User] = relationship()


# ---- Chat (Section 7.6) -------------------------------------------------------

class RegistrationStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class IdCardRegistration(Base):
    __tablename__ = "id_card_registrations"

    registration_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    id_card_image_ref: Mapped[str] = mapped_column(String(200))  # file name under UPLOAD_DIR
    id_number: Mapped[str] = mapped_column(String(60))
    status: Mapped[RegistrationStatus] = mapped_column(Enum(RegistrationStatus), default=RegistrationStatus.pending)
    submitted_on: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    reviewed_on: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    user: Mapped[User] = relationship(foreign_keys=[user_id])


class BiometricCredential(Base):
    """A WebAuthn public key for one device. The fingerprint/face match happens on the device;
    the server only ever sees this public key and a signature."""

    __tablename__ = "biometric_credentials"

    credential_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    device_label: Mapped[str] = mapped_column(String(80))
    webauthn_credential_id: Mapped[bytes] = mapped_column(unique=True)
    webauthn_public_key: Mapped[bytes]
    sign_count: Mapped[int] = mapped_column(default=0)
    registered_on: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChatSession(Base):
    """An unlocked chat window: access stays open until expires_on instead of re-checking every message."""

    __tablename__ = "chat_sessions"

    session_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    credential_id: Mapped[int | None] = mapped_column(ForeignKey("biometric_credentials.credential_id"), nullable=True)
    method: Mapped[str] = mapped_column(String(20))  # "biometric" or "password"
    unlocked_on: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_on: Mapped[datetime] = mapped_column(UTCDateTime)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"))
    message_text: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    reported: Mapped[bool] = mapped_column(default=False)
    reported_by: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    hidden: Mapped[bool] = mapped_column(default=False)  # removed by a moderator

    sender: Mapped[User] = relationship(foreign_keys=[sender_id])


# ---- Notifications (Section 7.7) ----------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), index=True)
    type: Mapped[str] = mapped_column(String(40))  # marks_confirmed, booking_*, new_notice, status_change, conflict, id_*, chat_report
    message: Mapped[str] = mapped_column(String(300))
    link: Mapped[str | None] = mapped_column(String(120), nullable=True)  # page to open in the portal
    related_id: Mapped[int | None] = mapped_column(nullable=True)
    is_read: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
