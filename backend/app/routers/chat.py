"""Identity-verified campus chat (Section 4.5).

Gate 1: the user registers their college ID card and an admin approves it.
Gate 2: the user unlocks chat on their own device with WebAuthn (fingerprint, Face ID, Touch ID,
        Windows Hello or the device PIN). Only a public key is stored; no biometric data reaches the server.
Once unlocked, access stays open for a session window (CHAT_SESSION_MINUTES) instead of a per-message check.
"""
import json
import os
import time
import uuid
from collections import deque
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, WebSocket,
                     WebSocketDisconnect)
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from webauthn import (generate_authentication_options, generate_registration_options, options_to_json,
                      verify_authentication_response, verify_registration_response)
from webauthn.helpers import base64url_to_bytes
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement, UserVerificationRequirement)

from ..database import SessionLocal, get_db
from ..models import (BiometricCredential, ChatMessage, ChatSession, IdCardRegistration, RegistrationStatus, Role,
                      User, utcnow)
from ..security import ALGORITHM, SECRET_KEY, audit, get_current_user, notify, require_roles, verify_password

router = APIRouter(prefix="/api/chat", tags=["chat"])
admin_only = require_roles(Role.admin)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", Path(__file__).resolve().parents[2] / "uploads"))
SESSION_MINUTES = int(os.getenv("CHAT_SESSION_MINUTES", "120"))
# Lets devices with no fingerprint/face/PIN authenticator still demo the flow. Set to 0 to require WebAuthn.
PASSWORD_FALLBACK = os.getenv("CHAT_PASSWORD_FALLBACK", "1") == "1"
ALLOWED_ORIGINS = os.getenv(
    "WEBAUTHN_ORIGINS", "http://localhost:8000,http://localhost:5173"
).split(",")
RP_NAME = "Department Smart Portal"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
MAX_MESSAGE = 1000

# One pending WebAuthn challenge per user and purpose, valid for 2 minutes (single server process).
_challenges: dict[tuple[int, str], tuple[bytes, float]] = {}


# ---- helpers -------------------------------------------------------------------

def latest_registration(db: Session, user_id: int) -> IdCardRegistration | None:
    return db.scalar(select(IdCardRegistration).where(IdCardRegistration.user_id == user_id)
                     .order_by(IdCardRegistration.registration_id.desc()).limit(1))


def id_verified(db: Session, user: User) -> bool:
    if user.role == Role.admin:
        return True  # admins are the ones who approve ID cards
    reg = latest_registration(db, user.user_id)
    return reg is not None and reg.status == RegistrationStatus.approved


def active_session(db: Session, user_id: int) -> ChatSession | None:
    return db.scalar(select(ChatSession).where(ChatSession.user_id == user_id, ChatSession.expires_on > utcnow())
                     .order_by(ChatSession.session_id.desc()).limit(1))


def require_chat_session(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
    if active_session(db, user.user_id) is None:
        raise HTTPException(status_code=403, detail="Unlock chat first")
    return user


def rp_for(request: Request) -> tuple[str, str]:
    origin = request.headers.get("origin") or f"{request.url.scheme}://{request.url.netloc}"
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=400, detail=(
            f"Fingerprint unlock works on {ALLOWED_ORIGINS[0]} (open the portal at that address, not an IP address)"))
    return urlparse(origin).hostname, origin


def put_challenge(user_id: int, purpose: str, challenge: bytes):
    _challenges[(user_id, purpose)] = (challenge, time.time() + 120)


def take_challenge(user_id: int, purpose: str) -> bytes:
    challenge, expires = _challenges.pop((user_id, purpose), (None, 0))
    if challenge is None or expires < time.time():
        raise HTTPException(status_code=400, detail="That request expired. Try again.")
    return challenge


def start_session(db: Session, user: User, method: str, credential_id: int | None = None) -> ChatSession:
    s = ChatSession(user_id=user.user_id, credential_id=credential_id, method=method,
                    expires_on=utcnow() + timedelta(minutes=SESSION_MINUTES))
    db.add(s)
    audit(db, user, "unlock", "chat_session", None, method)
    db.commit()
    return s


def message_out(m: ChatMessage) -> dict:
    return {
        "message_id": m.message_id, "sender_id": m.sender_id, "sender_name": m.sender.name,
        "sender_role": m.sender.role, "text": m.message_text, "sent_at": m.sent_at.isoformat(),
        "reported": m.reported,
    }


# ---- status --------------------------------------------------------------------

