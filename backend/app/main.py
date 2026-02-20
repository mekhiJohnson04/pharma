# ------------------------------
# FastAPI "Hello API" skeleton
# Goal: boot a server so we know our toolchain works
# ------------------------------
import os
# Import FastAPI class to create the web app
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import survey
from app.routes.runs import router as runs_router
from app.api.debug import router as debug_router
from dotenv import load_dotenv
load_dotenv(dotenv_path=".env")
print("DATABASE_URL loaded?", bool(os.getenv("DATABASE_URL")))
# Create an application instance.
# 'app' is what Uvicorn looks for when you run: uvicorn app.main:app --reload
app = FastAPI(
    title="Abdominal Survey API",          # Shows up in docs
    version="0.1.0"                        # Semantic version for your service
)

# Allow the lightweight dashboard (served from a static file server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Dev-friendly: accept all origins so any local port works
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define a simple "health check" route so we can verify the server is alive.
# Method: GET
# Path:   /health
@app.get("/health")
def health_check():
    # Returning a dict automatically becomes JSON: {"status": "ok"}
    return {"status": "ok"}

# Define a basic root route.
# Method: GET
# Path:   /
@app.get("/")
def root():
    # Friendly message so you know the server is serving requests.
    return {"message": "API is running. Go to /docs for Swagger UI."}

# Notes:
# - Nothing here touches a database or external services yet.
# - The goal is to confirm your dev environment is set up before we add complexity.
app.include_router(survey.router, prefix="/api")
app.include_router(runs_router, prefix="/api")
app.include_router(debug_router)