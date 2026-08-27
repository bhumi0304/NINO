from collections import deque


class HeadStateDetector:

    def __init__(
        self,
        yaw_threshold=12,
        pitch_threshold=12,
        smoothing_frames=7
    ):

        self.yaw_threshold = yaw_threshold
        self.pitch_threshold = pitch_threshold

        self.yaw_history = deque(
            maxlen=smoothing_frames
        )

        self.pitch_history = deque(
            maxlen=smoothing_frames
        )

        self.neutral_yaw = None
        self.neutral_pitch = None

        self.current_state = "FORWARD"

    # -----------------------------------------------------
    # Calibration
    # -----------------------------------------------------

    def calibrate(self, yaw, pitch):

        self.neutral_yaw = yaw
        self.neutral_pitch = pitch

        self.yaw_history.clear()
        self.pitch_history.clear()

    # -----------------------------------------------------
    # Update
    # -----------------------------------------------------

    def update(self, yaw, pitch):

        if self.neutral_yaw is None:
            return "CALIBRATING"

        # Relative movement from neutral position
        relative_yaw = (
            yaw - self.neutral_yaw
        )

        relative_pitch = (
            pitch - self.neutral_pitch
        )

        # Add to smoothing buffers
        self.yaw_history.append(
            relative_yaw
        )

        self.pitch_history.append(
            relative_pitch
        )

        # Average recent frames
        smooth_yaw = (
            sum(self.yaw_history)
            / len(self.yaw_history)
        )

        smooth_pitch = (
            sum(self.pitch_history)
            / len(self.pitch_history)
        )

        # -------------------------------------------------
        # Direction
        # -------------------------------------------------

        # LEFT / RIGHT
        if smooth_yaw > self.yaw_threshold:

            self.current_state = "LOOKING_RIGHT"

        elif smooth_yaw < -self.yaw_threshold:

            self.current_state = "LOOKING_LEFT"

        # UP / DOWN
        elif smooth_pitch > self.pitch_threshold:

            self.current_state = "LOOKING_UP"

        elif smooth_pitch < -self.pitch_threshold:

            self.current_state = "LOOKING_DOWN"

        else:

            self.current_state = "FORWARD"

        return self.current_state

    # -----------------------------------------------------
    # Relative values for display
    # -----------------------------------------------------

    def get_relative_angles(self, yaw, pitch):

        if self.neutral_yaw is None:

            return 0.0, 0.0

        relative_yaw = (
            yaw - self.neutral_yaw
        )

        relative_pitch = (
            pitch - self.neutral_pitch
        )

        return relative_yaw, relative_pitch