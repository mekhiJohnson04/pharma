# HTTP Routes (requests/response shapes, calls engine)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from app.core import config
import re

router = APIRouter() # Routers = modular endpoints (keeps code organized by endpoints)

@router.get("/survey/test")
def survey_test():
    return {"status": "survey alive"}

class SurveyRequest(BaseModel):
    question_id: Optional[str]
    answer: Optional[str]


SURVEY_DEFINITION = {
    "min_criteria_questions": {

    "q1": {
        "id": "q1",
        "text": "Who is reporting this information?",
        "type": "single_choice",
        "options": {
            "a": {"label": "I am a healthcare professional (HCP)", "next": "q2"},
            "b": {"label": "I am not a healthcare professional (consumer)", "next": "q2"},
            "c": {"label": "This is from a published article (literature)", "next": "q2"},
            "d": {"label": "This is from a partner organization", "next": "q2"},
            "e": {"label": "This is from a study", "next": "q2"}
        },
        "constraints": {"required": True}
    },

    "q2": {
        "id": "q2",
        "text": "Can we contact you for follow-up if needed?",
        "type": "single_choice",
        "options": {
            "a": {"label": "Yes", "next": "q2a"},
            "b": {"label": "No", "next": "q3"}
        },
        "constraints": {"required": True}
    },

    "q2a": {
        "id": "q2a",
        "text": "What is the best way to contact you?",
        "type": "single_choice",
        "options": {
            "a": {"label": "Email", "next": "q2a_email"},
            "b": {"label": "Phone", "next": "q2a_phone"},
            "c": {"label": "Other", "next": "q2a_other"}
        },
        "constraints": {"required": True}
    },

    "q2a_email": {
        "id": "q2a_email",
        "text": "Enter your email address",
        "type": "free_text",
        "next": "q3",
        "hints": {"placeholder": "name@example.com"},
        "constraints": {"required": True}
    },

    "q2a_phone": {
        "id": "q2a_phone",
        "text": "Enter your phone number",
        "type": "free_text",
        "next": "q3",
        "hints": {"placeholder": "e.g., +1 555 555 5555"},
        "constraints": {"required": True}
    },

    "q2a_other": {
        "id": "q2a_other",
        "text": "Enter the best way to contact you",
        "type": "free_text",
        "next": "q3",
        "hints": {"placeholder": "e.g., secure portal message"},
        "constraints": {"required": True}
    },

    "q3": {
        "id": "q3",
        "text": "Are you the person who experienced the event?",
        "type": "single_choice",
        "options": {
            "a": {"label": "Yes (I am the patient)", "next": "q4"},
            "b": {"label": "No (I am reporting for someone else)", "next": "q3a"}
        },
        "constraints": {"required": True}
    },

    "q3a": {
        "id": "q3a",
        "text": "What is your relationship to the patient?",
        "type": "single_choice",
        "options": {
            "a": {"label": "Parent/Guardian", "next": "q4"},
            "b": {"label": "Spouse/Partner", "next": "q4"},
            "c": {"label": "Family member", "next": "q4"},
            "d": {"label": "Caregiver", "next": "q4"},
            "e": {"label": "Friend/Other", "next": "q3a_other"}
        },
        "constraints": {"required": True}
    },

    "q3a_other": {
        "id": "q3a_other",
        "text": "Describe your relationship to the patient",
        "type": "free_text",
        "next": "q4",
        "hints": {"placeholder": "e.g., roommate, coach, etc."},
        "constraints": {"required": True}
    },

    "q4": {
        "id": "q4",
        "text": "Please provide at least one detail about the person who experienced the event.",
        "type": "single_choice",
        "options": {
            "a": {"label": "Age", "next": "q4a"},
            "b": {"label": "Sex", "next": "q4b"},
            "c": {"label": "Initials (optional identifier)", "next": "q4c"},
            "d": {"label": "I don't know any of these", "next": "q4_missing"}
        },
        "constraints": {"required": True}
    },

    "q4a": {
        "id": "q4a",
        "text": "Enter the patient's age (number only)",
        "type": "free_text",
        "next": "q4a_unit",
        "hints": {"placeholder": "e.g., 34"},
        "constraints": {"required": True}
    },

    "q4a_unit": {
        "id": "q4a_unit",
        "text": "Select the age unit",
        "type": "single_choice",
        "options": {
            "a": {"label": "Years", "next": "q5"},
            "b": {"label": "Months", "next": "q5"},
            "c": {"label": "Days", "next": "q5"},
            "d": {"label": "Unknown", "next": "q5"}
        },
        "constraints": {"required": True}
    },

    "q4b": {
        "id": "q4b",
        "text": "Select the patient's sex",
        "type": "single_choice",
        "options": {
            "a": {"label": "Male", "next": "q5"},
            "b": {"label": "Female", "next": "q5"},
            "c": {"label": "Other", "next": "q5"},
            "d": {"label": "Unknown", "next": "q5"}
        },
        "constraints": {"required": True}
    },

    "q4c": {
        "id": "q4c",
        "text": "Enter the patient's initials",
        "type": "free_text",
        "next": "q5",
        "hints": {"placeholder": "e.g., J.D."},
        "constraints": {"required": True}
    },

    "q4_missing": {
        "id": "q4_missing",
        "text": "Understood. Without at least one patient detail (age, sex, or initials), the report may be incomplete. Would you like to proceed anyway?",
        "type": "single_choice",
        "options": {
            "a": {"label": "Yes, proceed", "next": "q5"},
            "b": {"label": "No, go back", "next": "q4"}
        },
        "constraints": {"required": True}
    },

    "q5": {
        "id": "q5",
        "text": "What product do you believe is related to the event?",
        "type": "free_text",
        "next": "q6",
        "hints": {"placeholder": "e.g., medication/vaccine name"},
        "constraints": {"required": True}
    },

    "q6": {
        "id": "q6",
        "text": "What happened?",
        "type": "free_text",
        "next": "GOTO:ae_selector:q1",
        "hints": {"placeholder": "Describe the symptoms or event in your own words"},
        "constraints": {"required": True}
    },

},

    "ae_selector": {
        "q1": {
            "id": "q1",
            "text": "Which symptom category best matches?",
            "type": "single_choice",
            "options": {
            "a": {"label": "Abdominal / GI", "next": "GOTO:abdominal_questions:q1"},
            "b": {"label": "Headache / Neuro", "next": "GOTO:headache_questions:q1"},
            "c": {"label": "Vomiting", "next": "GOTO:vomiting_questions:q1"},
            }
        }
    },

    "abdominal_questions": {

        "q1": {
            "id": "q1",
            "text": "When did this symptom start?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Exact date, if known", "next": "q1a"},   # -> new free_text node
                "b": {"label": "Approximate date",      "next": "q1b"}    # -> new free_text node
            }
        },

        # --- new node: exact date ---
        "q1a": {
            "id": "q1a",
            "text": "Enter the exact date (YYYY-MM-DD)",
            "type": "free_text",
            "next": "q2",
            "hints": {"placeholder": "YYYY-MM-DD"},
            "constraints": {"required": True}
        },

        # --- new node: approximate date ---
        "q1b": {
            "id": "q1b",
            "text": "Enter an approximate date (e.g., 'about 2 weeks ago')",
            "type": "free_text",
            "next": "q2",
            "hints": {"placeholder": "e.g., about 2 weeks ago"},
            "constraints": {"required": True}
        },

        "q2": {
            "id": "q2",
            "text": "Do you still have pain?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes. Go to #4.", "next": "q4"},
                "b": {"label": "No.", "next": "q3"}
            }
        },

        "q3": {
            "id": "q3",
            "text": "When did the symptom stop?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Exact date, if known", "next": "q4"},
                "b": {"label": "Approximate date", "next": "q3b"}
            }
        },

        "q3a": {
            "id": "q3a",
            "text": "Enter the exact date (YYYY-MM-DD)",
            "type": "free_text",
            "next": "q4",
            "hints": {"placeholder": "YYYY-MM-DD"},
            "constraints": {"required": True}
        },

          "q3b": {
            "id": "q3b",
            "text": "Enter an approximate date the symptoms stopped (e.g., 'about 2 weeks ago')",
            "type": "free_text",
            "next": "q4",
            "hints": {"placeholder": "e.g., about 2 weeks ago"},
            "constraints": {"required": True}
        },

        "q4": {
            "id": "q4",
            "text": "Is (was) the pain:",
            "type": "single_choice",
            "options": {
                "a": {"label": "Sharp?", "next": "q5"},
                "b": {"label": "Dull?", "next": "q5"},
                "c": {"label": "Throbbing?", "next": "q5"},
                "d": {"label": "Burning?", "next": "q5"},
                "e": {"label": "Cramping?", "next": "q5"}
            }
        },

        "q5": {
            "id": "q5",
            "text": "How would you grade the intensity of the pain? (Refer to visual analog pain scale)",
            "type": "scale",
            "options": {  # For now we will leave next as None but, later we will wire to q6.
                "a": {"label": "2 - Hurts Little Bit", "next": "q6"},
                "b": {"label": "4 - Hurts Little More", "next": "q6"},
                "c": {"label": "6 - Hurts Even More", "next": "q6"},
                "d": {"label": "8 - Hurts Whole Lot", "next": "q6"},
                "e": {"label": "10 - Hurts Worst", "next": "q6"}
            }
        },
        # --- Q6: sleep disruption ---
        "q6": {
            "id": "q6",
            "text": "Does (did) the symptom disrupt your sleep?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes.", "next": "q7"},
                "b": {"label": "No.",  "next": "q7"},
                "c": {"label": "N/A. I did not have pain during sleep.", "next": "q7"}
            }
        },

        # --- Q7: localized vs generalized ---
        "q7": {
            "id": "q7",
            "text": "Is (was) the abdominal pain localized or generalized?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Localized. (Confined to one specific area of the body)",   "next": "q8"},
                "b": {"label": "Generalized. (Affect the entire body or a large region of it)", "next": "q9"}
            }
        },

        # --- Q8: main location (refer to figure 1) ---
        "q8": {
            "id": "q8",
            "text": "Where in the abdomen is (was) the pain mainly located? (Refer to figure 1.)",
            "type": "single_choice",
            "options": {
                "a": {"label": "Upper right side (RUQ)",          "next": "q9"},
                "b": {"label": "Lower right side (RLQ)",          "next": "q9"},
                "c": {"label": "Upper left side (LUQ)",           "next": "q9"},
                "d": {"label": "Lower left side (LLQ)",           "next": "q9"},
                "e": {"label": "Upper central (epigastric)",      "next": "q9"},
                "f": {"label": "Middle central (periumbilical)",  "next": "q9"},
                "g": {"label": "Lower central (suprapubic)",      "next": "q9"}
            }
        },

        # --- Q9: radiate? ---
        "q9": {
            "id": "q9",
            "text": "Does (did) the pain radiate?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes.", "next": "q10"},
                "b": {"label": "No. Go to #11.", "next": "q11"}
            }
        },

        # --- Q10: where does it radiate (free text) ---
        "q10": {
            "id": "q10",
            "text": "Where does (did) the pain radiate? (Refer to figure 1.)",
            "type": "free_text",
            "next": "q11",
            "hints": {"placeholder": "e.g., back, shoulder, groin"},
            "constraints": {"required": True}
        },

        # --- Q11: current course of symptom ---
        "q11": {
            "id": "q11",
            "text": "If you are still having this symptom, is it:",
            "type": "single_choice",
            "options": {
                "a": {"label": "Worsening?",            "next": "q12"},
                "b": {"label": "Stable?",               "next": "q12"},
                "c": {"label": "Improving?",            "next": "q12"},
                "d": {"label": "Unsure.",               "next": "q12"},
                "e": {"label": "No longer having pain.", "next": "q12"}
            }
        },

        # --- Q12: impact on routine ---
        "q12": {
            "id": "q12",
            "text": "The symptom",
            "type": "single_choice",
            "options": {
                "a": {"label": "Has not affected my daily routine at all.",            "next": "q13"},
                "b": {"label": "Has caused me to cancel some of my daily routine.",    "next": "q13"},
                "c": {"label": "Has caused me to cancel all of my daily routine.",     "next": "q13"}
            }
        },

        # --- Q13: abdominal tenderness ---
        "q13": {
            "id": "q13",
            "text": "Is (was) there any abdominal tenderness (area tender to touch)?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes", "next": "q14"},
                "b": {"label": "No",  "next": "q14"}
            }
        },

        # --- Q14: recent trauma ---
        "q14": {
            "id": "q14",
            "text": "Have you had any recent trauma before the symptom began?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes.", "next": "q15"},
                "b": {"label": "No.",  "next": "q15"}
            }
        },

        # --- Q15: positional pain ---
        "q15": {
            "id": "q15",
            "text": "Is (was) the abdominal pain positional (better/worse in a position)?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes.", "next": "q16"},
                "b": {"label": "No.",  "next": "q16"}
            }
        },

        # --- Q16: anything lessens/improves? -> optional detail ---
        "q16": {
            "id": "q16",
            "text": "Does (did) anything appear to lessen or improve the symptom?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes. What?", "next": "q16a"},
                "b": {"label": "No.",        "next": "q17"}
            }
        },
        "q16a": {
            "id": "q16a",
            "text": "What improves the symptom?",
            "type": "free_text",
            "next": "q17",
            "hints": {"placeholder": "e.g., rest, heat, medication name"},
            "constraints": {"required": True}
        },

        # --- Q17: anything worsens? -> optional detail ---
        "q17": {
            "id": "q17",
            "text": "Does (did) anything appear to worsen the symptom?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes. What?", "next": "q17a"},
                "b": {"label": "No.",        "next": "q18"}
            }
        },
        "q17a": {
            "id": "q17a",
            "text": "What worsens the symptom?",
            "type": "free_text",
            "next": "q18",
            "hints": {"placeholder": "e.g., certain foods, movement"},
            "constraints": {"required": True}
        },

        # --- Q18: deep breath worsens? ---
        "q18": {
            "id": "q18",
            "text": "Does (did) taking a deep breath worsen the abdominal pain?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes.", "next": "q19"},
                "b": {"label": "No.",  "next": "q19"}
            }
        },

        # --- Q19: unusual stress -> optional detail ---
        "q19": {
            "id": "q19",
            "text": "Are you under any unusual stress?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes. What?", "next": "q19a"},
                "b": {"label": "No.",        "next": "q20"}
            }
        },
        "q19a": {
            "id": "q19a",
            "text": "Describe the stress:",
            "type": "free_text",
            "next": "q20",
            "hints": {"placeholder": "brief description"},
            "constraints": {"required": True}
        },

        # --- Q20: apparent cause -> optional detail ---
        "q20": {
            "id": "q20",
            "text": "Did anything appear to cause this symptom?",
            "type": "single_choice",
            "options": {
                "a": {"label": "Yes. What?", "next": "q20a"},
                "b": {"label": "No.",        "next": None}
            }
        },
        "q20a": {
            "id": "q20a",
            "text": "What do you think caused the symptom?",
            "type": "free_text",
            "next": "q21",
            "hints": {"placeholder": "brief description"},
            "constraints": {"required": True}
        },

    },
    
    "headache_questions":{










    }
}


