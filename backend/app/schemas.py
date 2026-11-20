from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.taxonomy import (
    AIRPORTS,
    CATEGORIES,
    FLIGHT_PHASES,
    OPERATORS,
    MeasurePriority,
    MeasureStatus,
    Role,
    Severity,
)


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------ auth / users
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: str
    designation: str | None
    base_station: str | None
    is_active: bool


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    role: Role
    designation: str | None = Field(default=None, max_length=80)
    base_station: str | None = None


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    designation: str | None = Field(default=None, max_length=80)
    base_station: str | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


class UserBrief(ORM):
    id: int
    full_name: str


# ------------------------------------------------------------------ incidents
class IncidentCreate(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=20, max_length=10000)
    category: str
    occurred_at: datetime
    airport_code: str
    flight_phase: str
    aircraft_registration: str | None = Field(default=None, max_length=10)
    aircraft_type: str | None = Field(default=None, max_length=20)
    operator_code: str | None = None
    flight_number: str | None = Field(default=None, max_length=10)

    @field_validator("category")
    @classmethod
    def _cat(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError("Unknown category")
        return v

    @field_validator("airport_code")
    @classmethod
    def _apt(cls, v: str) -> str:
        v = v.upper()
        if v not in AIRPORTS:
            raise ValueError("Unknown airport code")
        return v

    @field_validator("flight_phase")
    @classmethod
    def _phase(cls, v: str) -> str:
        if v not in FLIGHT_PHASES:
            raise ValueError("Unknown flight phase")
        return v

    @field_validator("operator_code")
    @classmethod
    def _op(cls, v: str | None) -> str | None:
        if v and v not in OPERATORS:
            raise ValueError("Unknown operator")
        return v or None

    @field_validator("occurred_at")
    @classmethod
    def _past(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        if v > datetime.now(v.tzinfo):
            raise ValueError("occurred_at cannot be in the future")
        return v


class AnalysisIn(BaseModel):
    severity: Severity
    analysis: str = Field(min_length=20, max_length=10000)


class CloseIn(BaseModel):
    closing_note: str | None = Field(default=None, max_length=2000)


class SummaryEdit(BaseModel):
    summary: str = Field(min_length=10, max_length=4000)


class MeasureCreate(BaseModel):
    description: str = Field(min_length=5, max_length=1000)
    priority: MeasurePriority


class MeasureUpdate(BaseModel):
    status: MeasureStatus | None = None
    reason: str | None = Field(default=None, max_length=1000)
    priority: MeasurePriority | None = None

    @model_validator(mode="after")
    def _reason_required(self) -> "MeasureUpdate":
        if self.status == MeasureStatus.NOT_APPLIED and not (self.reason and self.reason.strip()):
            raise ValueError("A reason is required when a measure is not applied")
        return self


class MeasureComplete(BaseModel):
    note: str = Field(min_length=5, max_length=1000, description="What was done, by whom, reference")


class MeasureOut(ORM):
    id: int
    description: str
    priority: str
    source: str
    status: str
    reason: str | None
    policy_reference: str | None
    marked_at: datetime | None
    icon: str
    completed_late: bool = False
    completion_note: str | None = None
    completed_at: datetime | None = None
    completed_by: str | None = None


class SummaryOut(ORM):
    id: int
    status: str
    summary: str | None
    citations: str | None
    model: str | None
    error: str | None
    created_at: datetime
    reviewed_at: datetime | None


class HistoryOut(ORM):
    from_status: str | None
    to_status: str
    note: str | None
    changed_at: datetime
    changed_by: UserBrief | None


class IncidentListItem(ORM):
    id: int
    reference: str
    title: str
    category: str
    occurred_at: datetime
    airport_code: str
    severity: str | None
    status: str
    colour: str
    reporter: UserBrief
    officer: UserBrief | None
    created_at: datetime


class IncidentOut(IncidentListItem):
    description: str
    flight_phase: str
    aircraft_registration: str | None
    aircraft_type: str | None
    operator_code: str | None
    flight_number: str | None
    analysis: str | None
    closing_note: str | None
    closed_at: datetime | None
    measures: list[MeasureOut]
    summary: SummaryOut | None
    history: list[HistoryOut]


class Page(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


class IncidentPage(Page):
    items: list[IncidentListItem]


# ------------------------------------------------------------------ admin
class MeasureCounts(BaseModel):
    total: int
    applied: int
    not_applied_must: int
    not_applied_should: int
    pending: int
    completed_late: int = 0


class AdminIncidentItem(BaseModel):
    id: int
    reference: str
    title: str
    category: str
    severity: str | None
    status: str
    colour: str
    occurred_at: datetime
    airport_code: str
    short_summary: str | None
    counts: MeasureCounts


class AdminIncidentPage(Page):
    items: list[AdminIncidentItem]
    colour_totals: dict[str, int]
    completed_late_total: int = 0


class AdminIncidentDetail(BaseModel):
    id: int
    reference: str
    title: str
    issue: str
    category: str
    severity: str | None
    status: str
    colour: str
    airport_code: str
    occurred_at: datetime
    short_summary: str | None
    summary_status: str | None
    suggested_measures: list[MeasureOut]
    applied_measures: list[MeasureOut]
    not_applied_measures: list[MeasureOut]
    pending_measures: list[MeasureOut]


# ------------------------------------------------------------------ policies
class PolicyIn(BaseModel):
    content: str = Field(min_length=50, description="SOP markdown with '## ' sections")


class PolicyOut(ORM):
    id: int
    code: str
    title: str
    category: str | None
    source: str | None
    chunk_count: int


class PolicySearchHit(BaseModel):
    key: str
    section_ref: str
    policy_code: str
    score: float
    content: str


ColourName = Literal["green", "yellow", "red", "grey"]