@router.get("/status")
def chat_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reg = latest_registration(db, user.user_id)
    creds = db.scalars(select(BiometricCredential).where(BiometricCredential.user_id == user.user_id)).all()
    session = active_session(db, user.user_id)
    return {
        "id_required": user.role != Role.admin,
        "id_status": reg.status if reg else None,
        "id_review_note": reg.review_note if reg else None,
        "verified": id_verified(db, user),
        "devices": [{"credential_id": c.credential_id, "device_label": c.device_label, "registered_on": c.registered_on} for c in creds],
        "session_expires": session.expires_on if session else None,
        "password_fallback": PASSWORD_FALLBACK,
        "session_minutes": SESSION_MINUTES,
    }


# ---- Gate 1: ID card registration ----------------------------------------------

@router.post("/id-card", status_code=201)
async def submit_id_card(id_number: str = Form(..., min_length=3, max_length=60), image: UploadFile = File(...),
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role == Role.admin:
        raise HTTPException(status_code=400, detail="Admins do not need ID verification")
    current = latest_registration(db, user.user_id)
    if current and current.status == RegistrationStatus.approved:
        raise HTTPException(status_code=409, detail="Your ID card is already approved")
    ext = IMAGE_TYPES.get(image.content_type or "")
    if ext is None:
        raise HTTPException(status_code=422, detail="Upload a PNG, JPEG or WebP photo of your ID card")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=422, detail="Image must be under 5 MB")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    reg = IdCardRegistration(user_id=user.user_id, id_card_image_ref=name, id_number=id_number.strip())
    db.add(reg)
    db.flush()
    audit(db, user, "submit", "id_card_registration", reg.registration_id, reg.id_number)
    admins = db.scalars(select(User.user_id).where(User.role == Role.admin, User.is_active))
    notify(db, admins, "id_submitted", f"{user.name} submitted an ID card for chat access", "/admin/verification", reg.registration_id)
    db.commit()
    return {"registration_id": reg.registration_id, "status": reg.status}


@router.get("/id-cards")
def list_id_cards(status: RegistrationStatus | None = None, db: Session = Depends(get_db),
                  _: User = Depends(admin_only)):
    q = select(IdCardRegistration).order_by(IdCardRegistration.registration_id.desc())
    if status:
        q = q.where(IdCardRegistration.status == status)
    return [{
        "registration_id": r.registration_id, "user_id": r.user_id, "name": r.user.name, "email": r.user.email,
        "roll_no": r.user.roll_no, "role": r.user.role, "id_number": r.id_number, "status": r.status,
        "submitted_on": r.submitted_on, "reviewed_on": r.reviewed_on, "review_note": r.review_note,
    } for r in db.scalars(q)]


