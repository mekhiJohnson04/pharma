# Abdominal Survey App (Step 1)

This step gets a minimal FastAPI server running so we can verify your environment.

## Run locally (recommended)

```bash
# From project root
cd backend

# Create and activate a virtual environment (macOS/Linux)
python3 -m venv .venv
source .venv/bin/activate

# (Windows)
# py -3 -m venv .venv
# .venv\Scripts\activate

# Install the minimal requirements for Step 1
pip install -r requirements.txt

# Run the server
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs to see the interactive API docs.

## Next

Once this is working, we'll:
1) Add a `survey` module with your branching questions
2) Add request/response models (Pydantic)
3) Add a webhook endpoint and (later) the database
