import os

import joblib
import numpy as np

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
    extract_head_landmark_features,
    align_head_landmark_features,
)


DEFAULT_MODEL_PATH = (
    "models/head_direction/"
    "random_forest_head_direction_aligned.joblib"
)


class HeadDirectionPredictor:
    """
    ML-based head-direction predictor for NINO.

    Pipeline
    --------
    MediaPipe face landmarks
            ↓
    normalized landmark features
            ↓
    eye-line alignment
            ↓
    Random Forest
            ↓
    head direction prediction
    """

    def __init__(
        self,
        model_path=DEFAULT_MODEL_PATH,
    ):

        self.model_path = model_path

        self.model = None

        self.feature_names = None

        self.labels = None

        self.representation = None

        self._load_model()

    # =====================================================
    # MODEL LOADING
    # =====================================================

    def _load_model(self):

        if not os.path.exists(
            self.model_path
        ):

            raise FileNotFoundError(
                "Head-direction model not found: "
                f"{self.model_path}"
            )

        package = joblib.load(
            self.model_path
        )

        # -------------------------------------------------
        # Validate model package
        # -------------------------------------------------

        required_keys = {
            "model",
            "feature_names",
            "labels",
            "representation",
        }

        missing_keys = (
            required_keys
            -
            set(package.keys())
        )

        if missing_keys:

            raise ValueError(
                "Invalid head-direction model package. "
                "Missing keys: "
                + ", ".join(
                    sorted(missing_keys)
                )
            )

        self.model = package[
            "model"
        ]

        self.feature_names = package[
            "feature_names"
        ]

        self.labels = package[
            "labels"
        ]

        self.representation = package[
            "representation"
        ]

        # -------------------------------------------------
        # Critical consistency checks
        # -------------------------------------------------

        if (
            self.representation
            != "ALIGNED_XYZ"
        ):

            raise ValueError(
                "Unexpected model representation: "
                f"{self.representation}"
            )

        if list(
            self.feature_names
        ) != list(
            HEAD_FEATURE_NAMES
        ):

            raise ValueError(
                "Model feature order does not match "
                "the current feature extractor."
            )

    # =====================================================
    # FEATURE VECTOR
    # =====================================================

    def _build_feature_vector(
        self,
        face_landmarks,
    ):
        """
        Convert MediaPipe landmarks into exactly the
        same feature representation used during training.
        """

        # ---------------------------------------------
        # 1. Normalized XYZ landmark features
        # ---------------------------------------------

        normalized_features = (
            extract_head_landmark_features(
                face_landmarks
            )
        )

        if normalized_features is None:
            return None

        # ---------------------------------------------
        # 2. Eye-line alignment
        # ---------------------------------------------

        aligned_features = (
            align_head_landmark_features(
                normalized_features
            )
        )

        if aligned_features is None:
            return None

        # ---------------------------------------------
        # 3. Preserve exact training feature order
        # ---------------------------------------------

        feature_vector = [
            aligned_features[
                feature_name
            ]
            for feature_name
            in self.feature_names
        ]

        return np.array(
            feature_vector,
            dtype=np.float64,
        ).reshape(1, -1)

    # =====================================================
    # PREDICTION
    # =====================================================

    def predict(
        self,
        face_landmarks,
    ):
        """
        Predict head direction.

        Returns
        -------
        str or None

        Possible predictions:
            FORWARD
            LEFT
            RIGHT
            UP
            DOWN
        """

        feature_vector = (
            self._build_feature_vector(
                face_landmarks
            )
        )

        if feature_vector is None:
            return None

        prediction = self.model.predict(
            feature_vector
        )[0]

        return str(
            prediction
        )

    # =====================================================
    # PREDICTION WITH CONFIDENCE
    # =====================================================

    def predict_with_confidence(
        self,
        face_landmarks,
    ):
        """
        Predict head direction and Random Forest
        class probability.

        Returns
        -------
        dict or None

        Example:
        {
            "direction": "LEFT",
            "confidence": 0.91,
            "probabilities": {
                "DOWN": 0.01,
                "FORWARD": 0.04,
                "LEFT": 0.91,
                "RIGHT": 0.02,
                "UP": 0.02
            }
        }
        """

        feature_vector = (
            self._build_feature_vector(
                face_landmarks
            )
        )

        if feature_vector is None:
            return None

        prediction = self.model.predict(
            feature_vector
        )[0]

        probabilities = (
            self.model.predict_proba(
                feature_vector
            )[0]
        )

        classes = self.model.classes_

        probability_map = {
            str(label): float(probability)
            for label, probability
            in zip(
                classes,
                probabilities,
            )
        }

        confidence = probability_map[
            str(prediction)
        ]

        return {
            "direction":
                str(prediction),

            "confidence":
                float(confidence),

            "probabilities":
                probability_map,
        }