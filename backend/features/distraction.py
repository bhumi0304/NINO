class DistractionDetector:

    def __init__(
        self,
        required_duration=1.5,
        fps=30
    ):
        self.required_frames = int(
            required_duration * fps
        )

        self.left_frames = 0
        self.right_frames = 0
        self.up_frames = 0
        self.down_frames = 0

    def update(self, direction):

        # Reset the counters that aren't currently active
        if direction != "LOOKING_LEFT":
            self.left_frames = 0

        if direction != "LOOKING_RIGHT":
            self.right_frames = 0

        if direction != "LOOKING_UP":
            self.up_frames = 0

        if direction != "LOOKING_DOWN":
            self.down_frames = 0

        # Count sustained movement
        if direction == "LOOKING_LEFT":
            self.left_frames += 1

        elif direction == "LOOKING_RIGHT":
            self.right_frames += 1

        elif direction == "LOOKING_UP":
            self.up_frames += 1

        elif direction == "LOOKING_DOWN":
            self.down_frames += 1

        # Check whether movement lasted long enough
        if self.left_frames >= self.required_frames:
            return "DISTRACTED_LEFT"

        if self.right_frames >= self.required_frames:
            return "DISTRACTED_RIGHT"

        if self.up_frames >= self.required_frames:
            return "DISTRACTED_UP"

        if self.down_frames >= self.required_frames:
            return "DISTRACTED_DOWN"

        return "ATTENTIVE"