def build_meta() -> dict: # Returning server_authored metadata with an ISO-8601 UTC timestamp

    now_utc = datetime.now(timezone.utc) # timezone aware UTC
    ts = now_utc.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    return {
        "version": config.SURVEY_VERSION,
        "timestamp": ts
    }

def show_question(question) -> dict:
    payload = {
        "next": {
            "id": question["id"],
            "text": question["text"],
            "type": question["type"],
        },
        "done": False,
        "meta": build_meta(),
    }

    # Only include options for choice/scale questions
    if "options" in question and isinstance(question["options"], dict):
        payload["next"]["options"] = [
            {"key": k, "label": v["label"]} for k, v in question["options"].items()
        ]

    # (Nice) surface UI helpers for free_text
    if "hints" in question:
        payload["next"]["hints"] = question["hints"]
    if "constraints" in question:
        payload["next"]["constraints"] = question["constraints"]

    return payload


START_ID = "q1"

@router.post("/survey/next")    # Primary route: advances one question forward
def survey_next(request: SurveyRequest):
    active_section = "min_criteria"
    

    if request.question_id is None:    # The Pydantic model (SurveyRequest) has two fields: question_id and answer which are both Optional[str]
        current = SURVEY_DEFINITION[active_section][START_ID]   
        return show_question(current)
    
    qmap = SURVEY_DEFINITION[active_section]     # local alias for the questions map
    qid = request.question_id   # the question the client claims they just answered

    if qid not in qmap:     # guard: unknown question id
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "UNKNOWN_QUESTION", "message": "Invalid question ID: " + qid}, 
                "meta": build_meta()}
        )
    
    current = qmap[qid]     # the node we are validating/advancing from 

    #[current] is the node object for the question-id while current = qmap[qid] gives us the full dictionary for any specific question.

    if current["type"] == "free_text":    # has to be handled before single choice and scale so nothing triggers to early
        ans_text = request.answer # read answer from the request, not input()

        if ans_text is None or not isinstance(ans_text, str) or not ans_text.strip():
            raise HTTPException (
                status_code=400,
                detail={
                    "error": {"code": "MISSING_ANSWER", "message": f"Missing answer for {qid}: {current['text']}"},
                    "meta": build_meta()
                }
            )
        
        needs_iso_date = current["id"] == "q1a" or current.get("constraints", {}).get("pattern") == "ISO_YYYY_MM_DD"
        if needs_iso_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", ans_text.strip()):     # guard: incorrect date format
            raise HTTPException (
                status_code=400,
                detail={
                    "error": {"code": "DATE_FORMAT", "message": "Use YYYY-MM-DD (e.g., 2025-09-01)"},
                    "meta": build_meta()
                }
            )
        
        # follow node-level next
        next_qid = current.get("next")
        if next_qid is None or next_qid == "END":    # if none, survey ends here
            return {"next": None, "done": True, "meta": build_meta()}
        
        if next_qid not in qmap:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {"code": "BROKEN_DEFINITION",
                              "message": f"free_text '{qid}' points to unknown question '{next_qid}'"},
                    "meta": build_meta()
                }
            )
        
        next_node = qmap[next_qid]
        return show_question(next_node)

    if current["type"] not in ("single_choice", "scale"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {"code": "UNSUPPORTED_TYPE", "message": f"Unsupported type {current['type']}"}, 
                "meta": build_meta()}
        )
    
    
    ans_key = request.answer
    ans_options = current["options"]

    if ans_key is None or not isinstance(ans_key, str) or ans_key.strip() == "":
        raise HTTPException (
            status_code=400,
            detail={
                "error": {"code": "MISSING_ANSWER", "message": "Missing answer for " + qid + ": " + current["text"]}, 
                "meta": build_meta()}
        )
    if ans_key in ans_options:
        next_qid = ans_options[ans_key]["next"]

        if next_qid is None:
            return {"next": None, "done": True, "meta": build_meta()}
        
        if next_qid not in qmap:
            # Developer/Config error
            raise HTTPException(
                status_code=500,
                detail={
                "error": {
                    "code": "BROKEN_DEFINITION",
                    "message": f"Option '{ans_key}' on '{qid}' points to unknown question '{next_qid}'"
                },
            "meta": build_meta()
            }
        )
        
        next_node = qmap[next_qid]  # safe next node
        return show_question(next_node) # present the node

    else:
        raise HTTPException (
            status_code=400,
            detail={"error": {"code": "INVALID_ANSWER", "message": "Answer not allowed for " + qid}, "meta": build_meta()}
        )
    
