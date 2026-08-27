class MouthStateDetector:

    def __init__(
        self,
        mar_threshold=0.50,
        fps=30,
        yawn_min_duration=1.0
    ):

        self.mar_threshold = mar_threshold
        self.fps = fps

        self.yawn_min_frames = int(
            yawn_min_duration * fps
        )

        self.open_frames = 0
        self.mouth_open = False

    def update(self, mar):

        # Mouth is open
        if mar >= self.mar_threshold:

            self.open_frames += 1
            self.mouth_open = True

            duration = (
                self.open_frames / self.fps
            )

            return (
                "OPEN",
                duration,
                None
            )

        # Mouth closed
        else:

            event = None

            duration = (
                self.open_frames / self.fps
            )

            if self.mouth_open:

                if self.open_frames >= self.yawn_min_frames:

                    event = "POSSIBLE_YAWN"

                else:

                    event = "MOUTH_MOVEMENT"

            self.open_frames = 0
            self.mouth_open = False

            return (
                "CLOSED",
                0.0,
                event
            )