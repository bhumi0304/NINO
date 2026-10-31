import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp

from backend.alerts.alert_manager import (
    SafetyAlertManager,
)

from backend.analytics.session_analyzer import (
    DriveSessionAnalyzer,
)

from backend.data.session_logger import (
    DriveSessionLogger,
)

from backend.pipeline.driver_monitor import (
    DriverMonitor,
)


# =========================================================
# PROJECT PATHS
# =========================================================

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

FACE_LANDMARKER_MODEL = (
    PROJECT_ROOT
    / "models"
    / "mediapipe"
    / "face_landmarker.task"
)


# =========================================================
# MONITOR SERVICE
# =========================================================

class MonitorService:
    """
    Central live-camera service for the NINO web app.

    Responsibilities
    ----------------
    - Open webcam
    - Run MediaPipe Face Landmarker
    - Run DriverMonitor
    - Run SafetyAlertManager
    - Provide live JPEG frames to FastAPI
    - Provide live driver-state JSON
    - Start/end drive sessions
    - Log CSV telemetry
    - Generate session analytics automatically

    Important
    ---------
    The browser will display the camera stream.

    We therefore do NOT open an OpenCV cv2.imshow()
    window here.
    """

    def __init__(self):

        self.lock = threading.RLock()

        self.thread = None

        self.running = False

        self.camera = None

        self.latest_jpeg = None

        self.driver_monitor = None

        self.alert_manager = None

        self.session_logger = (
            DriveSessionLogger(
                sample_interval_seconds=0.2
            )
        )

        self.drive_active = False

        self.last_completed_summary = None

        self.latest_state = (
            self._empty_state()
        )

    # =====================================================
    # EMPTY LIVE STATE
    # =====================================================

    @staticmethod
    def _empty_state():

        return {
            "monitor_running": False,

            "drive_active": False,

            "session_id": None,

            # ---------------------------------------------
            # FACE
            # ---------------------------------------------

            "face_detected": False,

            # ---------------------------------------------
            # EYES
            # ---------------------------------------------

            "ear": None,

            "left_ear": None,

            "right_ear": None,

            "eye_state": "UNKNOWN",

            "eye_closed_duration": 0.0,

            "eye_event": None,

            "is_drowsy": False,

            "blink_count": 0,

            "long_eye_closure_count": 0,

            "drowsiness_event_count": 0,

            # ---------------------------------------------
            # MOUTH
            # ---------------------------------------------

            "mar": None,

            "mouth_state": "UNKNOWN",

            "mouth_open_duration": 0.0,

            "mouth_event": None,

            "mouth_movement_count": 0,

            "yawn_count": 0,

            # ---------------------------------------------
            # HEAD ML
            # ---------------------------------------------

            "head_direction_raw": "UNKNOWN",

            "head_direction_raw_confidence": None,

            "head_direction": "UNKNOWN",

            "head_direction_confidence": None,

            "head_direction_probabilities": {},

            # ---------------------------------------------
            # DISTRACTION
            # ---------------------------------------------

            "distraction_state": "UNKNOWN",

            "distraction_duration": 0.0,

            "distraction_event_count": 0,

            # ---------------------------------------------
            # ALERT
            # ---------------------------------------------

            "alert_state": "NORMAL",

            # ---------------------------------------------
            # ERROR
            # ---------------------------------------------

            "error": None,
        }

    # =====================================================
    # CREATE FRESH DETECTION PIPELINE
    # =====================================================

    @staticmethod
    def _create_detection_stack():

        monitor = DriverMonitor(
            fps=30,

            calibration_frames=30,

            drowsiness_duration=0.9,

            head_smoothing_frames=3,
        )

        alerts = (
            SafetyAlertManager()
        )

        return monitor, alerts

    # =====================================================
    # STATUS
    # =====================================================

    def is_running(self):

        with self.lock:

            return self.running

    def is_drive_active(self):

        with self.lock:

            return self.drive_active

    # =====================================================
    # START CAMERA MONITOR
    # =====================================================

    def start_monitor(self):
        """
        Start webcam + AI processing thread.

        This does NOT automatically begin a logged drive.
        """

        with self.lock:

            if self.running:

                return {
                    "status":
                        "already_running",

                    "running":
                        True,
                }

            if not (
                FACE_LANDMARKER_MODEL.exists()
            ):

                raise FileNotFoundError(
                    "MediaPipe model not found: "
                    f"{FACE_LANDMARKER_MODEL}"
                )

            (
                self.driver_monitor,
                self.alert_manager,
            ) = (
                self._create_detection_stack()
            )

            self.latest_state = (
                self._empty_state()
            )

            self.latest_jpeg = None

            self.running = True

            self.thread = (
                threading.Thread(
                    target=self._camera_loop,

                    daemon=True,

                    name="nino-camera-thread",
                )
            )

            self.thread.start()

        return {
            "status": "started",
            "running": True,
        }

    # =====================================================
    # STOP CAMERA MONITOR
    # =====================================================

    def stop_monitor(self):
        """
        Stop webcam processing.

        If a drive is active, safely end and analyze it.
        """

        summary = None

        if self.is_drive_active():

            result = self.end_drive()

            summary = result.get(
                "summary"
            )

        with self.lock:

            self.running = False

            thread = self.thread

        if (
            thread is not None
            and
            thread.is_alive()
        ):

            thread.join(
                timeout=3.0
            )

        with self.lock:

            self.thread = None

            self.latest_jpeg = None

            self.latest_state[
                "monitor_running"
            ] = False

        return {
            "status": "stopped",

            "running": False,

            "summary": summary,
        }

    # =====================================================
    # START DRIVE SESSION
    # =====================================================

    def start_drive(self):
        """
        Start camera if needed, then begin drive logging.

        This is what the React "Start Drive" button calls.
        """

        if not self.is_running():

            self.start_monitor()

            # Give camera thread a short moment
            # to initialize.
            deadline = (
                time.monotonic()
                +
                3.0
            )

            while (
                time.monotonic()
                <
                deadline
            ):

                with self.lock:

                    if (
                        self.camera
                        is not None
                    ):

                        break

                    error = (
                        self.latest_state.get(
                            "error"
                        )
                    )

                if error:

                    raise RuntimeError(
                        error
                    )

                time.sleep(
                    0.05
                )

        with self.lock:

            if self.drive_active:

                return {
                    "status":
                        "already_active",

                    "session_id":
                        self.session_logger
                        .session_id,
                }

            # Reset counters / temporal state
            # for each new drive.
            (
                self.driver_monitor,
                self.alert_manager,
            ) = (
                self._create_detection_stack()
            )

            session_id = (
                self.session_logger
                .start_session()
            )

            self.drive_active = True

            self.latest_state[
                "drive_active"
            ] = True

            self.latest_state[
                "session_id"
            ] = session_id

        return {
            "status": "started",

            "session_id":
                session_id,
        }

    # =====================================================
    # END DRIVE SESSION
    # =====================================================

    def end_drive(self):
        """
        Stop logging and automatically generate
        drive analytics JSON.
        """

        with self.lock:

            if not self.drive_active:

                return {
                    "status":
                        "not_active",

                    "summary":
                        self.last_completed_summary,
                }

            self.drive_active = False

            self.latest_state[
                "drive_active"
            ] = False

            csv_path = (
                self.session_logger
                .end_session()
            )

        summary = None

        summary_path = None

        if csv_path is not None:

            analyzer = (
                DriveSessionAnalyzer(
                    csv_path
                )
            )

            summary = (
                analyzer.analyze()
            )

            summary_path = (
                analyzer.save_summary(
                    summary
                )
            )

        with self.lock:

            self.last_completed_summary = (
                summary
            )

            self.latest_state[
                "session_id"
            ] = None

        return {
            "status": "ended",

            "csv_path":
                str(csv_path)
                if csv_path
                else None,

            "summary_path":
                str(summary_path)
                if summary_path
                else None,

            "summary":
                summary,
        }

    # =====================================================
    # LIVE STATE FOR REACT
    # =====================================================

    def get_state(self):

        with self.lock:

            state = dict(
                self.latest_state
            )

            state[
                "monitor_running"
            ] = self.running

            state[
                "drive_active"
            ] = self.drive_active

            if self.drive_active:

                state[
                    "session_id"
                ] = (
                    self.session_logger
                    .session_id
                )

            else:

                state[
                    "session_id"
                ] = None

            return state

    # =====================================================
    # MJPEG STREAM
    # =====================================================

    def frame_generator(self):
        """
        Yield JPEG frames for:

        /api/monitor/stream
        """

        while True:

            with self.lock:

                running = (
                    self.running
                )

                jpeg = (
                    self.latest_jpeg
                )

            if not running:

                break

            if jpeg is None:

                time.sleep(
                    0.03
                )

                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                +
                jpeg
                +
                b"\r\n"
            )

            time.sleep(
                0.03
            )

    # =====================================================
    # CAMERA / AI LOOP
    # =====================================================

    def _camera_loop(self):

        camera = None

        try:

            # =================================================
            # MEDIAPIPE SETUP
            # =================================================

            BaseOptions = (
                mp.tasks.BaseOptions
            )

            FaceLandmarker = (
                mp.tasks.vision
                .FaceLandmarker
            )

            FaceLandmarkerOptions = (
                mp.tasks.vision
                .FaceLandmarkerOptions
            )

            RunningMode = (
                mp.tasks.vision
                .RunningMode
            )

            options = (
                FaceLandmarkerOptions(
                    base_options=
                        BaseOptions(
                            model_asset_path=
                                str(
                                    FACE_LANDMARKER_MODEL
                                )
                        ),

                    running_mode=
                        RunningMode.VIDEO,

                    num_faces=1,

                    min_face_detection_confidence=
                        0.5,

                    min_face_presence_confidence=
                        0.5,

                    min_tracking_confidence=
                        0.5,
                )
            )

            # =================================================
            # CAMERA
            # =================================================

            if hasattr(
                cv2,
                "CAP_DSHOW",
            ):

                camera = (
                    cv2.VideoCapture(
                        0,
                        cv2.CAP_DSHOW,
                    )
                )

            else:

                camera = (
                    cv2.VideoCapture(
                        0
                    )
                )

            camera.set(
                cv2.CAP_PROP_FRAME_WIDTH,
                960,
            )

            camera.set(
                cv2.CAP_PROP_FRAME_HEIGHT,
                540,
            )

            if not camera.isOpened():

                raise RuntimeError(
                    "Could not open webcam. "
                    "Close any other program using the camera."
                )

            with self.lock:

                self.camera = camera

            started_at = (
                time.monotonic()
            )

            last_timestamp_ms = -1

            # =================================================
            # FACE LANDMARKER LOOP
            # =================================================

            with (
                FaceLandmarker
                .create_from_options(
                    options
                )
            ) as landmarker:

                while True:

                    with self.lock:

                        if not self.running:

                            break

                        monitor = (
                            self.driver_monitor
                        )

                        alert_manager = (
                            self.alert_manager
                        )

                    success, frame = (
                        camera.read()
                    )

                    if not success:

                        time.sleep(
                            0.02
                        )

                        continue

                    # Same orientation used during
                    # ML collection and validation.
                    frame = cv2.flip(
                        frame,
                        1,
                    )

                    (
                        height,
                        width,
                        _,
                    ) = frame.shape

                    # -----------------------------------------
                    # MediaPipe input
                    # -----------------------------------------

                    rgb_frame = (
                        cv2.cvtColor(
                            frame,
                            cv2.COLOR_BGR2RGB,
                        )
                    )

                    mp_image = (
                        mp.Image(
                            image_format=
                                mp.ImageFormat.SRGB,

                            data=
                                rgb_frame,
                        )
                    )

                    timestamp_ms = int(
                        (
                            time.monotonic()
                            -
                            started_at
                        )
                        *
                        1000
                    )

                    # detect_for_video requires
                    # monotonically increasing timestamps.
                    timestamp_ms = max(
                        timestamp_ms,
                        last_timestamp_ms
                        +
                        1,
                    )

                    last_timestamp_ms = (
                        timestamp_ms
                    )

                    result = (
                        landmarker
                        .detect_for_video(
                            mp_image,
                            timestamp_ms,
                        )
                    )

                    # -----------------------------------------
                    # DriverMonitor
                    # -----------------------------------------

                    if (
                        result.face_landmarks
                    ):

                        driver_data = (
                            monitor.update(
                                result
                                .face_landmarks[0],

                                width,
                                height,
                            )
                        )

                    else:

                        driver_data = (
                            monitor.update(
                                None,
                                width,
                                height,
                            )
                        )

                    # -----------------------------------------
                    # Safety alerts
                    # -----------------------------------------

                    alert_state = (
                        alert_manager.update(
                            driver_data
                        )
                    )

                    # -----------------------------------------
                    # Session logging
                    # -----------------------------------------

                    with self.lock:

                        current_drive_active = (
                            self.drive_active
                        )

                        if (
                            current_drive_active
                            and
                            self.session_logger
                            .active
                        ):

                            self.session_logger.log(
                                driver_data,
                                alert_state,
                            )

                    # -----------------------------------------
                    # React live-state object
                    # -----------------------------------------

                    state = dict(
                        driver_data
                    )

                    state[
                        "alert_state"
                    ] = alert_state

                    state[
                        "monitor_running"
                    ] = True

                    state[
                        "drive_active"
                    ] = (
                        current_drive_active
                    )

                    state[
                        "session_id"
                    ] = (
                        self.session_logger
                        .session_id
                        if current_drive_active
                        else None
                    )

                    state[
                        "error"
                    ] = None

                    # =================================================
                    # SMALL CAMERA OVERLAY
                    # =================================================

                    cv2.rectangle(
                        frame,
                        (0, 0),
                        (width, 42),
                        (12, 27, 22),
                        -1,
                    )

                    cv2.putText(
                        frame,
                        "NINO  |  LIVE DRIVER MONITOR",

                        (16, 28),

                        cv2.FONT_HERSHEY_SIMPLEX,

                        0.62,

                        (255, 255, 255),

                        2,
                    )

                    direction = (
                        state.get(
                            "head_direction",
                            "UNKNOWN",
                        )
                    )

                    confidence = (
                        state.get(
                            "head_direction_confidence"
                        )
                    )

                    if confidence is None:

                        confidence_text = (
                            "N/A"
                        )

                    else:

                        confidence_text = (
                            f"{confidence * 100:.0f}%"
                        )

                    cv2.putText(
                        frame,

                        (
                            f"Head: {direction}"
                            f"  |  RF: "
                            f"{confidence_text}"
                        ),

                        (
                            16,
                            height - 48,
                        ),

                        cv2.FONT_HERSHEY_SIMPLEX,

                        0.58,

                        (255, 255, 255),

                        2,
                    )

                    current_alert = str(
                        state.get(
                            "alert_state",
                            "NORMAL",
                        )
                    )

                    dangerous = (
                        "ALERT"
                        in current_alert
                        or
                        "DROWSINESS"
                        in current_alert
                        or
                        "DISTRACTED"
                        in current_alert
                    )

                    alert_color = (
                        (0, 0, 255)
                        if dangerous
                        else
                        (0, 255, 0)
                    )

                    cv2.putText(
                        frame,

                        (
                            "Safety: "
                            f"{current_alert}"
                        ),

                        (
                            16,
                            height - 18,
                        ),

                        cv2.FONT_HERSHEY_SIMPLEX,

                        0.58,

                        alert_color,

                        2,
                    )

                    # =================================================
                    # JPEG ENCODING
                    # =================================================

                    encoded, jpeg = (
                        cv2.imencode(
                            ".jpg",

                            frame,

                            [
                                int(
                                    cv2.IMWRITE_JPEG_QUALITY
                                ),
                                82,
                            ],
                        )
                    )

                    if encoded:

                        with self.lock:

                            self.latest_jpeg = (
                                jpeg.tobytes()
                            )

                            self.latest_state = (
                                state
                            )

        # =====================================================
        # CAMERA ERROR
        # =====================================================

        except Exception as error:

            print()
            print(
                "NINO Monitor Service Error:"
            )

            print(
                error
            )

            with self.lock:

                self.latest_state = (
                    self._empty_state()
                )

                self.latest_state[
                    "error"
                ] = str(
                    error
                )

                self.running = False

        # =====================================================
        # CLEANUP
        # =====================================================

        finally:

            if camera is not None:

                camera.release()

            with self.lock:

                self.camera = None

                self.running = False

                self.latest_state[
                    "monitor_running"
                ] = False