class HistoryStep(BaseModel):
    question_id: str
    answer: str
        
class EvaluateRequest(BaseModel):
    history: List[HistoryStep]

# Helper to parse a numeric score from "10 - Hurts worst" to an Integer (10) for computational purposes
def _parse_scale(label: str) -> Optional[int]:
    m = re.match(r"\s*(\d+)\b", label or "")
    return int(m.group(1)) if m else None

def _build_summary(answers_by_id: dict) -> dict:
    if "q1a" in answers_by_id:
        started_at_precision = "exact"
        started_at_value = answers_by_id["q1a"]["value"]
    
    elif "q1b" in answers_by_id:
        started_at_precision = "approx"
        started_at_value = answers_by_id["q1b"]["value"]
    
    else:
        started_at_precision = None
        started_at_value = None
    
    # still pain
    still_pain = None

    if "q2" in answers_by_id:
        still_pain = answers_by_id["q2"]["key"] == "a" # only true if patient answers "a" for q2. (still_pain = True)

    # pain_quality (label), pain_scale (number)
    pain_quality = answers_by_id.get("q4", {}).get("label")
    pain_scale = answers_by_id.get("q5", {}).get("score")

    requires_attention = bool(pain_scale is not None and pain_scale >= 8)

    return {
        "started_at_precision": started_at_precision,
        "started_at_value": started_at_value,
        "still_pain": still_pain,
        "pain_quality": pain_quality,
        "pain_scale": pain_scale,
        "requires_attention": requires_attention,
    }

