
import time
import threading
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from backend.features.alerts.alert_manager import SafetyAlertManager
from backend.analytics.session_analyzer import DriveSessionAnalyzer
from backend.data.session_logger import DriveSessionLogger
from backend.pipeline.driver_monitor import DriverMonitor


PROJECT_ROOT = Path(__file__).resolve().parents[2]

FACE_LANDMARKER_MODEL = (
    PROJECT_ROOT
    / "models"
    / "mediapipe"
    / "face_landmarker.task"
)


OVERLAY_GROUPS = {
    "left_eye": [
        33, 246, 161, 160, 159, 158, 157, 173,
        133, 155, 154, 153, 145, 144, 163, 7,
    ],
    "right_eye": [
        362, 398, 384, 385, 386, 387, 388, 466,
        263, 249, 390, 373, 374, 380, 381, 382,
    ],
    "mouth": [
        61, 185, 40, 39, 37, 0, 267, 269,
        270, 409, 291, 375, 321, 405, 314,
        17, 84, 181, 91, 146,
    ],
    "nose": [
        168, 6, 197, 195, 5, 4, 1,
    ],
    "face": [
        10, 338, 297, 332, 284, 251, 389,
        356, 454, 323, 361, 288, 397, 365,
        379, 378, 400, 377, 152, 148, 176,
        149, 150, 136, 172, 58, 132, 93,
        234, 127, 162, 21, 54, 103, 67, 109,
    ],
}


