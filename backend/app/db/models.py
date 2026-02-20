from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid
import enum
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
    Boolean,
    Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class CaseStatus(str, enum.Enum): # current status snapshot
    OPEN = "open"
    FOLLOW_UP = "follow_up"
    READY = "ready"
    SUBMITTED = "submitted"
    CLOSED = "closed"

class EventType(str, enum.Enum): # what happened
    CASE_CREATED = "case.created"
    INTAKE_RECEIVED = "intake.received"
    FIELD_SET = "field.set"
    FIELD_CLEARED = "field.cleared"
    NOTE_ADDED = "note.added"
    AWARENESS_SET = "case.awareness_set"
    AWARENESS_AMENDED = "case.awareness_amended"

class ActorType(str, enum.Enum): # who caused it
    USER = "user"
    SYSTEM = "system"
    API = "api"

class ReporterType(str, enum.Enum): # qualification ontology
    CONSUMER = "consumer" # Non-HCP
    HCP = "HCP" # Physician, Pharmacist, Nurse, Dentist, etc.

class SourceType(str, enum.Enum): # source ontology
    SPONTANEOUS = "spontaneous"
    LITERATURE = "literature"
    PARTNER = "partner"
    STUDY = "study"

class Case(Base): # the "current state" record
    __tablename__ = "cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # This should be set once and never overwritten; amendments happen via events.
    initial_awareness_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(Enum(CaseStatus), nullable=False, default=CaseStatus.OPEN)

    # convenient relationship to read event timeline
    events = relationship(
        "CaseEventLog",
        back_populates="case", 
        order_by="CaseEventLog.occurred_at.asc()",
        cascade="all, delete-orphan",
    )

class CaseEventLog(Base): # the "history" record
    __tablename__ = "case_event_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id = Column(UUID(as_uuid=True), ForeignKey("cases.id"), nullable=False, index=True)

    event_type = Column(Enum(EventType), nullable=False)
    occurred_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    actor_type = Column(Enum(ActorType), nullable=False, default=ActorType.SYSTEM)
    actor_id = Column(String, nullable=True) # user id, api key id, service id, etc.

    # JSON payload should always include what changed and where it came from
    payload = Column(JSON, nullable=False, default=dict)

    # IN regulated mode, certain event types should require a reason
    reason = Column(Text, nullable=True)

    case = relationship("Case", back_populates="events")

class Patient(Base): # Key Constraint: Patient must be identifiable not necessarily by name but distinguishable enough in the report.
    __tablename__ = "patient"

    patient_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4) # internal no need for name, PV allows limited data
    sex = Column(String, nullable=True) # male | female
    age = Column(int, nullable=False)
    weight = Optional(Column(float, nullable=True))

class Reporter(Base):
    __tablename__ = "reporter"
