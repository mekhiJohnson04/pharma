from __future__ import annotations                                  # lets Python treat type hints as strings (deferred evaluation) this avoids circular import issues and speeds imports; handy when types reference eachother


from pydantic import BaseModel                                      # Defines request/ response models with automatic validation and parsing
from typing import Dict, Optional, List, TypedDict, Literal, Any    # type checking & documentation; defines the shape of dicts (e.g., what keys a stored run must have)
import threading                                                    # run tasks concurrently; thread-safe
import copy                                                         # clone Python objects safely; ensures callers get copies of stored runs, so they can't accidentally mutate the store's internal state
from datetime import datetime,  timezone                            # handle timestamps and time-zones

RunStatus = Literal["active", "completed", "cancelled"] # Literal - restricts a string to a specific value(s)

class HistoryStep(TypedDict):  # A single answered step in a run's history
    question_id: str
    answer: str

class SurveyRun(TypedDict, total=False):
    run_id: str
    version: str
    status: RunStatus
    cursor: Optional[str]
    history: List[HistoryStep]
    answers_by_id: Dict[str, Any]
    summary: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str

# ---- Helper function ----
def _ts_utc_iso() -> str:
    now_utc = datetime.now(timezone.utc)
    return now_utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")

# ---- Store Implementation ----

class InMemoryRunStore:
    def __init__(self) -> None:
        
        self._runs: Dict[str, SurveyRun] = {}   # _runs holds run_id -> SurveyRun
        self._lock = threading.RLock() # RLock allows re-entrant acquisition (safe if a method calls another) so concurrent requests dont corrupt shared data.

    def create_run(self, run: SurveyRun) -> None:   # insert a brand new run, fails if run_id already exists. Caller must provide a valid SurveyRun with run_id set.
        if "run_id" not in run or not run["run_id"]:
            raise ValueError(f"create_run: run.run_id is required.")
            
        with self._lock:    # [with] is a context manager used to acquire the start of the block (One Thread at a time) running the code inside the block safely and releasing the lock automatically at the end (Error or not)
            if run["run_id"] in self._runs:
                raise ValueError(f"create_run: run_id '{run['run_id']}' already exists.")
            
            # Stamp timestamps if caller forgot (defensive)
            run = copy.deepcopy(run)
            run.setdefault("created_at", _ts_utc_iso())
            run.setdefault("updated_at", run['created_at'])

            self._runs[run["run_id"]] = run

    def get_run(self, run_id: str) -> Optional[SurveyRun]:
        with self._lock:
            run = self._runs.get(run_id)
            return copy.deepcopy(run) if run else None

    def update_run(self, run_id: str, **changes: Any) -> SurveyRun:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"update_run: run_id '{run_id}' not found")
            
            # update in place
            record = self._runs[run_id]
            for k, v in changes.items():
                record[k] = v

            # Always bump updated_at
            record["updated_at"] = _ts_utc_iso()
            return copy.deepcopy(record)

    def replace_run(self, run: SurveyRun) -> SurveyRun:

        if "run_id" not in run or not run["run_id"]:
            raise ValueError("replace_run: run.run_id is required")
            
        with self._lock:   # thread safety; one run at a time
            run_id = run["run_id"]
            if run_id not in self._runs:
                raise KeyError(f"replace_run: run_id '{run_id}' not found")
            
            new_run = copy.deepcopy(run)
            new_run["updated_at"] = _ts_utc_iso()
            self._runs[run_id] = new_run
            return copy.deepcopy(new_run)

            #replace run

