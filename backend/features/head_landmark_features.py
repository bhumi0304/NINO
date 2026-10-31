import math


# ---------------------------------------------------------
# Landmarks selected for head-direction ML.
# ---------------------------------------------------------

HEAD_LANDMARKS = {
    "nose_tip": 1,
    "nose_bridge": 168,
    "chin": 152,

    "left_eye_outer": 33,
    "left_eye_inner": 133,

    "right_eye_inner": 362,
    "right_eye_outer": 263,

    "left_cheek": 234,
    "right_cheek": 454,

    "left_mouth": 61,
    "right_mouth": 291,

    "forehead": 10,
}


# ---------------------------------------------------------
# Landmarks used for normalization.
# ---------------------------------------------------------

LEFT_EYE_ANCHOR = 33
RIGHT_EYE_ANCHOR = 263


# ---------------------------------------------------------
# Feature names.
#
# 12 landmarks × 3 coordinates = 36 features.
# ---------------------------------------------------------

HEAD_FEATURE_NAMES = []

for landmark_name in HEAD_LANDMARKS:

    HEAD_FEATURE_NAMES.extend([
        f"{landmark_name}_x",
        f"{landmark_name}_y",
        f"{landmark_name}_z",
    ])


# =========================================================
# DISTANCE
# =========================================================

def _distance_2d(
    point1,
    point2,
):
    """
    Calculate 2D Euclidean distance between
    two MediaPipe landmarks.
    """

    return math.sqrt(
        (point1.x - point2.x) ** 2
        +
        (point1.y - point2.y) ** 2
    )


# =========================================================
# NORMALIZED LANDMARK FEATURE EXTRACTION
# =========================================================

def extract_head_landmark_features(
    face_landmarks,
):
    """
    Convert MediaPipe face landmarks into normalized
    numerical features for head-direction ML.

    Normalization
    -------------
    1. Use midpoint between outer eyes as origin.
    2. Use inter-eye distance as scale.

    This reduces variation caused by:
        - face position in frame
        - distance from camera
        - different face sizes

    Returns
    -------
    dict or None
        36 normalized XYZ features.
    """

    if face_landmarks is None:
        return None

    # -----------------------------------------------------
    # Make sure all required landmarks exist.
    # -----------------------------------------------------

    maximum_index = max(
        max(HEAD_LANDMARKS.values()),
        LEFT_EYE_ANCHOR,
        RIGHT_EYE_ANCHOR,
    )

    if len(face_landmarks) <= maximum_index:
        return None

    # -----------------------------------------------------
    # Eye anchors.
    # -----------------------------------------------------

    left_eye = face_landmarks[
        LEFT_EYE_ANCHOR
    ]

    right_eye = face_landmarks[
        RIGHT_EYE_ANCHOR
    ]

    # -----------------------------------------------------
    # Center of face using midpoint of outer eyes.
    # -----------------------------------------------------

    center_x = (
        left_eye.x
        +
        right_eye.x
    ) / 2.0

    center_y = (
        left_eye.y
        +
        right_eye.y
    ) / 2.0

    center_z = (
        left_eye.z
        +
        right_eye.z
    ) / 2.0

    # -----------------------------------------------------
    # Scale normalization using eye distance.
    # -----------------------------------------------------

    eye_distance = _distance_2d(
        left_eye,
        right_eye,
    )

    if eye_distance < 1e-6:
        return None

    # -----------------------------------------------------
    # Build normalized feature dictionary.
    # -----------------------------------------------------

    features = {}

    for (
        landmark_name,
        landmark_index,
    ) in HEAD_LANDMARKS.items():

        point = face_landmarks[
            landmark_index
        ]

        normalized_x = (
            point.x
            -
            center_x
        ) / eye_distance

        normalized_y = (
            point.y
            -
            center_y
        ) / eye_distance

        normalized_z = (
            point.z
            -
            center_z
        ) / eye_distance

        features[
            f"{landmark_name}_x"
        ] = float(
            normalized_x
        )

        features[
            f"{landmark_name}_y"
        ] = float(
            normalized_y
        )

        features[
            f"{landmark_name}_z"
        ] = float(
            normalized_z
        )

    return features


# =========================================================
# EYE-LINE ALIGNMENT
# =========================================================

