import csv
import time
import uuid

from datetime import datetime, timezone
from pathlib import Path


class DriveSessionLogger:
    """
    NINO Drive Session Logger

    Purpose
    -------
    Records structured driver-monitoring data during
    an active drive session.

    Logging strategy
    ----------------
    1. Normal telemetry:
       Logged every sample_interval_seconds.

    2. Important events:
       Logged immediately so short events are not lost.

    Examples of immediately logged events:
        - drowsiness warning
        - distraction warning
        - eye event
        - mouth event
        - alert-state change
        - distraction-state change

    Important:
        This file records observations produced by NINO.
        It does NOT create accident-risk labels.
    """

    # =====================================================
    # IMPORTANT ALERTS
    #
    # Support BOTH:
    #
    # Older alert-manager names:
    #     DROWSINESS_ALERT
    #     DISTRACTION_ALERT
    #
    # New multi-stage names:
    #     EARLY_EYE_WARNING
    #     CRITICAL_DROWSINESS_ALERT
    #     EARLY_DISTRACTION_WARNING
    #     CRITICAL_DISTRACTION_ALERT
    # =====================================================

    IMPORTANT_ALERT_STATES = {
        # Older/current compatibility
        "DROWSINESS_ALERT",
        "DISTRACTION_ALERT",

        # New multi-stage alerts
        "EARLY_EYE_WARNING",
        "CRITICAL_DROWSINESS_ALERT",
        "EARLY_DISTRACTION_WARNING",
        "CRITICAL_DISTRACTION_ALERT",
    }

    # =====================================================
    # INITIALIZATION
    # =====================================================

    def __init__(
        self,
        output_directory="data/drive_sessions",
        sample_interval_seconds=0.2,
    ):

        self.output_directory = Path(
            output_directory
        )

        self.output_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        # 0.2 sec = about 5 normal samples/second.
        #
        # Important events bypass this interval and
        # are written immediately.
        self.sample_interval_seconds = (
            sample_interval_seconds
        )

        # -------------------------------------------------
        # Session information
        # -------------------------------------------------

        self.session_id = None

        self.session_start_monotonic = None

        self.session_start_utc = None

        self.last_log_time = None

        self.file_path = None

        self.file = None

        self.writer = None

        self.active = False

        # -------------------------------------------------
        # Previous states
        #
        # Used for transition detection.
        # -------------------------------------------------

        self.previous_alert_state = None

        self.previous_eye_event = None

        self.previous_mouth_event = None

        self.previous_distraction_state = None

        self.previous_face_detected = None

    # =====================================================
    # CSV SCHEMA
    # =====================================================

    @staticmethod
    def _fieldnames():
        """
        Exact column order used by every new NINO
        drive-session CSV.
        """

        return [
            # =============================================
            # SESSION
            # =============================================

            "session_id",
            "timestamp_utc",
            "elapsed_seconds",

            # =============================================
            # FACE
            # =============================================

            "face_detected",

            # =============================================
            # EYES
            # =============================================

            "left_ear",
            "right_ear",
            "ear",

            "eye_state",
            "eye_closed_duration",
            "eye_event",

            "is_drowsy",

            "blink_count",
            "long_eye_closure_count",
            "drowsiness_event_count",

            # =============================================
            # MOUTH
            # =============================================

            "mar",

            "mouth_state",
            "mouth_open_duration",
            "mouth_event",

            "mouth_movement_count",
            "yawn_count",

            # =============================================
            # DIAGNOSTIC HEAD POSE
            # =============================================

            "yaw",
            "pitch",
            "roll",

            "relative_yaw",
            "relative_pitch",

            # =============================================
            # RANDOM FOREST HEAD DIRECTION
            # =============================================

            "head_direction_raw",
            "head_direction_raw_confidence",

            "head_direction",
            "head_direction_confidence",

            # =============================================
            # RANDOM FOREST CLASS PROBABILITIES
            # =============================================

            "prob_forward",
            "prob_left",
            "prob_right",
            "prob_up",
            "prob_down",

            # =============================================
            # DISTRACTION
            # =============================================

            "distraction_state",
            "distraction_duration",
            "distraction_event_count",

            # =============================================
            # SAFETY ALERT
            # =============================================

            "alert_state",

            # =============================================
            # DATA-LOGGING METADATA
            # =============================================

            "log_reason",
        ]

    # =====================================================
    # START DRIVE SESSION
    # =====================================================

    def start_session(self):
        """
        Start a new drive-session CSV.

        Returns
        -------
        str
            Newly generated session ID.
        """

        if self.active:

            raise RuntimeError(
                "A drive session is already active."
            )

        # -------------------------------------------------
        # Generate session ID
        # -------------------------------------------------

        self.session_id = (
            uuid.uuid4().hex[:12]
        )

        # -------------------------------------------------
        # Session time
        # -------------------------------------------------

        self.session_start_monotonic = (
            time.monotonic()
        )

        self.session_start_utc = (
            datetime.now(
                timezone.utc
            )
        )

        self.last_log_time = None

        # -------------------------------------------------
        # Reset state history
        # -------------------------------------------------

        self.previous_alert_state = None

        self.previous_eye_event = None

        self.previous_mouth_event = None

        self.previous_distraction_state = None

        self.previous_face_detected = None

        # -------------------------------------------------
        # File name
        # -------------------------------------------------

        timestamp_string = (
            self.session_start_utc.strftime(
                "%Y%m%d_%H%M%S"
            )
        )

        filename = (
            f"drive_"
            f"{timestamp_string}_"
            f"{self.session_id}.csv"
        )

        self.file_path = (
            self.output_directory
            /
            filename
        )

        # -------------------------------------------------
        # Open file
        # -------------------------------------------------

        self.file = open(
            self.file_path,
            "w",
            newline="",
            encoding="utf-8",
        )

        self.writer = csv.DictWriter(
            self.file,
            fieldnames=self._fieldnames(),
        )

        self.writer.writeheader()

        self.file.flush()

        self.active = True

        print()
        print(
            "Drive session started:"
        )

        print(
            "Session ID:",
            self.session_id,
        )

        print(
            "Log file:",
            self.file_path,
        )

        return self.session_id

    # =====================================================
    # DETECT IMPORTANT CHANGE
    # =====================================================

    def _important_change(
        self,
        monitor_output,
        alert_state,
    ):
        """
        Determine whether the current frame must be written
        immediately.

        Returns
        -------
        tuple

        Example:

            (True, "IMPORTANT_ALERT")

            (False, "PERIODIC_SAMPLE")
        """

        eye_event = (
            monitor_output.get(
                "eye_event"
            )
        )

        mouth_event = (
            monitor_output.get(
                "mouth_event"
            )
        )

        distraction_state = (
            monitor_output.get(
                "distraction_state"
            )
        )

        face_detected = bool(
            monitor_output.get(
                "face_detected",
                False,
            )
        )

        # =================================================
        # 1. IMPORTANT SAFETY ALERT
        # =================================================

        if (
            alert_state
            in self.IMPORTANT_ALERT_STATES
        ):

            return (
                True,
                "IMPORTANT_ALERT",
            )

        # =================================================
        # 2. ALERT STATE CHANGED
        # =================================================

        if (
            self.previous_alert_state
            is not None
            and
            alert_state
            !=
            self.previous_alert_state
        ):

            return (
                True,
                "ALERT_STATE_CHANGE",
            )

        # =================================================
        # 3. EYE EVENT
        #
        # Examples:
        #     BLINK
        #     LONG_CLOSURE
        #     DROWSINESS
        # =================================================

        if eye_event is not None:

            return (
                True,
                "EYE_EVENT",
            )

        # =================================================
        # 4. MOUTH EVENT
        #
        # Examples:
        #     MOUTH_MOVEMENT
        #     POSSIBLE_YAWN
        # =================================================

        if mouth_event is not None:

            return (
                True,
                "MOUTH_EVENT",
            )

        # =================================================
        # 5. DISTRACTION STATE CHANGED
        # =================================================

        if (
            self.previous_distraction_state
            is not None
            and
            distraction_state
            !=
            self.previous_distraction_state
        ):

            return (
                True,
                "DISTRACTION_STATE_CHANGE",
            )

        # =================================================
        # 6. FACE VISIBILITY CHANGED
        #
        # Useful later for detecting:
        #     face disappeared
        #     driver moved outside camera
        #     face returned
        # =================================================

        if (
            self.previous_face_detected
            is not None
            and
            face_detected
            !=
            self.previous_face_detected
        ):

            return (
                True,
                "FACE_STATE_CHANGE",
            )

        # =================================================
        # OTHERWISE NORMAL SAMPLE
        # =================================================

        return (
            False,
            "PERIODIC_SAMPLE",
        )

    # =====================================================
    # UPDATE PREVIOUS STATES
    # =====================================================

    def _update_previous_states(
        self,
        monitor_output,
        alert_state,
    ):
        """
        Store the latest states for transition detection.
        """

        self.previous_alert_state = (
            alert_state
        )

        self.previous_eye_event = (
            monitor_output.get(
                "eye_event"
            )
        )

        self.previous_mouth_event = (
            monitor_output.get(
                "mouth_event"
            )
        )

        self.previous_distraction_state = (
            monitor_output.get(
                "distraction_state"
            )
        )

        self.previous_face_detected = bool(
            monitor_output.get(
                "face_detected",
                False,
            )
        )

    # =====================================================
    # LOG ONE OBSERVATION
    # =====================================================

    def log(
        self,
        monitor_output,
        alert_state,
    ):
        """
        Log current NINO state.

        Normal telemetry:
            approximately every 0.2 seconds.

        Important event:
            immediately.

        Returns
        -------
        bool

        True
            CSV row written.

        False
            Frame skipped because no important event
            occurred and periodic interval has not elapsed.
        """

        if not self.active:

            raise RuntimeError(
                "No active drive session."
            )

        if monitor_output is None:

            return False

        current_monotonic = (
            time.monotonic()
        )

        # =================================================
        # SHOULD THIS FRAME BE WRITTEN IMMEDIATELY?
        # =================================================

        (
            force_log,
            log_reason,
        ) = self._important_change(
            monitor_output,
            alert_state,
        )

        # =================================================
        # PERIODIC SAMPLING
        # =================================================

        if (
            not force_log
            and
            self.last_log_time is not None
            and
            current_monotonic
            -
            self.last_log_time
            <
            self.sample_interval_seconds
        ):

            # Even though the row is not written,
            # transition history must remain current.
            self._update_previous_states(
                monitor_output,
                alert_state,
            )

            return False

        # =================================================
        # ROW TIMING
        # =================================================

        elapsed_seconds = (
            current_monotonic
            -
            self.session_start_monotonic
        )

        timestamp_utc = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        # =================================================
        # ML HEAD PROBABILITIES
        # =================================================

        probabilities = (
            monitor_output.get(
                "head_direction_probabilities",
                {},
            )
            or
            {}
        )

        # =================================================
        # CREATE ROW
        # =================================================

        row = {
            # =============================================
            # SESSION
            # =============================================

            "session_id":
                self.session_id,

            "timestamp_utc":
                timestamp_utc,

            "elapsed_seconds":
                round(
                    elapsed_seconds,
                    3,
                ),

            # =============================================
            # FACE
            # =============================================

            "face_detected":
                monitor_output.get(
                    "face_detected"
                ),

            # =============================================
            # EYES
            # =============================================

            "left_ear":
                monitor_output.get(
                    "left_ear"
                ),

            "right_ear":
                monitor_output.get(
                    "right_ear"
                ),

            "ear":
                monitor_output.get(
                    "ear"
                ),

            "eye_state":
                monitor_output.get(
                    "eye_state"
                ),

            "eye_closed_duration":
                monitor_output.get(
                    "eye_closed_duration"
                ),

            "eye_event":
                monitor_output.get(
                    "eye_event"
                ),

            "is_drowsy":
                monitor_output.get(
                    "is_drowsy"
                ),

            "blink_count":
                monitor_output.get(
                    "blink_count"
                ),

            "long_eye_closure_count":
                monitor_output.get(
                    "long_eye_closure_count"
                ),

            "drowsiness_event_count":
                monitor_output.get(
                    "drowsiness_event_count"
                ),

            # =============================================
            # MOUTH
            # =============================================

            "mar":
                monitor_output.get(
                    "mar"
                ),

            "mouth_state":
                monitor_output.get(
                    "mouth_state"
                ),

            "mouth_open_duration":
                monitor_output.get(
                    "mouth_open_duration"
                ),

            "mouth_event":
                monitor_output.get(
                    "mouth_event"
                ),

            "mouth_movement_count":
                monitor_output.get(
                    "mouth_movement_count"
                ),

            "yawn_count":
                monitor_output.get(
                    "yawn_count"
                ),

            # =============================================
            # DIAGNOSTIC HEAD POSE
            # =============================================

            "yaw":
                monitor_output.get(
                    "yaw"
                ),

            "pitch":
                monitor_output.get(
                    "pitch"
                ),

            "roll":
                monitor_output.get(
                    "roll"
                ),

            "relative_yaw":
                monitor_output.get(
                    "relative_yaw"
                ),

            "relative_pitch":
                monitor_output.get(
                    "relative_pitch"
                ),

            # =============================================
            # RANDOM FOREST HEAD DIRECTION
            # =============================================

            "head_direction_raw":
                monitor_output.get(
                    "head_direction_raw"
                ),

            "head_direction_raw_confidence":
                monitor_output.get(
                    "head_direction_raw_confidence"
                ),

            "head_direction":
                monitor_output.get(
                    "head_direction"
                ),

            "head_direction_confidence":
                monitor_output.get(
                    "head_direction_confidence"
                ),

            # =============================================
            # RF PROBABILITIES
            # =============================================

            "prob_forward":
                probabilities.get(
                    "FORWARD"
                ),

            "prob_left":
                probabilities.get(
                    "LEFT"
                ),

            "prob_right":
                probabilities.get(
                    "RIGHT"
                ),

            "prob_up":
                probabilities.get(
                    "UP"
                ),

            "prob_down":
                probabilities.get(
                    "DOWN"
                ),

            # =============================================
            # DISTRACTION
            # =============================================

            "distraction_state":
                monitor_output.get(
                    "distraction_state"
                ),

            "distraction_duration":
                monitor_output.get(
                    "distraction_duration"
                ),

            "distraction_event_count":
                monitor_output.get(
                    "distraction_event_count"
                ),

            # =============================================
            # SAFETY ALERT
            # =============================================

            "alert_state":
                alert_state,

            # =============================================
            # LOGGER METADATA
            # =============================================

            "log_reason":
                log_reason,
        }

        # =================================================
        # WRITE ROW
        # =================================================

        self.writer.writerow(
            row
        )

        # Flush immediately so the data survives even if
        # NINO is interrupted unexpectedly.
        self.file.flush()

        self.last_log_time = (
            current_monotonic
        )

        # =================================================
        # UPDATE TRANSITION HISTORY
        # =================================================

        self._update_previous_states(
            monitor_output,
            alert_state,
        )

        return True

    # =====================================================
    # END DRIVE SESSION
    # =====================================================

    def end_session(self):
        """
        Safely finish current drive session.

        Returns
        -------
        Path or None
            Path of completed CSV.
        """

        if not self.active:

            return None

        output_path = (
            self.file_path
        )

        if self.file is not None:

            self.file.flush()

            self.file.close()

        self.file = None

        self.writer = None

        self.active = False

        print()
        print(
            "Drive session ended."
        )

        print(
            "Saved:",
            output_path,
        )

        return output_path