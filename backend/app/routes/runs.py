# _____ uses survey.py (engine) + storage.py (persistence) to provide stateful run endpoints

from typing import Optional
from uuid import uuid4
import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# survey engine bits we REUSE (do not re-implement validation rules here)
from app.api.survey import (
    START_ID,                      # the first question id (e.g., "q1")
    SURVEY_DEFINITION,            # the full question graph (dict)
    show_question,                # formats a node into the frontend-friendly "next" payload
    build_meta,                   # meta block with version + timestamp
    _build_summary,               # builds a summary dict from answers_by_id
)

# process-wide, thread-safe in-memory store
from app.services.storage import InMemoryRunStore, SurveyRun
from app.core.config import SURVEY_VERSION

router = APIRouter()

# Immutable config/data references (read-only):
QMAP = SURVEY_DEFINITION["questions"]   # convenience alias to the question graph

# One store instance per process
STORE = InMemoryRunStore()
 

# ---------- helpers ----------

def _new_run_id() -> str:
    """
    Generate a URL-safe short id from 16 random bytes.
    Example: 'f2q4...-' (~22 chars).
    """
    return base64.urlsafe_b64encode(uuid4().bytes).rstrip(b"=").decode("ascii")


def _require_run(run_id: str) -> SurveyRun:
    """
    Fetch a run from the store or raise 404 if it doesn't exist.
    """
    run = STORE.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": {"code": "UNKNOWN_RUN", "message": f"Run '{run_id}' not found."},
                "meta": build_meta(),
            },
        )
    return run


def _require_active(run: SurveyRun) -> None:
    """
    Ensure the run is currently active. If not, raise a 409 (conflict).
    """
    if run.get("status") != "active":
        raise HTTPException(
            status_code=409,
            detail={
                "error": {"code": "STATUS_INACTIVE", "message": f"Run is {run.get('status')}."},
                "meta": build_meta(),
            },
        )


def _build_answer_log(run_id: str):
    """
    Based off of the run_id, any question that has already been answered will 
    be stored in local memory for now until database is set up.
    """
    run = STORE.get_run(run_id)
    _require_run(run_id)

    results = []

    ans_id = run["answers_by_id"]
    history = run["history"]

    for step in history:
        qid = step["question_id"]
        node = QMAP.get(qid)
        stored = run["answers_by_id"].get(qid)

        # build one stitched record per history item
        record = {
            "question_id": qid,
            "question_text": node["text"] if node else "MISSING",
            "type": node["type"] if node else None,
            "answer": stored or {"incomplete": True}
        }
        results.append(record)

        return results

    
        

def _cursor_to_node(cursor: Optional[str], active_section):
    """
    Convert a cursor id to a node dict, with guardrails.
    - If cursor is None -> no next question (likely finished).
    - If cursor not in qmap/section map -> definition error (500).
    """
    if active_section not in SURVEY_DEFINITION: # if a bad section is caught
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "BROKEN_DEFINITION",
                    "message": f"{active_section} not found in SURVEY_DEFINITON."
                }
            }
        )
    qmap = SURVEY_DEFINITION[active_section] # section aware

    if cursor is None:
        return None
    if cursor not in qmap:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "BROKEN_DEFINITION",
                    "message": f"Cursor '{cursor}' not found in SURVEY_DEFINITION.",
                },
                "meta": build_meta(),
            },
        )
    return qmap[cursor]


# ---------- request models ----------

class ResumeRequest(BaseModel):
    run_id: str


class AnswerRequest(BaseModel):
    run_id: str
    question_id: str
    # For single_choice/scale: this is the option key like "a" | "b" | ...
    # For free_text: this holds the text value.
    answer: Optional[str]


# ---------- endpoints ----------

@router.post("/survey/begin")
def begin_run():
    """
    Create a new run (session), persist it, and return the first question.
    """
    run_id = _new_run_id()
    cursor = START_ID           # points at the first question id (e.g., "q1")
    node = _cursor_to_node(cursor)

    # Build + persist a brand new run record
    record: SurveyRun = {
        "run_id": run_id,
        "version": SURVEY_VERSION,
        "status": "active",
        "active_section": "min_criteria",
        "cursor": cursor,
        "history": [],
        "answers_by_id": {},
        "summary": None,
    }
    STORE.create_run(record)

    # Format the node as a "next" payload for the client
    next_payload = show_question(node)["next"]

    return {
        "run_id": run_id,
        "done": False,
        "next": next_payload,
        "version": SURVEY_VERSION,
        "meta": build_meta(),
    }


@router.post("/survey/resume")
def resume_run(req: ResumeRequest):
    """
    Reattach to an existing run and tell the client what to show now.
    - If active -> return next question.
    - If completed/cancelled -> return done=true (and summary if completed).
    """
    run = _require_run(req.run_id)      # 404 if missing
    active_section = run["active_section"]
    qmap = SURVEY_DEFINITION[active_section]

    status = run["status"]
    cursor = run.get("cursor")

    if status == "completed":
        return {
            "run_id": run["run_id"],
            "done": True,
            "next": None,
            "summary": run.get("summary"),
            "version": run["version"],
            "meta": build_meta(),
        }

    if status == "cancelled":
        return {
            "run_id": run["run_id"],
            "done": True,
            "next": None,
            "summary": None,
            "version": run["version"],
            "meta": build_meta(),
        }

    # Active: we must have a valid cursor pointing at a node
    node = _cursor_to_node(cursor)
    next_payload = show_question(node)["next"]

    return {
        "run_id": run["run_id"],
        "done": False,
        "next": next_payload,
        "version": run["version"],
        "meta": build_meta(),
    }