@router.post("/survey/evaluate")
def evaluate_survey_progress(request: EvaluateRequest):
    qmap = SURVEY_DEFINITION["abdominal_questions"]

    answers_by_id = {}
    # cursor is a single source of truth for expected position
    cursor = START_ID # "q1" default
    steps = request.history # array of steps

    if not request.history:
        return show_question(qmap[cursor]) # Consumed all steps: not finished -> tell client what to ask next

        

    for step in steps:
        if step.question_id != cursor:
            raise HTTPException (
                status_code=400,
                detail={
                    "error":{"code": "FLOW_DIVERGENCE", "message": f"Expected '{cursor}', got '{step.question_id}'"}, 
                    "meta": build_meta()
                }
            )
        
        if cursor not in qmap:
            raise HTTPException(
                status_code=500,
                detail={"error": {"code": "BROKEN_DEFINITION", "message": f"Missing node for expected cursor '{cursor}'"},
                        "meta": build_meta()
                }
            )


        node = qmap[cursor]

        qtype = node["type"]
        if qtype == "free_text":
            val = step.answer
            if val is None or not isinstance(val, str) or not val.strip():
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {
                            "code": "MISSING_ANSWER",
                            "message": f"Missing answer for {cursor}: {node['text']}"
                        },
                        "meta": build_meta(),
                    },
                )
            # q1a exact-date formatting
            if node["id"] == "q1a" and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", val.strip()):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {"code": "DATE_FORMAT",
                                  "message": "Use YYYY-MM-DD (e.g., 2025-09-01)"},
                                  "meta": build_meta(),
                    },
                )
            
            answers_by_id[cursor] = {"type": "free_text", "value": val.strip()}
            next_id = node.get("next")

        elif qtype in ("single_choice", "scale"):
            key = step.answer
            if key is None or not isinstance(key, str) or not key.strip():
                raise HTTPException(
                    status_code=400, 
                    detail={
                        "error":{
                            "code": "MISSING_ANSWER",
                            "message": f"Missing answer for {cursor}: {node['text']}"
                        },
                        "meta": build_meta(),
                    }
                )
            
            opts = node["options"]

            if key not in opts:     # if answer key is not an option, raise an error
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": {"code": "INVALID_ANSWER",
                                  "message": f"Answer key '{key}' not allowed for {cursor}"},
                                  "meta": build_meta(),
                    },
                )
            
            opt = opts[key]
            record = {"type":qtype, "key": key, "label": opt["label"]}

            if qtype == "scale":     # if the question type = scale, then add logic to the said scale using the parse scale function.
                record["score"] = _parse_scale(opt["label"])
            
            answers_by_id[cursor] = record
            next_id = opt["next"]

        else:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {"code": "UNSUPPORTED_TYPE",
                              "message": f"Unsupported type {qtype} on {cursor}"},
                              "meta": build_meta(),
                },
            )
        # 3 Advance or finish
        if next_id is None:
            return {
                "next": None,
                "done": True,
                "summary": _build_summary(answers_by_id),
                "meta": build_meta(),
            }
        
        if next_id not in qmap:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {"code": "BROKEN_DEFINITION",
                              "message": f"'{cursor}' points to unknown next '{next_id}'"},
                              "meta": build_meta(),
                },
            )
        
        cursor = next_id    # move to next node
        
    return show_question(qmap[cursor])



# 8nTeVlLcQtCnSxD572DKpg resume
# begin - GiJ-hG04R3qFrXdKfu4E8A




#