@router.get("/id-cards/{registration_id}/image")
def id_card_image(registration_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reg = db.get(IdCardRegistration, registration_id)
    if reg is None or (user.role != Role.admin and reg.user_id != user.user_id):
        raise HTTPException(status_code=404, detail="Not found")
    path = UPLOAD_DIR / reg.id_card_image_ref
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image missing")
    return FileResponse(path)


class ReviewIn(BaseModel):
    approve: bool
    note: str | None = Field(default=None, max_length=200)


@router.post("/id-cards/{registration_id}/review")
def review_id_card(registration_id: int, body: ReviewIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    reg = db.get(IdCardRegistration, registration_id)
    if reg is None:
        raise HTTPException(status_code=404, detail="Not found")
    if reg.status != RegistrationStatus.pending:
        raise HTTPException(status_code=409, detail="Already reviewed")
    if not body.approve and not (body.note or "").strip():
        raise HTTPException(status_code=422, detail="Give a reason when rejecting")
    reg.status = RegistrationStatus.approved if body.approve else RegistrationStatus.rejected
    reg.reviewed_by, reg.reviewed_on, reg.review_note = admin.user_id, utcnow(), (body.note or "").strip() or None
    audit(db, admin, reg.status.value, "id_card_registration", reg.registration_id, reg.user.email)
    msg = ("Your ID card was approved. You can now unlock campus chat." if body.approve
           else f"Your ID card was not approved: {reg.review_note}. Please upload it again.")
    notify(db, [reg.user_id], "status_change", msg, "/chat", reg.registration_id)
    db.commit()
    return {"registration_id": reg.registration_id, "status": reg.status}


# ---- Gate 2: device unlock (WebAuthn) ------------------------------------------

class DeviceIn(BaseModel):
    credential: dict
    device_label: str = Field(default="My device", max_length=80)


class AssertionIn(BaseModel):
    credential: dict


@router.post("/webauthn/register/options")
def register_options(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not id_verified(db, user):
        raise HTTPException(status_code=403, detail="Your ID card must be approved first")
    rp_id, _ = rp_for(request)
    existing = db.scalars(select(BiometricCredential).where(BiometricCredential.user_id == user.user_id)).all()
    opts = generate_registration_options(
        rp_id=rp_id, rp_name=RP_NAME, user_name=user.email, user_display_name=user.name,
        user_id=str(user.user_id).encode(),
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.DISCOURAGED, user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=c.webauthn_credential_id) for c in existing],
    )
    put_challenge(user.user_id, "register", opts.challenge)
    return json.loads(options_to_json(opts))


@router.post("/webauthn/register/verify", status_code=201)
def register_verify(body: DeviceIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rp_id, origin = rp_for(request)
    try:
        v = verify_registration_response(credential=body.credential, expected_challenge=take_challenge(user.user_id, "register"),
                                         expected_rp_id=rp_id, expected_origin=origin, require_user_verification=True)
    except HTTPException:
        raise
    except Exception as exc:  # library raises several specific error types
        raise HTTPException(status_code=400, detail=f"Device registration failed: {exc}")
    cred = BiometricCredential(user_id=user.user_id, device_label=body.device_label.strip() or "My device",
                               webauthn_credential_id=v.credential_id, webauthn_public_key=v.credential_public_key,
                               sign_count=v.sign_count)
    db.add(cred)
    db.flush()
    audit(db, user, "register", "biometric_credential", cred.credential_id, cred.device_label)
    db.commit()
    s = start_session(db, user, "biometric", cred.credential_id)
    return {"credential_id": cred.credential_id, "session_expires": s.expires_on}


@router.post("/webauthn/unlock/options")
def unlock_options(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not id_verified(db, user):
        raise HTTPException(status_code=403, detail="Your ID card must be approved first")
    rp_id, _ = rp_for(request)
    creds = db.scalars(select(BiometricCredential).where(BiometricCredential.user_id == user.user_id)).all()
    if not creds:
        raise HTTPException(status_code=404, detail="Register this device first")
    opts = generate_authentication_options(
        rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[PublicKeyCredentialDescriptor(id=c.webauthn_credential_id) for c in creds],
    )
    put_challenge(user.user_id, "unlock", opts.challenge)
    return json.loads(options_to_json(opts))


@router.post("/webauthn/unlock/verify")
def unlock_verify(body: AssertionIn, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rp_id, origin = rp_for(request)
    challenge = take_challenge(user.user_id, "unlock")
    try:
        raw_id = base64url_to_bytes(body.credential.get("rawId") or body.credential.get("id", ""))
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed credential")
    cred = db.scalar(select(BiometricCredential).where(BiometricCredential.webauthn_credential_id == raw_id,
                                                       BiometricCredential.user_id == user.user_id))
    if cred is None:
        raise HTTPException(status_code=400, detail="This device is not registered to your account")
    try:
        v = verify_authentication_response(credential=body.credential, expected_challenge=challenge, expected_rp_id=rp_id,
                                           expected_origin=origin, credential_public_key=cred.webauthn_public_key,
                                           credential_current_sign_count=cred.sign_count, require_user_verification=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Unlock failed: {exc}")
    cred.sign_count = v.new_sign_count
    s = start_session(db, user, "biometric", cred.credential_id)
    return {"session_expires": s.expires_on}


class PasswordUnlockIn(BaseModel):
    password: str


@router.post("/unlock/password")
def unlock_with_password(body: PasswordUnlockIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not PASSWORD_FALLBACK:
        raise HTTPException(status_code=403, detail="Password unlock is turned off; use your device's fingerprint or PIN")
    if not id_verified(db, user):
        raise HTTPException(status_code=403, detail="Your ID card must be approved first")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail="Wrong password")
    s = start_session(db, user, "password")
    return {"session_expires": s.expires_on}


@router.delete("/webauthn/credentials/{credential_id}", status_code=204)
def remove_device(credential_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cred = db.get(BiometricCredential, credential_id)
    if cred is None or cred.user_id != user.user_id:
        raise HTTPException(status_code=404, detail="Not found")
    audit(db, user, "remove", "biometric_credential", cred.credential_id, cred.device_label)
    db.delete(cred)
    db.commit()


@router.post("/lock", status_code=204)
def lock(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    for s in db.scalars(select(ChatSession).where(ChatSession.user_id == user.user_id, ChatSession.expires_on > utcnow())):
        s.expires_on = utcnow()
    db.commit()


# ---- Messages ------------------------------------------------------------------

class Hub:
    """Connected chat sockets; every message is pushed to everyone in real time."""

    def __init__(self):
        self.sockets: dict[WebSocket, int] = {}

    async def broadcast(self, payload: dict):
        dead = []
        for ws in list(self.sockets):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.sockets.pop(ws, None)

    def online(self) -> int:
        return len(set(self.sockets.values()))


hub = Hub()


@router.get("/messages")
def history(before_id: int | None = None, db: Session = Depends(get_db), _: User = Depends(require_chat_session)):
    q = select(ChatMessage).where(ChatMessage.hidden.is_(False)).order_by(ChatMessage.message_id.desc()).limit(50)
    if before_id:
        q = q.where(ChatMessage.message_id < before_id)
    return [message_out(m) for m in reversed(db.scalars(q).all())]


@router.post("/messages/{message_id}/report", status_code=204)
def report_message(message_id: int, db: Session = Depends(get_db), user: User = Depends(require_chat_session)):
    m = db.get(ChatMessage, message_id)
    if m is None or m.hidden:
        raise HTTPException(status_code=404, detail="Message not found")
    if m.sender_id == user.user_id:
        raise HTTPException(status_code=400, detail="You cannot report your own message")
    if not m.reported:
        m.reported, m.reported_by = True, user.user_id
        audit(db, user, "report", "chat_message", m.message_id, m.message_text[:80])
        admins = db.scalars(select(User.user_id).where(User.role == Role.admin, User.is_active))
        notify(db, admins, "chat_report", f"{user.name} reported a chat message from {m.sender.name}", "/admin/verification", m.message_id)
        db.commit()


@router.get("/reported")
def reported(db: Session = Depends(get_db), _: User = Depends(admin_only)):
    rows = db.scalars(select(ChatMessage).where(ChatMessage.reported.is_(True), ChatMessage.hidden.is_(False))
                      .order_by(ChatMessage.message_id.desc()))
    return [message_out(m) for m in rows]


class ModerateIn(BaseModel):
    hide: bool


@router.post("/messages/{message_id}/moderate")
async def moderate(message_id: int, body: ModerateIn, db: Session = Depends(get_db), admin: User = Depends(admin_only)):
    m = db.get(ChatMessage, message_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if body.hide:
        m.hidden = True
        audit(db, admin, "hide", "chat_message", m.message_id, m.message_text[:80])
    else:
        m.reported = False  # report dismissed
        audit(db, admin, "dismiss_report", "chat_message", m.message_id)
    db.commit()
    if body.hide:
        await hub.broadcast({"type": "hidden", "message_id": message_id})
    return {"message_id": message_id, "hidden": m.hidden}


@router.websocket("/ws")
async def chat_socket(ws: WebSocket, token: str):
    # Browsers cannot set headers on WebSockets, so the JWT comes as a query parameter.
    try:
        user_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])["sub"])
    except (JWTError, KeyError, ValueError):
        await ws.close(code=4401)
        return
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if user is None or not user.is_active or active_session(db, user_id) is None:
            await ws.close(code=4403)
            return
    await ws.accept()
    hub.sockets[ws] = user_id
    await hub.broadcast({"type": "presence", "online": hub.online()})
    recent: deque[float] = deque(maxlen=5)
    try:
        while True:
            data = await ws.receive_json()
            text = str(data.get("text", "")).strip()
            if not text:
                continue
            if len(text) > MAX_MESSAGE:
                await ws.send_json({"type": "error", "detail": f"Messages are limited to {MAX_MESSAGE} characters"})
                continue
            now = time.monotonic()
            if len(recent) == recent.maxlen and now - recent[0] < 5:
                await ws.send_json({"type": "error", "detail": "Slow down a little"})
                continue
            recent.append(now)
            with SessionLocal() as db:
                if active_session(db, user_id) is None:
                    await ws.send_json({"type": "expired"})
                    await ws.close(code=4403)
                    return
                m = ChatMessage(sender_id=user_id, message_text=text)
                db.add(m)
                db.commit()
                db.refresh(m)
                payload = {"type": "message", **message_out(m)}
            await hub.broadcast(payload)
    except WebSocketDisconnect:
        pass
    finally:
        hub.sockets.pop(ws, None)
        await hub.broadcast({"type": "presence", "online": hub.online()})