@router.post("/survey/answer")
def answer_question(req: AnswerRequest):
    """
    Submit an answer for the current cursor and advance the run.
    This function is the *stateful wrapper* around the survey engine rules you
    already wrote (we reuse the same logic, not duplicate it).
    """
    # 1) Load + validate run
    run = _require_run(req.run_id)
    _require_active(run)

    active_section = run["active_section"]
    qmap = SURVEY_DEFINITION[active_section]

    cursor = run.get("cursor")
    node = _cursor_to_node(cursor=cursor, active_section=active_section)  # validates presence in qmap/active section map, unless None

    # Guard: the client must be answering the node we're on
    if req.question_id != cursor:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "FLOW_DIVERGENCE",
                    "message": f"Expected to answer '{cursor}', got '{req.question_id}'.",
                },
                "meta": build_meta(),
            },
        )

    # 2) Apply the same validation/transition rules you used in survey_next
    qtype = node["type"]

    # Free text node: answer is a string value; next is node-level "next"
    if qtype == "free_text":
        val = (req.answer or "").strip()
        if not val:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {"code": "MISSING_ANSWER", "message": f"Missing answer for {cursor}."},
                    "meta": build_meta(),
                },
            )

        # Example: q1a must be YYYY-MM-DD (you implemented the same rule in survey_next)
        if node["id"] == "q1a":
            import re
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", val):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {"code": "DATE_FORMAT", "message": "Use YYYY-MM-DD (e.g., 2025-09-01)"},
                        "meta": build_meta(),
                    },
                )

        # Persist answer
        answers = run["answers_by_id"]
        answers[cursor] = {"type": "free_text", "value": val}

        # Move to next (node-level)
        next_id = node.get("next")

    # Choice/scale node: answer is an option key ("a", "b", ...)
    elif qtype in ("single_choice", "scale"):
        key = (req.answer or "").strip()
        if not key:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {"code": "MISSING_ANSWER", "message": f"Missing answer for {cursor}."},
                    "meta": build_meta(),
                },
            )

        opts = node["options"]
        if key not in opts:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {"code": "INVALID_ANSWER", "message": f"Answer '{key}' not allowed for {cursor}."},
                    "meta": build_meta(),
                },
            )

        opt = opts[key]
        record = {"type": qtype, "key": key, "label": opt["label"]}

        # If scale, also store a numeric score parsed from the label ("8 - Hurts Whole Lot" -> 8)
        if qtype == "scale":
            import re
            m = re.match(r"\s*(\d+)\b", opt["label"])
            record["score"] = int(m.group(1)) if m else None

        # Persist answer
        answers = run["answers_by_id"]
        answers[cursor] = record

        # Next id comes from the option
        next_id = opt["next"]

    else:
        # Unknown type -> definition error
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "UNSUPPORTED_TYPE", "message": f"Unsupported type '{qtype}' on {cursor}."},
                "meta": build_meta(),
            },
        )

    # Append to history (lightweight audit trail)
    run["history"].append({"question_id": cursor, "answer": req.answer or ""})

    # 3) Finish or advance
    if next_id is None:
        # Mark the run completed and build a summary
        run["status"] = "completed"
        run["cursor"] = None
        run["summary"] = _build_summary(run["answers_by_id"])
        STORE.replace_run(run)  # persist

        return {
            "run_id": run["run_id"],
            "done": True,
            "next": None,
            "summary": run["summary"],
            "version": run["version"],
            "meta": build_meta(),
        }

    if isinstance(next_id, str) and next_id.startswith("GOTO:"):
        _, target_section, target_qid = next_id.split(":", 2)

        if target_section not in SURVEY_DEFINITION:
            raise HTTPException(
                status_code=500,
                detail={
                    "error":{
                        "code": "BROKEN_DEFINITION",
                        "message": f"GOTO target section '{target_section}' not found.",
                    },
                    "meta": build_meta(),
                },
            )
        target_map = SURVEY_DEFINITION[target_section] # qmap just diff name for this case
        if target_qid not in target_map:
            raise HTTPException(
                status_code=500,
                detail= {
                    "error": {
                        "code": "BROKEN_DEFINITION",
                        "message": f"GOTO target question '{target_qid}' not found in section '{target_section}'.",
                    },
                    "meta": build_meta(),
                },
            )
        
        # Update the run state
        run["active_section"] = target_section
        run["cursor"] = target_qid
        STORE.replace_run(run)

        # Load and return new node
        next_node = target_map[target_qid] # node = qmap[cursor]
        next_payload = show_question(next_node)["next"]

        return {
            "run_id": run["run_id"],
            "done": False,
            "next": next_payload,
            "version": run["version"],
            "meta": build_meta()
        }
    
    # Ensure next exists in the graph
    if next_id not in qmap:
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "BROKEN_DEFINITION",
                    "message": f"'{cursor}' points to unknown next '{next_id}'.",
                },
                "meta": build_meta(),
            },
        )

    # Advance cursor and persist
    run["cursor"] = next_id
    STORE.replace_run(run)

    next_node = qmap[next_id]
    next_payload = show_question(next_node)["next"]

    return {
        "run_id": run["run_id"],
        "done": False,
        "next": next_payload,
        "version": run["version"],
        "meta": build_meta(),
    }

@router.get("/survey/runs/{run_id}/answers")
def show_answer_history(req: AnswerRequest):
    run = _require_run(req.run_id)

    
