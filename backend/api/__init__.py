import json
import os
import subprocess
import sys

from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.middleware.cors import (
    CORSMiddleware,
)


# =========================================================
# PROJECT PATHS
# =========================================================

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]


SUMMARY_DIRECTORY = (
    PROJECT_ROOT
    /
    "data"
    /
    "session_summaries"
)


# =========================================================
# CAMERA PROCESS
# =========================================================

monitor_process = None


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="NINO API",
    description=(
        "Backend API for NINO "
        "AI Driver Safety & Monitoring System"
    ),
    version="1.0.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],
)


# =========================================================
# HELPERS
# =========================================================

def _summary_files():

    if not SUMMARY_DIRECTORY.exists():

        return []

    files = list(
        SUMMARY_DIRECTORY.glob(
            "drive_*_summary.json"
        )
    )

    return sorted(
        files,
        key=lambda path:
            path.stat().st_mtime,
        reverse=True,
    )


def _load_json(
    path,
):

    try:

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(
                file
            )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not read session summary: "
                f"{error}"
            ),
        )


def _monitor_is_running():

    global monitor_process

    if monitor_process is None:

        return False

    return (
        monitor_process.poll()
        is None
    )


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "system": "NINO",
        "status": "online",
        "docs": "/docs",
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "system": "NINO",
        "monitoring":
            _monitor_is_running(),
    }


# =========================================================
# START DRIVER MONITORING
# =========================================================

@app.post(
    "/api/monitor/start"
)
def start_monitoring():

    global monitor_process

    if _monitor_is_running():

        return {
            "status": "already_running",
            "message": (
                "NINO driver monitoring "
                "is already running."
            ),
        }

    try:

        creation_flags = 0

        if os.name == "nt":

            creation_flags = (
                subprocess.CREATE_NEW_PROCESS_GROUP
            )

        monitor_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "scripts.driver_monitor_test",
            ],

            cwd=str(
                PROJECT_ROOT
            ),

            creationflags=creation_flags,
        )

        return {
            "status": "started",

            "message": (
                "NINO camera monitoring started."
            ),

            "pid":
                monitor_process.pid,
        }

    except Exception as error:

        monitor_process = None

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not start monitoring: "
                f"{error}"
            ),
        )


# =========================================================
# STOP DRIVER MONITORING
# =========================================================

@app.post(
    "/api/monitor/stop"
)
def stop_monitoring():

    global monitor_process

    if not _monitor_is_running():

        monitor_process = None

        return {
            "status": "not_running",
            "message": (
                "NINO monitoring is not running."
            ),
        }

    try:

        monitor_process.terminate()

        try:

            monitor_process.wait(
                timeout=5
            )

        except subprocess.TimeoutExpired:

            monitor_process.kill()

            monitor_process.wait(
                timeout=2
            )

        monitor_process = None

        return {
            "status": "stopped",
            "message": (
                "NINO camera monitoring stopped."
            ),
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not stop monitoring: "
                f"{error}"
            ),
        )


# =========================================================
# MONITOR STATUS
# =========================================================

@app.get(
    "/api/monitor/status"
)
def monitor_status():

    running = (
        _monitor_is_running()
    )

    return {
        "running": running,

        "status":
            "monitoring"
            if running
            else "stopped",
    }


# =========================================================
# LIST SESSIONS
# =========================================================

@app.get(
    "/api/sessions"
)
def list_sessions():

    files = _summary_files()

    sessions = []

    for path in files:

        summary = _load_json(
            path
        )

        sessions.append({

            "session_id":
                summary.get(
                    "session_id"
                ),

            "start_timestamp_utc":
                summary.get(
                    "start_timestamp_utc"
                ),

            "drive_duration_seconds":
                summary.get(
                    "drive_duration_seconds"
                ),

            "attentive_percent":
                summary.get(
                    "attentive_percent"
                ),

            "confirmed_distraction_percent":
                summary.get(
                    "confirmed_distraction_percent"
                ),

            "drowsiness_event_count":
                summary.get(
                    "drowsiness_event_count"
                ),

            "distraction_event_count":
                summary.get(
                    "distraction_event_count"
                ),

            "total_safety_alerts":
                summary.get(
                    "total_safety_alerts"
                ),
        })

    return {
        "count":
            len(sessions),

        "sessions":
            sessions,
    }


# =========================================================
# LATEST SESSION
# =========================================================

@app.get(
    "/api/sessions/latest"
)
def latest_session():

    files = _summary_files()

    if not files:

        raise HTTPException(
            status_code=404,
            detail=(
                "No NINO session "
                "summaries found."
            ),
        )

    return _load_json(
        files[0]
    )


# =========================================================
# SPECIFIC SESSION
# =========================================================

@app.get(
    "/api/sessions/{session_id}"
)
def get_session(
    session_id: str,
):

    files = _summary_files()

    for path in files:

        summary = _load_json(
            path
        )

        if (
            summary.get(
                "session_id"
            )
            ==
            session_id
        ):

            return summary

    raise HTTPException(
        status_code=404,
        detail=(
            f"Session not found: "
            f"{session_id}"
        ),
    )