from fastapi import Depends
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Case, CaseEventLog, ActorType, EventType
from app.services.case_events import append_event