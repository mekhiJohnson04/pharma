from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Case, CaseEventLog

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/latest")
def latest(db:Session = Depends(get_db)):
    case = db.query(Case).order_by(Case.received_at.desc()).first()
    if not case:
        return {"case": None, "events": []}
    
    events = (
        db.query(CaseEventLog).filter(CaseEventLog.case_id == case.id).order_by(CaseEventLog.occurred_at.asc()).all()
    )

    return {
        "case": {
            "id": str(case.id),
            "received_at": case.received_at,
            "initial_awareness_at": case.initial_awareness_at,
            "status": case.status.value if hasattr(case.status, "value") else str(case.status),
        },
        "events": [
            {
                "id": str(e.id),
                "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                "occurred_at": e.occurred_at,
                "actor_type": e.actor_type.value if hasattr(e.actor_type, "value") else str(e.actor_type),
                "actor_id": e.actor_id,
                "reason": e.reason,
                "payload": e.payload,
            }
            for e in events
        ],
    }