class RealtimeMonitorService:
    """
    Browser-camera realtime inference service for NINO.

    Calibration behavior
    --------------------
    - DriverMonitor performs neutral head-pose calibration.
    - While calibration is incomplete:
        * alert_state = CALIBRATING
        * distraction/drowsiness warnings are suppressed
        * safety telemetry is not logged
    - Once calibration completes:
        * normal alerting starts
        * normal drive analytics start
    """

    def __init__(self):
        self.lock = threading.RLock()

        self.landmarker = None
        self.driver_monitor = None
        self.alert_manager = None

        self.session_logger = DriveSessionLogger(
            sample_interval_seconds=0.2
        )

        self.drive_active = False
        self.latest_state = self._empty_state()
        self.last_summary = None

        self.events = deque(maxlen=100)

        self.last_alert_state = None
        self.last_distraction_state = None
        self.last_timestamp_ms = -1

        self.inference_started_at = time.monotonic()

        self.last_processed_at = None
        self.ai_fps_ema = 0.0
        self.inference_ms_ema = 0.0

        self.was_calibrated = False

        self._initialize_pipeline()

    # =====================================================
    # STATE
    # =====================================================

    @staticmethod
    def _empty_state():
        return {
            "connected": False,
            "drive_active": False,
            "session_id": None,

            "face_detected": False,

            "calibrated": False,
            "calibration_progress": 0.0,
            "calibration": {
                "active": False,
                "progress": 0.0,
                "percent": 0,
                "message": "Start a drive to calibrate",
            },

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

            "mar": None,
            "mouth_state": "UNKNOWN",
            "mouth_event": None,
            "yawn_count": 0,

            "head_direction": "UNKNOWN",
            "head_direction_confidence": None,
            "head_direction_probabilities": {},

            "distraction_state": "ATTENTIVE",
            "distraction_duration": 0.0,
            "distraction_event_count": 0,

            "alert_state": "IDLE",

            "events": [],

            "landmark_overlay": {},

            "performance": {
                "ai_fps": 0.0,
                "inference_ms": 0.0,
            },
        }

    # =====================================================
    # PIPELINE
    # =====================================================

    def _new_driver_monitor(self):
        return DriverMonitor(
            fps=30,
            calibration_frames=30,
            drowsiness_duration=0.9,
            head_smoothing_frames=3,
        )

    def _initialize_pipeline(self):
        if not FACE_LANDMARKER_MODEL.exists():
            raise FileNotFoundError(
                f"MediaPipe model not found: {FACE_LANDMARKER_MODEL}"
            )

        self.driver_monitor = self._new_driver_monitor()
        self.alert_manager = SafetyAlertManager()

        if self.landmarker is None:
            BaseOptions = mp.tasks.BaseOptions
            FaceLandmarkerOptions = (
                mp.tasks.vision.FaceLandmarkerOptions
            )
            RunningMode = mp.tasks.vision.RunningMode

            options = FaceLandmarkerOptions(
                base_options=BaseOptions(
                    model_asset_path=str(
                        FACE_LANDMARKER_MODEL
                    )
                ),
                running_mode=RunningMode.VIDEO,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )

            self.landmarker = (
                mp.tasks.vision.FaceLandmarker
                .create_from_options(options)
            )

    def _reset_detection(self):
        self.driver_monitor = self._new_driver_monitor()
        self.alert_manager = SafetyAlertManager()

        self.last_alert_state = None
        self.last_distraction_state = None

        self.events.clear()

        self.last_processed_at = None
        self.ai_fps_ema = 0.0
        self.inference_ms_ema = 0.0

        self.was_calibrated = False

        with self.lock:
            self.latest_state = self._empty_state()

    # =====================================================
    # DRIVE
    # =====================================================

    def start_drive(self):
        with self.lock:
            if self.drive_active:
                return {
                    "status": "already_active",
                    "session_id": self.session_logger.session_id,
                }

            self._reset_detection()

            session_id = self.session_logger.start_session()

            self.drive_active = True

            self.latest_state["drive_active"] = True
            self.latest_state["session_id"] = session_id
            self.latest_state["alert_state"] = "CALIBRATING"
            self.latest_state["calibration"] = {
                "active": True,
                "progress": 0.0,
                "percent": 0,
                "message": (
                    "Look straight ahead and keep your head still"
                ),
            }

            self._add_event(
                "SYSTEM",
                "Drive started",
            )

            self._add_event(
                "CALIBRATION",
                "Neutral-face calibration started",
            )

            return {
                "status": "started",
                "session_id": session_id,
            }

    def end_drive(self):
        with self.lock:
            if not self.drive_active:
                return {
                    "status": "not_active",
                    "summary": self.last_summary,
                }

            self._add_event(
                "SYSTEM",
                "Drive ended",
            )

            self.drive_active = False
            self.latest_state["drive_active"] = False

            csv_path = self.session_logger.end_session()

        summary = None
        summary_path = None

        if csv_path:
            try:
                analyzer = DriveSessionAnalyzer(
                    csv_path
                )

                summary = analyzer.analyze()

                summary_path = analyzer.save_summary(
                    summary
                )

            except Exception as error:
                print(
                    "NINO analytics warning:",
                    error,
                )

        with self.lock:
            self.last_summary = summary

            self.latest_state["session_id"] = None
            self.latest_state["calibration"] = {
                "active": False,
                "progress": 0.0,
                "percent": 0,
                "message": "Start a drive to calibrate",
            }

        return {
            "status": "ended",
            "csv_path": (
                str(csv_path)
                if csv_path
                else None
            ),
            "summary_path": (
                str(summary_path)
                if summary_path
                else None
            ),
            "summary": summary,
        }

    # =====================================================
    # EVENTS
    # =====================================================

    def _current_elapsed(self):
        if (
            self.drive_active
            and
            self.session_logger.session_start_monotonic
            is not None
        ):
            return max(
                0.0,
                time.monotonic()
                -
                self.session_logger.session_start_monotonic,
            )

        return 0.0

    def _add_event(
        self,
        event_type,
        message,
    ):
        self.events.append({
            "elapsed_seconds": round(
                self._current_elapsed(),
                2,
            ),
            "type": event_type,
            "message": message,
        })

    def _update_events(
        self,
        state,
    ):
        eye_event = state.get(
            "eye_event"
        )

        if eye_event:
            self._add_event(
                "EYE",
                str(eye_event).replace(
                    "_",
                    " ",
                ),
            )

        mouth_event = state.get(
            "mouth_event"
        )

        if mouth_event:
            self._add_event(
                "MOUTH",
                str(mouth_event).replace(
                    "_",
                    " ",
                ),
            )

        distraction_state = str(
            state.get(
                "distraction_state",
                "ATTENTIVE",
            )
        )

        if (
            distraction_state
            !=
            self.last_distraction_state
        ):
            if distraction_state.startswith(
                "DISTRACTED_"
            ):
                self._add_event(
                    "DISTRACTION",
                    distraction_state.replace(
                        "_",
                        " ",
                    ),
                )

            elif (
                self.last_distraction_state
                and
                self.last_distraction_state.startswith(
                    "DISTRACTED_"
                )
            ):
                self._add_event(
                    "RECOVERY",
                    "Attention restored",
                )

        self.last_distraction_state = (
            distraction_state
        )

        alert_state = str(
            state.get(
                "alert_state",
                "NORMAL",
            )
        )

        if (
            alert_state
            !=
            self.last_alert_state
            and
            alert_state
            in {
                "EARLY_EYE_WARNING",
                "CRITICAL_DROWSINESS_ALERT",
                "EARLY_DISTRACTION_WARNING",
                "CRITICAL_DISTRACTION_ALERT",
            }
        ):
            self._add_event(
                "ALERT",
                alert_state.replace(
                    "_",
                    " ",
                ),
            )

        self.last_alert_state = (
            alert_state
        )

    # =====================================================
    # LANDMARK OVERLAY
    # =====================================================

    @staticmethod
    def _normalized_point(
        landmark,
    ):
        return {
            "x": round(
                min(
                    1.0,
                    max(
                        0.0,
                        float(
                            landmark.x
                        ),
                    ),
                ),
                5,
            ),
            "y": round(
                min(
                    1.0,
                    max(
                        0.0,
                        float(
                            landmark.y
                        ),
                    ),
                ),
                5,
            ),
        }

    def _build_landmark_overlay(
        self,
        face_landmarks,
    ):
        if not face_landmarks:
            return {}

        overlay = {}
        total = len(face_landmarks)

        for (
            group_name,
            indices,
        ) in OVERLAY_GROUPS.items():

            points = []

            for index in indices:
                if (
                    0
                    <=
                    index
                    <
                    total
                ):
                    points.append(
                        self._normalized_point(
                            face_landmarks[
                                index
                            ]
                        )
                    )

            overlay[group_name] = points

        return overlay

    # =====================================================
    # PERFORMANCE
    # =====================================================

    def _update_performance(
        self,
        started_at,
    ):
        completed_at = time.perf_counter()

        inference_ms = (
            completed_at
            -
            started_at
        ) * 1000.0

        if self.inference_ms_ema <= 0:
            self.inference_ms_ema = (
                inference_ms
            )
        else:
            self.inference_ms_ema = (
                0.85
                *
                self.inference_ms_ema
                +
                0.15
                *
                inference_ms
            )

        now = time.monotonic()

        if self.last_processed_at is not None:
            interval = (
                now
                -
                self.last_processed_at
            )

            if interval > 0:
                instant_fps = min(
                    60.0,
                    max(
                        0.0,
                        1.0 / interval,
                    ),
                )

                if self.ai_fps_ema <= 0:
                    self.ai_fps_ema = (
                        instant_fps
                    )
                else:
                    self.ai_fps_ema = (
                        0.85
                        *
                        self.ai_fps_ema
                        +
                        0.15
                        *
                        instant_fps
                    )

        self.last_processed_at = now

        return {
            "ai_fps": round(
                self.ai_fps_ema,
                1,
            ),
            "inference_ms": round(
                self.inference_ms_ema,
                1,
            ),
        }

    # =====================================================
    # PROCESS ONE BROWSER FRAME
    # =====================================================

    def process_jpeg(
        self,
        jpeg_bytes,
    ):
        processing_started = time.perf_counter()

        if not jpeg_bytes:
            return self.get_state()

        numpy_buffer = np.frombuffer(
            jpeg_bytes,
            dtype=np.uint8,
        )

        frame = cv2.imdecode(
            numpy_buffer,
            cv2.IMREAD_COLOR,
        )

        if frame is None:
            return self.get_state()

        height, width = frame.shape[:2]

        max_width = 640

        if width > max_width:
            scale = max_width / width

            frame = cv2.resize(
                frame,
                (
                    int(
                        width
                        *
                        scale
                    ),
                    int(
                        height
                        *
                        scale
                    ),
                ),
                interpolation=cv2.INTER_AREA,
            )

        height, width = frame.shape[:2]

        rgb_frame = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2RGB,
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_frame,
        )

        timestamp_ms = int(
            (
                time.monotonic()
                -
                self.inference_started_at
            )
            *
            1000
        )

        timestamp_ms = max(
            timestamp_ms,
            self.last_timestamp_ms
            +
            1,
        )

        self.last_timestamp_ms = (
            timestamp_ms
        )

        result = self.landmarker.detect_for_video(
            mp_image,
            timestamp_ms,
        )

        overlay = {}

        if result.face_landmarks:
            face_landmarks = (
                result.face_landmarks[
                    0
                ]
            )

            overlay = (
                self._build_landmark_overlay(
                    face_landmarks
                )
            )

            driver_data = (
                self.driver_monitor.update(
                    face_landmarks,
                    width,
                    height,
                )
            )

        else:
            driver_data = (
                self.driver_monitor.update(
                    None,
                    width,
                    height,
                )
            )

        calibrated = bool(
            driver_data.get(
                "calibrated",
                False,
            )
        )

        calibration_progress = min(
            1.0,
            max(
                0.0,
                float(
                    driver_data.get(
                        "calibration_progress",
                        0.0,
                    )
                    or
                    0.0
                ),
            ),
        )

        if (
            self.drive_active
            and
            not calibrated
        ):
            alert_state = "CALIBRATING"

            driver_data[
                "distraction_state"
            ] = "CALIBRATING"

            driver_data[
                "distraction_duration"
            ] = 0.0

            driver_data[
                "is_drowsy"
            ] = False

        else:
            alert_state = (
                self.alert_manager.update(
                    driver_data
                )
            )

        state = dict(
            driver_data
        )

        state["alert_state"] = (
            alert_state
        )

        state["connected"] = True

        state["drive_active"] = (
            self.drive_active
        )

        state["session_id"] = (
            self.session_logger.session_id
            if self.drive_active
            else None
        )

        state["calibrated"] = (
            calibrated
        )

        state[
            "calibration_progress"
        ] = calibration_progress

        state["calibration"] = {
            "active": bool(
                self.drive_active
                and
                not calibrated
            ),

            "progress": round(
                calibration_progress,
                3,
            ),

            "percent": int(
                round(
                    calibration_progress
                    *
                    100
                )
            ),

            "message": (
                "Look straight ahead and keep your head still"
                if (
                    self.drive_active
                    and
                    not calibrated
                )
                else
                "Calibration complete"
                if calibrated
                else
                "Start a drive to calibrate"
            ),
        }

        if (
            self.drive_active
            and
            calibrated
            and
            not self.was_calibrated
        ):
            self._add_event(
                "CALIBRATION",
                "Neutral-face calibration complete",
            )

        self.was_calibrated = calibrated

        state["landmark_overlay"] = (
            overlay
        )

        state["performance"] = (
            self._update_performance(
                processing_started
            )
        )

        # Calibration frames are deliberately excluded
        # from safety analytics/logging.
        if (
            self.drive_active
            and
            self.session_logger.active
            and
            calibrated
        ):
            self.session_logger.log(
                state,
                alert_state,
            )

            self._update_events(
                state
            )

        state["events"] = list(
            self.events
        )[-25:]

        with self.lock:
            self.latest_state = state

        return state

    # =====================================================
    # CURRENT STATE
    # =====================================================

    def get_state(self):
        with self.lock:
            state = dict(
                self.latest_state
            )

            state["drive_active"] = (
                self.drive_active
            )

            state["session_id"] = (
                self.session_logger.session_id
                if self.drive_active
                else None
            )

            state["events"] = list(
                self.events
            )[-25:]

            # Defensive compatibility: always expose the
            # calibration object.
            if (
                "calibration"
                not in
                state
            ):
                state["calibration"] = {
                    "active": False,
                    "progress": 0.0,
                    "percent": 0,
                    "message": (
                        "Start a drive to calibrate"
                    ),
                }

            return state

    # =====================================================
    # CLEANUP
    # =====================================================

    def close(self):
        if self.drive_active:
            try:
                self.end_drive()
            except Exception:
                pass

        if self.landmarker is not None:
            try:
                self.landmarker.close()
            except Exception:
                pass

            self.landmarker = None
