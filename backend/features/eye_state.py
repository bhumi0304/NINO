class EyeStateDetector:

    def __init__(
        self,
        ear_threshold=0.20,
        fps=30,
        blink_max_duration=0.8,
        long_closure_duration=1.0,
        drowsiness_duration=1.5
    ):

        self.ear_threshold = ear_threshold

        self.fps = fps

        self.blink_max_frames = int(
            blink_max_duration * fps
        )

        self.long_closure_frames = int(
            long_closure_duration * fps
        )

        self.drowsiness_frames = int(
            drowsiness_duration * fps
        )

        self.closed_frames = 0

        self.eye_closed = False

    def update(self, ear):

        # --------------------------------
        # EYE CLOSED
        # --------------------------------

        if ear < self.ear_threshold:

            self.closed_frames += 1
            self.eye_closed = True

            closed_duration = (
                self.closed_frames / self.fps
            )

            return (
                "CLOSED",
                closed_duration,
                None
            )

        # --------------------------------
        # EYE OPEN
        # --------------------------------

        event = None

        closed_duration = (
            self.closed_frames / self.fps
        )

        if self.eye_closed:

            # Normal blink
            if self.closed_frames <= self.blink_max_frames:

                event = "BLINK"

            # Longer closure
            elif self.closed_frames < self.drowsiness_frames:

                event = "LONG_CLOSURE"

            # Drowsiness
            else:

                event = "DROWSINESS"

        self.closed_frames = 0
        self.eye_closed = False

        return (
            "OPEN",
            0.0,
            event
        )