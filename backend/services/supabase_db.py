import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")
if not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError("SUPABASE_PUBLISHABLE_KEY is missing from .env")

REST_BASE = f"{SUPABASE_URL}/rest/v1"


def _request(*, method, table, access_token, query=None, body=None, prefer=None):
    if not access_token:
        raise ValueError("Missing Supabase access token.")

    url = f"{REST_BASE}/{table}"
    if query:
        url += "?" + urlencode(query, doseq=True)

    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    if prefer:
        headers["Prefer"] = prefer

    req = Request(url, data=data, headers=headers, method=method)

    try:
        with urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as error:
        try:
            raw = error.read().decode("utf-8")
            details = json.loads(raw)
            message = (
                details.get("message")
                or details.get("hint")
                or details.get("details")
                or raw
            )
        except Exception:
            message = str(error)
        raise RuntimeError(f"Supabase database error: {message}") from error
    except Exception as error:
        raise RuntimeError("Could not reach Supabase database.") from error


def _optional_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value):
    return None if value is None else str(value)


def create_drive_session(*, access_token, user_id):
    rows = _request(
        method="POST",
        table="drive_sessions",
        access_token=access_token,
        body={
            "user_id": user_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
        prefer="return=representation",
    )
    if not rows:
        raise RuntimeError("Supabase did not return the created drive session.")
    return rows[0]


def finish_drive_session(*, access_token, session_id, user_id, summary):
    summary = summary or {}

    payload = {
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": float(summary.get("drive_duration_seconds", 0) or 0),
        "attentive_percent": float(summary.get("attentive_percent", 0) or 0),
        "head_away_percent": float(summary.get("head_away_percent", 0) or 0),
        "confirmed_distraction_percent": float(summary.get("confirmed_distraction_percent", 0) or 0),
        "confirmed_distraction_seconds": float(summary.get("confirmed_distraction_seconds", 0) or 0),
        "blink_count": int(summary.get("blink_count", 0) or 0),
        "long_eye_closure_count": int(summary.get("long_eye_closure_count", 0) or 0),
        "drowsiness_event_count": int(summary.get("drowsiness_event_count", 0) or 0),
        "yawn_count": int(summary.get("yawn_count", 0) or 0),
        "distraction_event_count": int(summary.get("distraction_event_count", 0) or 0),
        "total_safety_alerts": int(summary.get("total_safety_alerts", 0) or 0),
        "head_direction_percent": summary.get("head_direction_percent") or {},
        "summary_json": summary,
    }

    rows = _request(
        method="PATCH",
        table="drive_sessions",
        access_token=access_token,
        query={
            "id": f"eq.{session_id}",
            "user_id": f"eq.{user_id}",
        },
        body=payload,
        prefer="return=representation",
    )

    if not rows:
        raise RuntimeError("Drive session could not be updated.")
    return rows[0]


def insert_drive_event(*, access_token, session_id, user_id, elapsed_seconds, event_type, message):
    return _request(
        method="POST",
        table="drive_events",
        access_token=access_token,
        body={
            "session_id": session_id,
            "user_id": user_id,
            "elapsed_seconds": float(elapsed_seconds or 0),
            "event_type": str(event_type or "EVENT"),
            "message": None if message is None else str(message),
        },
        prefer="return=minimal",
    )


def insert_drive_sample(*, access_token, session_id, user_id, state):
    state = state or {}

    return _request(
        method="POST",
        table="drive_samples",
        access_token=access_token,
        body={
            "session_id": session_id,
            "user_id": user_id,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "ear": _optional_float(state.get("ear")),
            "mar": _optional_float(state.get("mar")),
            "eye_state": _optional_text(state.get("eye_state")),
            "head_direction": _optional_text(state.get("head_direction")),
            "head_direction_confidence": _optional_float(state.get("head_direction_confidence")),
            "head_direction_probabilities": state.get("head_direction_probabilities") or {},
            "distraction_state": _optional_text(state.get("distraction_state")),
            "distraction_duration": float(state.get("distraction_duration", 0) or 0),
            "alert_state": _optional_text(state.get("alert_state")),
        },
        prefer="return=minimal",
    )


def list_drive_sessions(*, access_token, limit=50, offset=0):
    return _request(
        method="GET",
        table="drive_sessions",
        access_token=access_token,
        query={
            "select": "*",
            "order": "started_at.desc",
            "limit": str(int(limit)),
            "offset": str(int(offset)),
        },
    ) or []


def get_drive_session(*, access_token, session_id):
    rows = _request(
        method="GET",
        table="drive_sessions",
        access_token=access_token,
        query={
            "select": "*",
            "id": f"eq.{session_id}",
            "limit": "1",
        },
    ) or []
    return rows[0] if rows else None


def list_drive_events(*, access_token, session_id):
    return _request(
        method="GET",
        table="drive_events",
        access_token=access_token,
        query={
            "select": "*",
            "session_id": f"eq.{session_id}",
            "order": "elapsed_seconds.asc",
        },
    ) or []


def list_drive_samples(*, access_token, session_id, limit=1500):
    return _request(
        method="GET",
        table="drive_samples",
        access_token=access_token,
        query={
            "select": "*",
            "session_id": f"eq.{session_id}",
            "order": "captured_at.asc",
            "limit": str(int(limit)),
        },
    ) or []
