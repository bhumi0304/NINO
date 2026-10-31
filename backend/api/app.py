
import asyncio
import threading
import time
from pathlib import Path

from fastapi import (
    FastAPI,
    Header,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from backend.services.model_evaluation_service import (
    load_model_evaluation,
)

from backend.services.realtime_monitor import RealtimeMonitorService
from backend.services.supabase_auth import (
    get_display_name,
    verify_access_token,
)
from backend.services.supabase_db import (
    create_drive_session,
    finish_drive_session,
    get_drive_session,
    insert_drive_event,
    insert_drive_sample,
    list_drive_events,
    list_drive_samples,
    list_drive_sessions,
)

from backend.analytics.drive_insights import (
    compute_drive_insights,
)


# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="NINO API",
    description=(
        "Backend API for the NINO "
        "AI Driver Safety & Monitoring System"
    ),
    version="5.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# PER-USER RUNTIME
# =========================================================

_USER_SERVICES: dict[str, RealtimeMonitorService] = {}

# Supabase drive UUID currently attached to each user's
# active realtime monitor.
_USER_DB_SESSION_IDS: dict[str, str] = {}

# Last time a telemetry sample was persisted.
_USER_LAST_SAMPLE_AT: dict[str, float] = {}

# Event keys already written to Supabase during the current
# drive. Prevents the same timeline item being inserted on
# every WebSocket response.
_USER_SAVED_EVENT_KEYS: dict[str, set] = {}

_USER_LOCK = threading.RLock()

SAMPLE_INTERVAL_SECONDS = 1.0


def _get_user_service(
    user_id: str,
) -> RealtimeMonitorService:

    with _USER_LOCK:

        service = _USER_SERVICES.get(
            user_id
        )

        if service is None:

            service = (
                RealtimeMonitorService()
            )

            _USER_SERVICES[
                user_id
            ] = service

        return service


def _remove_user_runtime(
    user_id: str,
):

    with _USER_LOCK:

        service = (
            _USER_SERVICES.pop(
                user_id,
                None,
            )
        )

        _USER_DB_SESSION_IDS.pop(
            user_id,
            None,
        )

        _USER_LAST_SAMPLE_AT.pop(
            user_id,
            None,
        )

        _USER_SAVED_EVENT_KEYS.pop(
            user_id,
            None,
        )

    if service is not None:

        try:
            service.close()

        except Exception as error:
            print(
                "NINO runtime cleanup warning:",
                error,
            )


# =========================================================
# AUTH HELPERS
# =========================================================

def _extract_bearer_token(
    authorization: str | None,
):

    if not authorization:
        return None

    prefix = "Bearer "

    if not authorization.startswith(
        prefix
    ):
        return None

    token = authorization[
        len(prefix):
    ].strip()

    return token or None


def _require_user_and_token(
    authorization: str | None,
):

    token = _extract_bearer_token(
        authorization
    )

    if not token:

        raise HTTPException(
            status_code=401,
            detail=(
                "Supabase authentication required."
            ),
        )

    try:

        user = verify_access_token(
            token
        )

    except ValueError as error:

        raise HTTPException(
            status_code=401,
            detail=str(error),
        ) from error

    return user, token


def _public_user(
    user,
):

    metadata = (
        user.get(
            "user_metadata"
        )
        or
        {}
    )

    return {
        "id":
            user.get(
                "id"
            ),

        "name":
            get_display_name(
                user
            ),

        "email":
            user.get(
                "email"
            ),

        "role":
            metadata.get(
                "role"
            )
            or
            "Driver",
    }


# =========================================================
# DATABASE TRANSFORM HELPERS
# =========================================================

def _session_row_to_summary(
    row,
):
    """
    Convert a drive_sessions row into the shape already used
    by the React dashboard/analytics pages.
    """

    if not row:
        return None

    stored_summary = (
        row.get(
            "summary_json"
        )
        or
        {}
    )

    result = dict(
        stored_summary
    )

    result.update({
        "session_id":
            row.get(
                "id"
            ),

        "start_timestamp_utc":
            row.get(
                "started_at"
            ),

        "end_timestamp_utc":
            row.get(
                "ended_at"
            ),

        "drive_duration_seconds":
            row.get(
                "duration_seconds"
            )
            or
            0,

        "attentive_percent":
            row.get(
                "attentive_percent"
            )
            or
            0,

        "head_away_percent":
            row.get(
                "head_away_percent"
            )
            or
            0,

        "confirmed_distraction_percent":
            row.get(
                "confirmed_distraction_percent"
            )
            or
            0,

        "confirmed_distraction_seconds":
            row.get(
                "confirmed_distraction_seconds"
            )
            or
            0,

        "blink_count":
            row.get(
                "blink_count"
            )
            or
            0,

        "long_eye_closure_count":
            row.get(
                "long_eye_closure_count"
            )
            or
            0,

        "drowsiness_event_count":
            row.get(
                "drowsiness_event_count"
            )
            or
            0,

        "yawn_count":
            row.get(
                "yawn_count"
            )
            or
            0,

        "distraction_event_count":
            row.get(
                "distraction_event_count"
            )
            or
            0,

        "total_safety_alerts":
            row.get(
                "total_safety_alerts"
            )
            or
            0,

        "head_direction_percent":
            row.get(
                "head_direction_percent"
            )
            or
            {},
    })

    return result


def _history_item(
    row,
):

    return {
        "session_id":
            row.get(
                "id"
            ),

        "start_timestamp_utc":
            row.get(
                "started_at"
            ),

        "end_timestamp_utc":
            row.get(
                "ended_at"
            ),

        "drive_duration_seconds":
            row.get(
                "duration_seconds"
            )
            or
            0,

        "attentive_percent":
            row.get(
                "attentive_percent"
            )
            or
            0,

        "head_away_percent":
            row.get(
                "head_away_percent"
            )
            or
            0,

        "confirmed_distraction_percent":
            row.get(
                "confirmed_distraction_percent"
            )
            or
            0,

        "drowsiness_event_count":
            row.get(
                "drowsiness_event_count"
            )
            or
            0,

        "distraction_event_count":
            row.get(
                "distraction_event_count"
            )
            or
            0,

        "total_safety_alerts":
            row.get(
                "total_safety_alerts"
            )
            or
            0,
    }


# =========================================================
# LIVE DATABASE PERSISTENCE
# =========================================================

def _event_key(
    event,
):

    return (
        round(
            float(
                event.get(
                    "elapsed_seconds",
                    0,
                )
                or
                0
            ),
            2,
        ),

        str(
            event.get(
                "type",
                ""
            )
        ),

        str(
            event.get(
                "message",
                ""
            )
        ),
    )


def _persist_new_events_sync(
    *,
    access_token,
    user_id,
    db_session_id,
    events,
):
    """
    Persist only events that have not already been written.
    """

    if not db_session_id:
        return

    with _USER_LOCK:

        saved = (
            _USER_SAVED_EVENT_KEYS
            .setdefault(
                user_id,
                set(),
            )
        )

    for event in (
        events
        or
        []
    ):

        key = _event_key(
            event
        )

        with _USER_LOCK:

            if key in saved:
                continue

        try:

            insert_drive_event(
                access_token=
                    access_token,

                session_id=
                    db_session_id,

                user_id=
                    user_id,

                elapsed_seconds=
                    event.get(
                        "elapsed_seconds",
                        0,
                    ),

                event_type=
                    event.get(
                        "type",
                        "EVENT",
                    ),

                message=
                    event.get(
                        "message",
                    ),
            )

            with _USER_LOCK:
                saved.add(
                    key
                )

        except Exception as error:

            print(
                "NINO Supabase event warning:",
                error,
            )


def _persist_sample_sync(
    *,
    access_token,
    user_id,
    db_session_id,
    state,
):

    if not db_session_id:
        return

    try:

        insert_drive_sample(
            access_token=
                access_token,

            session_id=
                db_session_id,

            user_id=
                user_id,

            state=
                state,
        )

    except Exception as error:

        print(
            "NINO Supabase sample warning:",
            error,
        )


def _flush_drive_state_sync(
    *,
    access_token,
    user_id,
    service,
):
    """
    Persist the final events/state just before completing the
    database session.
    """

    with _USER_LOCK:

        db_session_id = (
            _USER_DB_SESSION_IDS.get(
                user_id
            )
        )

    if not db_session_id:
        return

    state = (
        service.get_state()
    )

    _persist_new_events_sync(
        access_token=
            access_token,

        user_id=
            user_id,

        db_session_id=
            db_session_id,

        events=
            state.get(
                "events",
                []
            ),
    )

    _persist_sample_sync(
        access_token=
            access_token,

        user_id=
            user_id,

        db_session_id=
            db_session_id,

        state=
            state,
    )


# =========================================================
# ROOT / HEALTH
# =========================================================

@app.get("/")
def root():

    return {
        "system":
            "NINO",

        "status":
            "online",

        "version":
            app.version,

        "authentication":
            "Supabase Auth",

        "database":
            "Supabase PostgreSQL",

        "architecture":
            (
                "Browser camera + "
                "WebSocket AI inference"
            ),
    }


@app.get("/health")
def health():

    with _USER_LOCK:

        active_runtimes = len(
            _USER_SERVICES
        )

        active_drives = sum(
            1
            for service
            in _USER_SERVICES.values()
            if service.drive_active
        )

    return {
        "status":
            "ok",

        "system":
            "NINO",

        "version":
            app.version,

        "database":
            "Supabase PostgreSQL",

        "active_user_runtimes":
            active_runtimes,

        "active_drives":
            active_drives,
    }


# =========================================================
# AUTH
# =========================================================

@app.get("/api/auth/me")
def current_user(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    user, _ = (
        _require_user_and_token(
            authorization
        )
    )

    return _public_user(
        user
    )


@app.post("/api/auth/logout")
def backend_logout_cleanup(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    user, token = (
        _require_user_and_token(
            authorization
        )
    )

    user_id = str(
        user["id"]
    )

    drive_summary = None

    with _USER_LOCK:

        service = (
            _USER_SERVICES.get(
                user_id
            )
        )

        db_session_id = (
            _USER_DB_SESSION_IDS.get(
                user_id
            )
        )

    if service is not None:

        if service.drive_active:

            try:

                result = (
                    service.end_drive()
                )

                drive_summary = (
                    result.get(
                        "summary"
                    )
                    or
                    {}
                )

                _flush_drive_state_sync(
                    access_token=
                        token,

                    user_id=
                        user_id,

                    service=
                        service,
                )

                if db_session_id:

                    finish_drive_session(
                        access_token=
                            token,

                        session_id=
                            db_session_id,

                        user_id=
                            user_id,

                        summary=
                            drive_summary,
                    )

            except Exception as error:

                print(
                    "NINO logout drive cleanup warning:",
                    error,
                )

        _remove_user_runtime(
            user_id
        )

    return {
        "status":
            "backend_cleanup_complete",

        "drive_summary":
            drive_summary,
    }


# =========================================================
# DRIVE START
# =========================================================

@app.post("/api/drive/start")
def start_drive(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    user, token = (
        _require_user_and_token(
            authorization
        )
    )

    user_id = str(
        user["id"]
    )

    service = _get_user_service(
        user_id
    )

    if service.drive_active:

        with _USER_LOCK:
            db_session_id = (
                _USER_DB_SESSION_IDS.get(
                    user_id
                )
            )

        return {
            "status":
                "already_active",

            "session_id":
                db_session_id,

            "user_id":
                user_id,
        }

    # Start local analytics/logger first.
    local_result = (
        service.start_drive()
    )

    try:

        db_row = (
            create_drive_session(
                access_token=
                    token,

                user_id=
                    user_id,
            )
        )

    except Exception as error:

        # Avoid leaving a local drive running when the DB
        # session could not be created.
        try:
            service.end_drive()
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=(
                "Drive could not be created "
                f"in Supabase: {error}"
            ),
        ) from error

    db_session_id = str(
        db_row["id"]
    )

    with _USER_LOCK:

        _USER_DB_SESSION_IDS[
            user_id
        ] = db_session_id

        _USER_LAST_SAMPLE_AT[
            user_id
        ] = 0.0

        _USER_SAVED_EVENT_KEYS[
            user_id
        ] = set()

    return {
        "status":
            local_result.get(
                "status",
                "started",
            ),

        # Public session ID is now the Supabase UUID.
        "session_id":
            db_session_id,

        "user_id":
            user_id,
    }


# =========================================================
# DRIVE END
# =========================================================

@app.post("/api/drive/end")
def end_drive(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    user, token = (
        _require_user_and_token(
            authorization
        )
    )

    user_id = str(
        user["id"]
    )

    service = _get_user_service(
        user_id
    )

    with _USER_LOCK:

        db_session_id = (
            _USER_DB_SESSION_IDS.get(
                user_id
            )
        )

    if not service.drive_active:

        return {
            "status":
                "not_active",

            "summary":
                None,
        }

    try:

        result = (
            service.end_drive()
        )

        summary = (
            result.get(
                "summary"
            )
            or
            {}
        )

        # Save the final event(s) and sample.
        _flush_drive_state_sync(
            access_token=
                token,

            user_id=
                user_id,

            service=
                service,
        )

        db_row = None

        if db_session_id:

            db_row = (
                finish_drive_session(
                    access_token=
                        token,

                    session_id=
                        db_session_id,

                    user_id=
                        user_id,

                    summary=
                        summary,
                )
            )

        with _USER_LOCK:

            _USER_DB_SESSION_IDS.pop(
                user_id,
                None,
            )

            _USER_LAST_SAMPLE_AT.pop(
                user_id,
                None,
            )

            _USER_SAVED_EVENT_KEYS.pop(
                user_id,
                None,
            )

        public_summary = (
            _session_row_to_summary(
                db_row
            )
            if db_row
            else
            summary
        )

        return {
            "status":
                "ended",

            "session_id":
                db_session_id,

            "summary":
                public_summary,

            # Local CSV/JSON remain available as a backup.
            "local_csv_path":
                result.get(
                    "csv_path"
                ),

            "local_summary_path":
                result.get(
                    "summary_path"
                ),
        }

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


# =========================================================
# MONITOR STATE / STATUS
# =========================================================

@app.get("/api/monitor/state")
def monitor_state(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    user, _ = (
        _require_user_and_token(
            authorization
        )
    )

    user_id = str(
        user["id"]
    )

    service = _get_user_service(
        user_id
    )

    state = (
        service.get_state()
    )

    with _USER_LOCK:

        db_session_id = (
            _USER_DB_SESSION_IDS.get(
                user_id
            )
        )

    # Do not expose the local CSV logger session ID to React.
    state[
        "session_id"
    ] = db_session_id

    return state


@app.get("/api/monitor/status")
def monitor_status(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    user, _ = (
        _require_user_and_token(
            authorization
        )
    )

    user_id = str(
        user["id"]
    )

    with _USER_LOCK:

        service = (
            _USER_SERVICES.get(
                user_id
            )
        )

        db_session_id = (
            _USER_DB_SESSION_IDS.get(
                user_id
            )
        )

    if service is None:

        return {
            "connected":
                False,

            "drive_active":
                False,

            "session_id":
                None,
        }

    state = (
        service.get_state()
    )

    return {
        "connected":
            bool(
                state.get(
                    "connected",
                    False,
                )
            ),

        "drive_active":
            service.drive_active,

        "session_id":
            db_session_id,
    }


@app.post("/api/monitor/start")
def legacy_monitor_start(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    _require_user_and_token(
        authorization
    )

    return {
        "status":
            "browser_camera_required",

        "message":
            (
                "Camera is controlled by "
                "the browser using getUserMedia()."
            ),
    }


@app.post("/api/monitor/stop")
def legacy_monitor_stop(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    _require_user_and_token(
        authorization
    )

    return {
        "status":
            "browser_camera_required",

        "message":
            (
                "Browser camera must be stopped "
                "from the frontend."
            ),
    }


# =========================================================
# WEBSOCKET LIVE INFERENCE + DATABASE TELEMETRY
# =========================================================

@app.websocket("/ws/live")
async def live_websocket(
    websocket: WebSocket,

    token:
        str
        =
        Query(
            default=""
        ),
):

    try:

        user = await asyncio.to_thread(
            verify_access_token,
            token,
        )

    except Exception:

        await websocket.close(
            code=1008,
            reason=(
                "Supabase authentication required"
            ),
        )

        return

    user_id = str(
        user["id"]
    )

    service = _get_user_service(
        user_id
    )

    await websocket.accept()

    print(
        "NINO WebSocket connected:",
        user_id,
    )

    try:

        while True:

            jpeg_bytes = (
                await websocket
                .receive_bytes()
            )

            state = (
                await asyncio.to_thread(
                    service.process_jpeg,
                    jpeg_bytes,
                )
            )

            with _USER_LOCK:

                db_session_id = (
                    _USER_DB_SESSION_IDS.get(
                        user_id
                    )
                )

                last_sample_at = (
                    _USER_LAST_SAMPLE_AT.get(
                        user_id,
                        0.0,
                    )
                )

            # Replace local logger ID with the public DB UUID.
            state[
                "session_id"
            ] = db_session_id

            # -------------------------------------------------
            # DATABASE WRITES ONLY DURING AN ACTIVE DRIVE
            # -------------------------------------------------

            if (
                service.drive_active
                and
                db_session_id
            ):

                # Save newly-created timeline events.
                events = (
                    state.get(
                        "events",
                        []
                    )
                )

                await asyncio.to_thread(
                    _persist_new_events_sync,

                    access_token=
                        token,

                    user_id=
                        user_id,

                    db_session_id=
                        db_session_id,

                    events=
                        events,
                )

                # Store telemetry around once per second,
                # not every WebSocket/inference frame.
                now = time.monotonic()

                if (
                    now
                    -
                    last_sample_at
                    >=
                    SAMPLE_INTERVAL_SECONDS
                ):

                    with _USER_LOCK:

                        _USER_LAST_SAMPLE_AT[
                            user_id
                        ] = now

                    await asyncio.to_thread(
                        _persist_sample_sync,

                        access_token=
                            token,

                        user_id=
                            user_id,

                        db_session_id=
                            db_session_id,

                        state=
                            state,
                    )

            await websocket.send_json(
                state
            )

    except WebSocketDisconnect:

        print(
            "NINO WebSocket disconnected:",
            user_id,
        )

    except Exception as error:

        print(
            "NINO WebSocket error:",
            user_id,
            error,
        )

        try:

            await websocket.send_json({
                "error":
                    str(
                        error
                    ),
            })

        except Exception:
            pass

        try:

            await websocket.close(
                code=1011
            )

        except Exception:
            pass


# =========================================================
# ML MODEL INFO
# =========================================================

@app.get("/api/model/info")
def model_information(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    _require_user_and_token(
        authorization
    )

    evaluation = (
        load_model_evaluation()
    )

    return {
        "model":
            "Random Forest Classifier",

        "task":
            "Head-direction classification",

        "representation":
            "ALIGNED_XYZ",

        "feature_count":
            evaluation.get(
                "feature_count",
                36,
            ),

        "classes":
            evaluation.get(
                "classes",
                [
                    "FORWARD",
                    "LEFT",
                    "RIGHT",
                    "UP",
                    "DOWN",
                ],
            ),

        "training_samples":
            evaluation.get(
                "samples",
                1322,
            ),

        "training_sessions":
            3,

        "cross_session_accuracy":
            evaluation.get(
                "cross_session_accuracy",
                0.8596,
            ),

        "macro_f1":
            evaluation.get(
                "cross_session_macro_f1",
                0.8415,
            ),

        "session_accuracy_std":
            evaluation.get(
                "cross_session_accuracy_std",
                0.0744,
            ),

        "controlled_live_validation":
            "5/5",

        "pipeline": [
            "MediaPipe Face Landmarks",
            "Face translation normalization",
            "Inter-eye scale normalization",
            "Eye-line rotation alignment",
            "36 ALIGNED_XYZ features",
            "Random Forest classification",
        ],

        # =============================================
        # REAL MODEL EVALUATION ARTIFACTS
        # =============================================

        "evaluation_available":
            evaluation.get(
                "available",
                False,
            ),

        "confusion_matrix":
            evaluation.get(
                "confusion_matrix",
                [],
            ),

        "per_class":
            evaluation.get(
                "per_class",
                {},
            ),

        "feature_importance":
            evaluation.get(
                "top_feature_importance",
                [],
            ),

        "full_dataset_accuracy":
            evaluation.get(
                "full_dataset_accuracy",
            ),

        "evaluation_note":
            evaluation.get(
                "note",
                "",
            ),

        "validation_note":
            (
                "Cross-session validation used three "
                "controlled collection sessions. "
                "The classifier has not yet been "
                "validated on unseen individuals."
            ),
    }

# =========================================================
# SUPABASE DRIVE HISTORY
# =========================================================

@app.get("/api/sessions")
def sessions(
    authorization:
        str | None
        =
        Header(
            default=None
        ),

    limit:
        int
        =
        Query(
            default=50,
            ge=1,
            le=100,
        ),

    offset:
        int
        =
        Query(
            default=0,
            ge=0,
        ),
):

    _, token = (
        _require_user_and_token(
            authorization
        )
    )

    try:

        rows = (
            list_drive_sessions(
                access_token=
                    token,

                limit=
                    limit,

                offset=
                    offset,
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    # Exclude incomplete/orphan rows from normal history.
    completed_rows = [
        row
        for row
        in rows
        if row.get(
            "ended_at"
        )
    ]

    items = [
        _history_item(
            row
        )
        for row
        in completed_rows
    ]

    return {
        "count":
            len(
                items
            ),

        "sessions":
            items,
    }


@app.get("/api/sessions/latest")
def latest_session(
    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    _, token = (
        _require_user_and_token(
            authorization
        )
    )

    try:

        rows = (
            list_drive_sessions(
                access_token=
                    token,

                limit=25,

                offset=0,
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    completed = [
        row
        for row
        in rows
        if row.get(
            "ended_at"
        )
    ]

    if not completed:

        raise HTTPException(
            status_code=404,
            detail=(
                "No completed drive session found."
            ),
        )

    return (
        _session_row_to_summary(
            completed[0]
        )
    )


@app.get("/api/sessions/{session_id}")
def session_detail(
    session_id: str,

    authorization:
        str | None
        =
        Header(
            default=None
        ),
):

    _, token = (
        _require_user_and_token(
            authorization
        )
    )

    try:

        row = (
            get_drive_session(
                access_token=
                    token,

                session_id=
                    session_id,
            )
        )

        if not row:

            raise HTTPException(
                status_code=404,
                detail=(
                    "Drive session not found."
                ),
            )

        events = (
            list_drive_events(
                access_token=
                    token,

                session_id=
                    session_id,
            )
        )

        samples = (
            list_drive_samples(
                access_token=
                    token,

                session_id=
                    session_id,

                limit=1500,
            )
        )

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error

    summary = (
        _session_row_to_summary(
            row
        )
    )

    insights = (
        compute_drive_insights(
            summary=
                summary,

            samples=
                samples,

            events=
                events,
        )
    )

    return {
        "summary":
            summary,

        "events":
            events,

        "samples":
            samples,

        "insights":
            insights,
    }


# =========================================================
# SHUTDOWN
# =========================================================

@app.on_event("shutdown")
def shutdown_event():

    with _USER_LOCK:

        services = list(
            _USER_SERVICES.values()
        )

        _USER_SERVICES.clear()

        _USER_DB_SESSION_IDS.clear()

        _USER_LAST_SAMPLE_AT.clear()

        _USER_SAVED_EVENT_KEYS.clear()

    for service in services:

        try:
            service.close()

        except Exception as error:
            print(
                "NINO shutdown warning:",
                error,
            )
