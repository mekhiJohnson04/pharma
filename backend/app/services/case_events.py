from sqlalchemy.orm import Session # this function writes inside a DB transaction
from datetime import datetime, timezone
from typing import Dict, Any, Optional # event payload is JSON-like + actor_id/reason may be optional
from app.db.models import Case, CaseEventLog, ActorType, CaseStatus, EventType # CaseEventLog is the table we insert into ; EventType, ActorType ensures we use standard enums (no random strings)
import json
import uuid
# All case mutations go through this service
# Forces append-only disclipline
# Centralizes audit behavior

def utc_now():
    return datetime.now(timezone.utc)

def build_case_created_payload(
            source: str, 
            intake_channel: str | None = None, 
            external_ref: str | None = None,
    ) -> dict: # Create a small, versioned JSON payload describing a Case creation event
        payload = {
            "schema_version": "case.created.v1",
            "source": source
        }
        if intake_channel:
            payload["intake_channel"] = intake_channel

        if external_ref:
            payload["external_ref"] = external_ref

        return payload

def append_event(
          db: Session, 
          case_id: uuid.UUID, 
          event_type: EventType, 
          payload: Optional[dict[str, Any]] = None,
          actor_type: ActorType = ActorType.SYSTEM,
          actor_id: Optional[str] = None,
          reason: Optional[str] = None,
          occurred_at: Optional[datetime] = None,
) -> CaseEventLog: 
    # Write one immutable event row to CaseEventLog for a specific case
    
    if payload is None:
        payload = {}

    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
         
    # Optional strictness: JSON requires string keys
    if any(not isinstance(k, str) for k in payload.keys()):
        raise ValueError("payload keys must be strings")
         
    # 2) validate JSON-serializable
    try:
        json.dumps(payload)
    except TypeError as e:
        raise ValueError(f"payload is not JSON-serializable: {e}")
    
    if occurred_at is None:
        occurred_at = utc_now()

    event = CaseEventLog(
        case_id=case_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=reason,
        payload=payload,
        
    )

    db.add(event)
    db.flush() # assigns event.id without committing
    return event

def create_case_from_intake(
        db: Session,
        intake_payload: Dict[str, Any],
        source: str,
        intake_channel: Optional[str] = None,
        external_ref: Optional[str] = None,
        actor_type: ActorType = ActorType.API,
        actor_id: Optional[str] = None,
        received_at: Optional[datetime] = None,
) -> Case:
    
    # Create a new Case and log the evidence/events that prove how it was created.

    if intake_payload is None or not isinstance(intake_payload, dict):
        raise ValueError("intake payload must be a dict")
    
    if received_at is None:
        received_at = utc_now() # reciept time is a system fact (important for clock reasoning later)

    case = Case(
        id=uuid.uuid4(),
        received_at=received_at,
        status=CaseStatus.OPEN,
        initial_awareness_at=None,
    )
    db.add(case)
    db.flush() # ensure case.id is available

    created_payload = build_case_created_payload(source=source, intake_channel=intake_channel, external_ref=external_ref,)
    append_event(
        db=db,
        case_id=case.id,
        event_type=EventType.CASE_CREATED, # adjust name if your enum differs
        payload=created_payload,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    # INTAKE_RECEIVED event (raw evidence)
    intake_event_payload: Dict[str, Any] = {
        "schema_version": "intake.received.v1",
        "source": source,
        "raw": intake_payload,
    }
    if external_ref:
        intake_event_payload["external_ref"] = external_ref

    append_event(
        db=db,
        case_id=case.id,
        event_type=EventType.INTAKE_RECEIVED, # adjust name if your enum differs
        payload=intake_event_payload,
        actor_type=actor_type,
        actor_id=actor_id,
    )

    return case


def redact_intake_payload():
    # Whitelists fields /
    pass