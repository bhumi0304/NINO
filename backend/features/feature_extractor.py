class FeatureExtractor:

    def extract(
        self,
        ear,
        mar,
        yaw,
        pitch,
        roll,
        eye_closed_duration,
        mouth_open_duration,
        blink_count,
        yawn_count,
        head_direction
    ):

        features = {
            "EAR": ear,
            "MAR": mar,
            "Yaw": yaw,
            "Pitch": pitch,
            "Roll": roll,
            "BlinkCount": blink_count,
            "YawnCount": yawn_count,
            "EyeClosedDuration": eye_closed_duration,
            "MouthOpenDuration": mouth_open_duration,
            "HeadDirection": head_direction
        }

        return features