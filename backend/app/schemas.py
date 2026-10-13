from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import Role


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    name: str
    email: str
    role: Role
    roll_no: str | None
    department: str
    is_active: bool


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6)
    role: Role
    roll_no: str | None = None
    department: str = "Computer Science"


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    roll_no: str | None = None
    department: str | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    subject_code: str
    subject_name: str
    semester: int
    department: str


class SubjectCreate(BaseModel):
    subject_code: str
    subject_name: str
    semester: int = Field(ge=1, le=10)
    department: str = "Computer Science"


class CredentialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    credential_id: int
    user_id: int
    subject_id: int
    granted_by: int
    granted_on: datetime
    subject: SubjectOut


class CredentialCreate(BaseModel):
    user_id: int
    subject_id: int


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    log_id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: int | None
    details: str | None
    created_at: datetime