def align_head_landmark_features(
    features,
):
    """
    Align normalized facial landmark features so that
    the outer-eye line becomes horizontal.

    The extractor already normalizes:
        - translation
        - scale

    This additionally normalizes:
        - in-plane face/camera rotation

    X and Y coordinates are rotated.

    Z remains unchanged.

    Parameters
    ----------
    features : dict
        Output from extract_head_landmark_features().

    Returns
    -------
    dict or None
        Same 36 feature names using aligned coordinates.
    """

    if features is None:
        return None

    # -----------------------------------------------------
    # Get eye-line coordinates.
    # -----------------------------------------------------

    try:

        left_x = features[
            "left_eye_outer_x"
        ]

        left_y = features[
            "left_eye_outer_y"
        ]

        right_x = features[
            "right_eye_outer_x"
        ]

        right_y = features[
            "right_eye_outer_y"
        ]

    except KeyError:

        return None

    # -----------------------------------------------------
    # Calculate eye-line angle.
    # -----------------------------------------------------

    dx = (
        right_x
        -
        left_x
    )

    dy = (
        right_y
        -
        left_y
    )

    eye_line_length = math.sqrt(
        dx ** 2
        +
        dy ** 2
    )

    if eye_line_length < 1e-6:
        return None

    angle = math.atan2(
        dy,
        dx,
    )

    cos_angle = math.cos(
        angle
    )

    sin_angle = math.sin(
        angle
    )

    # -----------------------------------------------------
    # Rotate all landmark X/Y coordinates by -angle.
    # -----------------------------------------------------

    aligned_features = {}

    for landmark_name in HEAD_LANDMARKS:

        x = features[
            f"{landmark_name}_x"
        ]

        y = features[
            f"{landmark_name}_y"
        ]

        z = features[
            f"{landmark_name}_z"
        ]

        aligned_x = (
            x * cos_angle
            +
            y * sin_angle
        )

        aligned_y = (
            -x * sin_angle
            +
            y * cos_angle
        )

        aligned_features[
            f"{landmark_name}_x"
        ] = float(
            aligned_x
        )

        aligned_features[
            f"{landmark_name}_y"
        ] = float(
            aligned_y
        )

        # Z is deliberately preserved.
        aligned_features[
            f"{landmark_name}_z"
        ] = float(
            z
        )

    return aligned_features


# =========================================================
# NEUTRAL CALIBRATOR
#
# Keep this because it belongs to our experiment history.
# We are NOT using it for the current ALIGNED_XYZ model.
# =========================================================

class HeadLandmarkCalibrator:
    """
    Builds a neutral landmark-feature baseline and
    converts current head features into deviations
    from that neutral position.
    """

    def __init__(
        self,
        required_frames=30,
    ):

        self.required_frames = (
            required_frames
        )

        self.samples = []

        self.baseline = None

    @property
    def is_calibrated(self):

        return (
            self.baseline
            is not None
        )

    @property
    def progress(self):

        if self.is_calibrated:
            return 1.0

        return min(
            len(self.samples)
            /
            self.required_frames,
            1.0,
        )

    def add_calibration_sample(
        self,
        features,
    ):
        """
        Add one FORWARD-position feature sample.
        """

        if features is None:
            return False

        if self.is_calibrated:
            return True

        self.samples.append(
            features.copy()
        )

        if (
            len(self.samples)
            >=
            self.required_frames
        ):

            self._calculate_baseline()

            return True

        return False

    def _calculate_baseline(
        self,
    ):

        self.baseline = {}

        for feature_name in (
            HEAD_FEATURE_NAMES
        ):

            values = [
                sample[
                    feature_name
                ]
                for sample
                in self.samples
            ]

            self.baseline[
                feature_name
            ] = (
                sum(values)
                /
                len(values)
            )

    def transform(
        self,
        features,
    ):
        """
        Convert normalized features into
        neutral-relative features.
        """

        if (
            features is None
            or
            not self.is_calibrated
        ):

            return None

        relative_features = {}

        for feature_name in (
            HEAD_FEATURE_NAMES
        ):

            relative_features[
                feature_name
            ] = float(
                features[
                    feature_name
                ]
                -
                self.baseline[
                    feature_name
                ]
            )

        return relative_features

    def reset(
        self,
    ):

        self.samples = []

        self.baseline = None