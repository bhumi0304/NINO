from collections import deque

from backend.detection.landmark_indices import (
    LEFT_EYE,
    RIGHT_EYE,
    MOUTH,
)

from backend.features.eye_features import calculate_ear
from backend.features.eye_state import EyeStateDetector

from backend.features.mouth_features import calculate_mar
from backend.features.mouth_state import MouthStateDetector

from backend.features.head_pose import calculate_head_pose

from backend.features.distraction import DistractionDetector

from backend.ml.head_direction_predictor import (
    HeadDirectionPredictor,
)


class DriverMonitor:
    """
    Central feature-processing pipeline for NINO.

    Input:
        MediaPipe face landmarks from one frame.

    Output:
        Structured dictionary containing:
        - EAR
        - MAR
        - eye state/events
        - mouth state/events
        - diagnostic head pose
        - ML head direction
        - ML confidence/probabilities
        - distraction state
        - cumulative event counts
    """

    VALID_HEAD_DIRECTIONS = (
        "FORWARD",
        "LEFT",
        "RIGHT",
        "UP",
        "DOWN",
    )

    def __init__(
        self,
        fps=30,
        calibration_frames=30,
        drowsiness_duration=1.5,
        head_smoothing_frames=5,
    ):

        self.fps = fps

        self.calibration_frames_required = (
            calibration_frames
        )

        self.drowsiness_duration = (
            drowsiness_duration
        )

        # =================================================
        # STATEFUL EYE / MOUTH DETECTORS
        # =================================================

        self.eye_detector = EyeStateDetector(
            fps=fps,
            drowsiness_duration=drowsiness_duration,
        )

        self.mouth_detector = MouthStateDetector(
            fps=fps,
        )

        # =================================================
        # ML HEAD-DIRECTION MODEL
        # =================================================

        self.head_predictor = (
            HeadDirectionPredictor()
        )

        # Keep several recent probability distributions
        # to reduce frame-to-frame ML flickering.
        self.head_probability_history = deque(
            maxlen=head_smoothing_frames
        )

        # =================================================
        # DISTRACTION DETECTOR
        # =================================================

        self.distraction_detector = (
    DistractionDetector(
        fps=fps,
        required_duration=0.7,
    )
)

        # =================================================
        # DIAGNOSTIC HEAD-POSE CALIBRATION
        #
        # IMPORTANT:
        # This calibration is NOT used by the Random Forest
        # to classify LEFT / RIGHT / UP / DOWN / FORWARD.
        #
        # It is retained only so relative yaw/pitch can still
        # be displayed or logged for diagnostic purposes.
        # =================================================

        self.calibration_count = 0

        self.calibration_yaw_values = []

        self.calibration_pitch_values = []

        self.neutral_yaw = None
        self.neutral_pitch = None

        self.is_calibrated = False

        # =================================================
        # SESSION COUNTERS
        # =================================================

        self.blink_count = 0

        self.long_eye_closure_count = 0

        self.drowsiness_event_count = 0

        self.mouth_movement_count = 0

        self.yawn_count = 0

        self.distraction_event_count = 0

        # =================================================
        # CURRENT DISTRACTION STATE
        # =================================================

        self.away_frames = 0

        self.was_distracted = False

    # =====================================================
    # LANDMARK EXTRACTION
    # =====================================================

    @staticmethod
    def _extract_landmarks(
        face_landmarks,
        indices,
    ):
        """
        Extract selected MediaPipe landmarks.
        """

        return [
            face_landmarks[index]
            for index in indices
        ]

    # =====================================================
    # CALIBRATION PROGRESS
    # =====================================================

    def _calibration_progress(self):

        if self.is_calibrated:
            return 1.0

        if (
            self.calibration_frames_required
            <= 0
        ):
            return 1.0

        return min(
            self.calibration_count
            /
            self.calibration_frames_required,
            1.0,
        )

    # =====================================================
    # NO-FACE OUTPUT
    # =====================================================

    def _no_face_output(self):
        """
        Safe output when no face is available.
        """

        return {
            "face_detected": False,

            # Diagnostic pose calibration only
            "calibrated": self.is_calibrated,
            "calibration_progress":
                self._calibration_progress(),

            # ---------------------------------------------
            # Eyes
            # ---------------------------------------------

            "left_ear": None,
            "right_ear": None,
            "ear": None,

            "eye_state": "UNKNOWN",
            "eye_closed_duration": 0.0,
            "eye_event": None,

            "is_drowsy": False,

            "blink_count":
                self.blink_count,

            "long_eye_closure_count":
                self.long_eye_closure_count,

            "drowsiness_event_count":
                self.drowsiness_event_count,

            # ---------------------------------------------
            # Mouth
            # ---------------------------------------------

            "mar": None,

            "mouth_state": "UNKNOWN",

            "mouth_open_duration": 0.0,

            "mouth_event": None,

            "mouth_movement_count":
                self.mouth_movement_count,

            "yawn_count":
                self.yawn_count,

            # ---------------------------------------------
            # Diagnostic head pose
            # ---------------------------------------------

            "yaw": None,
            "pitch": None,
            "roll": None,

            "relative_yaw": None,
            "relative_pitch": None,

            # ---------------------------------------------
            # ML head direction
            # ---------------------------------------------

            "head_direction_raw": "UNKNOWN",

            "head_direction_raw_confidence": None,

            "head_direction": "UNKNOWN",

            "head_direction_confidence": None,

            "head_direction_probabilities": {},

            # ---------------------------------------------
            # Distraction
            # ---------------------------------------------

            "distraction_state": "UNKNOWN",

            "distraction_duration": 0.0,

            "distraction_event_count":
                self.distraction_event_count,
        }

    # =====================================================
    # DIAGNOSTIC HEAD-POSE CALIBRATION
    # =====================================================

    def _process_head_calibration(
        self,
        yaw,
        pitch,
    ):
        """
        Build a neutral yaw/pitch baseline.

        This does NOT affect ML head-direction prediction.

        It exists only to provide:
            relative_yaw
            relative_pitch
        """

        if self.is_calibrated:
            return True

        # Calibration can be disabled by setting
        # calibration_frames=0.
        if (
            self.calibration_frames_required
            <= 0
        ):

            self.neutral_yaw = 0.0
            self.neutral_pitch = 0.0

            self.is_calibrated = True

            return True

        self.calibration_yaw_values.append(
            yaw
        )

        self.calibration_pitch_values.append(
            pitch
        )

        self.calibration_count += 1

        if (
            self.calibration_count
            >=
            self.calibration_frames_required
        ):

            self.neutral_yaw = (
                sum(
                    self.calibration_yaw_values
                )
                /
                len(
                    self.calibration_yaw_values
                )
            )

            self.neutral_pitch = (
                sum(
                    self.calibration_pitch_values
                )
                /
                len(
                    self.calibration_pitch_values
                )
            )

            self.is_calibrated = True

            return True

        return False

    # =====================================================
    # ML TEMPORAL SMOOTHING
    # =====================================================

    def _smooth_head_prediction(
        self,
        probabilities,
    ):
        """
        Smooth recent Random Forest probabilities.

        This is NOT a rule-based head classifier.

        The Random Forest still performs classification.
        We simply average a short history of model
        probabilities to reduce frame-level flickering.

        Returns:
            direction
            confidence
            averaged probability dictionary
        """

        if not probabilities:

            return (
                "UNKNOWN",
                None,
                {},
            )

        probability_sample = {}

        for direction in (
            self.VALID_HEAD_DIRECTIONS
        ):

            probability_sample[
                direction
            ] = float(
                probabilities.get(
                    direction,
                    0.0,
                )
            )

        self.head_probability_history.append(
            probability_sample
        )

        averaged_probabilities = {}

        history_length = len(
            self.head_probability_history
        )

        for direction in (
            self.VALID_HEAD_DIRECTIONS
        ):

            total_probability = sum(
                sample[direction]
                for sample
                in self.head_probability_history
            )

            averaged_probabilities[
                direction
            ] = (
                total_probability
                /
                history_length
            )

        direction = max(
            averaged_probabilities,
            key=averaged_probabilities.get,
        )

        confidence = (
            averaged_probabilities[
                direction
            ]
        )

        return (
            direction,
            float(confidence),
            averaged_probabilities,
        )

    # =====================================================
    # DIRECTION MAPPING FOR EXISTING DISTRACTION DETECTOR
    # =====================================================

    @staticmethod
    def _direction_for_distraction(
        direction,
    ):
        """
        The existing DistractionDetector was designed
        around HeadStateDetector strings such as:

            LOOKING_LEFT
            LOOKING_RIGHT

        Our Random Forest intentionally outputs cleaner
        labels:

            LEFT
            RIGHT
            UP
            DOWN
            FORWARD

        This mapping preserves compatibility without
        bringing threshold-based classification back.
        """

        mapping = {
            "FORWARD": "FORWARD",
            "LEFT": "LOOKING_LEFT",
            "RIGHT": "LOOKING_RIGHT",
            "UP": "LOOKING_UP",
            "DOWN": "LOOKING_DOWN",
        }

        return mapping.get(
            direction
        )

    # =====================================================
    # MAIN PIPELINE
    # =====================================================

    def update(
        self,
        face_landmarks,
        image_width,
        image_height,
    ):
        """
        Process one video frame.
        """

        # =================================================
        # NO FACE
        # =================================================

        if face_landmarks is None:

            return self._no_face_output()

        # =================================================
        # EYE FEATURES
        # =================================================

        left_eye_landmarks = (
            self._extract_landmarks(
                face_landmarks,
                LEFT_EYE,
            )
        )

        right_eye_landmarks = (
            self._extract_landmarks(
                face_landmarks,
                RIGHT_EYE,
            )
        )

        left_ear = calculate_ear(
            left_eye_landmarks
        )

        right_ear = calculate_ear(
            right_eye_landmarks
        )

        ear = (
            left_ear
            +
            right_ear
        ) / 2.0

        (
            eye_state,
            eye_closed_duration,
            eye_event,
        ) = self.eye_detector.update(
            ear
        )

        # -------------------------------------------------
        # Eye-event counters
        # -------------------------------------------------

        if eye_event == "BLINK":

            self.blink_count += 1

        elif eye_event == "LONG_CLOSURE":

            self.long_eye_closure_count += 1

        elif eye_event == "DROWSINESS":

            self.long_eye_closure_count += 1

            self.drowsiness_event_count += 1

        # -------------------------------------------------
        # Current live drowsiness state
        # -------------------------------------------------

        is_drowsy = (
            eye_state == "CLOSED"
            and
            eye_closed_duration
            >=
            self.drowsiness_duration
        )

        # =================================================
        # MOUTH FEATURES
        # =================================================

        mouth_landmarks = (
            self._extract_landmarks(
                face_landmarks,
                MOUTH,
            )
        )

        mar = calculate_mar(
            mouth_landmarks
        )

        (
            mouth_state,
            mouth_open_duration,
            mouth_event,
        ) = self.mouth_detector.update(
            mar
        )

        # -------------------------------------------------
        # Mouth-event counters
        # -------------------------------------------------

        if (
            mouth_event
            ==
            "MOUTH_MOVEMENT"
        ):

            self.mouth_movement_count += 1

        elif (
            mouth_event
            ==
            "POSSIBLE_YAWN"
        ):

            self.yawn_count += 1

        # =================================================
        # DIAGNOSTIC HEAD POSE
        #
        # solvePnP is now COMPLETELY SEPARATE from the
        # Random Forest direction classifier.
        # =================================================

        head_pose = calculate_head_pose(
            face_landmarks,
            image_width,
            image_height,
        )

        if head_pose is None:

            yaw = None
            pitch = None
            roll = None

            relative_yaw = None
            relative_pitch = None

        else:

            yaw, pitch, roll = (
                head_pose
            )

            self._process_head_calibration(
                yaw,
                pitch,
            )

            if (
                self.is_calibrated
                and
                self.neutral_yaw
                is not None
                and
                self.neutral_pitch
                is not None
            ):

                relative_yaw = (
                    yaw
                    -
                    self.neutral_yaw
                )

                relative_pitch = (
                    pitch
                    -
                    self.neutral_pitch
                )

            else:

                # Calibration is diagnostic only.
                # ML prediction below still works.
                relative_yaw = 0.0
                relative_pitch = 0.0

        # =================================================
        # RANDOM FOREST HEAD DIRECTION
        # =================================================

        ml_prediction = (
            self.head_predictor
            .predict_with_confidence(
                face_landmarks
            )
        )

        if ml_prediction is None:

            raw_head_direction = (
                "UNKNOWN"
            )

            raw_head_confidence = None

            head_direction = "UNKNOWN"

            head_direction_confidence = None

            head_direction_probabilities = {}

        else:

            raw_head_direction = (
                ml_prediction[
                    "direction"
                ]
            )

            raw_head_confidence = float(
                ml_prediction[
                    "confidence"
                ]
            )

            (
                head_direction,
                head_direction_confidence,
                head_direction_probabilities,
            ) = self._smooth_head_prediction(
                ml_prediction[
                    "probabilities"
                ]
            )

        # =================================================
        # DISTRACTION
        # =================================================

        distraction_input = (
            self._direction_for_distraction(
                head_direction
            )
        )

        if distraction_input is None:

            # We don't have a reliable direction for
            # this frame.
            distraction_state = "UNKNOWN"

            distraction_duration = 0.0

            self.away_frames = 0

            self.was_distracted = False

        else:

            distraction_state = (
                self.distraction_detector.update(
                    distraction_input
                )
            )

            # ---------------------------------------------
            # Measure continuous time looking away.
            # ---------------------------------------------

            if head_direction in (
                "LEFT",
                "RIGHT",
                "UP",
                "DOWN",
            ):

                self.away_frames += 1

            else:

                self.away_frames = 0

            distraction_duration = (
                self.away_frames
                /
                self.fps
            )

            # ---------------------------------------------
            # Count distraction event only once when
            # entering a distracted state.
            # ---------------------------------------------

            currently_distracted = (
                distraction_state.startswith(
                    "DISTRACTED_"
                )
            )

            if (
                currently_distracted
                and
                not self.was_distracted
            ):

                self.distraction_event_count += 1

            self.was_distracted = (
                currently_distracted
            )

        # =================================================
        # STRUCTURED OUTPUT
        # =================================================

        return {
            "face_detected": True,

            # ---------------------------------------------
            # Diagnostic pose calibration only
            # ---------------------------------------------

            "calibrated":
                self.is_calibrated,

            "calibration_progress":
                self._calibration_progress(),

            # ---------------------------------------------
            # Eyes
            # ---------------------------------------------

            "left_ear":
                left_ear,

            "right_ear":
                right_ear,

            "ear":
                ear,

            "eye_state":
                eye_state,

            "eye_closed_duration":
                eye_closed_duration,

            "eye_event":
                eye_event,

            "is_drowsy":
                is_drowsy,

            "blink_count":
                self.blink_count,

            "long_eye_closure_count":
                self.long_eye_closure_count,

            "drowsiness_event_count":
                self.drowsiness_event_count,

            # ---------------------------------------------
            # Mouth
            # ---------------------------------------------

            "mar":
                mar,

            "mouth_state":
                mouth_state,

            "mouth_open_duration":
                mouth_open_duration,

            "mouth_event":
                mouth_event,

            "mouth_movement_count":
                self.mouth_movement_count,

            "yawn_count":
                self.yawn_count,

            # ---------------------------------------------
            # Diagnostic pose
            # ---------------------------------------------

            "yaw":
                yaw,

            "pitch":
                pitch,

            "roll":
                roll,

            "relative_yaw":
                relative_yaw,

            "relative_pitch":
                relative_pitch,

            # ---------------------------------------------
            # ML head direction
            # ---------------------------------------------

            # Direct RF output before temporal smoothing.
            "head_direction_raw":
                raw_head_direction,

            "head_direction_raw_confidence":
                raw_head_confidence,

            # Final short-window probability-smoothed
            # direction used by distraction detection.
            "head_direction":
                head_direction,

            "head_direction_confidence":
                head_direction_confidence,

            "head_direction_probabilities":
                head_direction_probabilities,

            # ---------------------------------------------
            # Distraction
            # ---------------------------------------------

            "distraction_state":
                distraction_state,

            "distraction_duration":
                distraction_duration,

            "distraction_event_count":
                self.distraction_event_count,
        }