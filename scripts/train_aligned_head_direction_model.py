import csv
import os

import joblib
import numpy as np

from sklearn.ensemble import RandomForestClassifier

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
    align_head_landmark_features,
)


DATASET_PATH = (
    "data/head_direction/"
    "head_direction_landmark_samples.csv"
)

MODEL_DIR = "models/head_direction"

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "random_forest_head_direction_aligned.joblib"
)


LABELS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
]


def load_dataset():
    """
    Load the original normalized-landmark dataset,
    apply eye-line alignment, and return training data.
    """

    X = []
    y = []
    sessions = []

    with open(
        DATASET_PATH,
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            # ---------------------------------------------
            # Reconstruct normalized feature dictionary
            # from the existing CSV.
            # ---------------------------------------------

            normalized_features = {
                feature_name: float(
                    row[feature_name]
                )
                for feature_name
                in HEAD_FEATURE_NAMES
            }

            # ---------------------------------------------
            # Apply the winning ALIGNED_XYZ transform.
            # ---------------------------------------------

            aligned_features = (
                align_head_landmark_features(
                    normalized_features
                )
            )

            if aligned_features is None:
                continue

            feature_vector = [
                aligned_features[
                    feature_name
                ]
                for feature_name
                in HEAD_FEATURE_NAMES
            ]

            X.append(
                feature_vector
            )

            y.append(
                row["label"]
            )

            sessions.append(
                row["session_id"]
            )

    return (
        np.array(
            X,
            dtype=np.float64,
        ),
        np.array(y),
        np.array(sessions),
    )


def main():

    print()
    print(
        "NINO Final Aligned Head Direction Model"
    )

    print(
        "======================================="
    )

    # =====================================================
    # LOAD DATA
    # =====================================================

    X, y, sessions = load_dataset()

    unique_sessions = list(
        dict.fromkeys(
            sessions
        )
    )

    print()
    print(
        "Training samples:",
        len(X),
    )

    print(
        "Features:",
        X.shape[1],
    )

    print(
        "Sessions:",
        len(unique_sessions),
    )

    print(
        "Classes:",
        sorted(
            set(y)
        ),
    )

    # =====================================================
    # BASIC VALIDATION
    # =====================================================

    if len(X) == 0:

        print(
            "ERROR: No training samples found."
        )

        return

    if X.shape[1] != len(
        HEAD_FEATURE_NAMES
    ):

        print(
            "ERROR: Feature count mismatch."
        )

        return

    # =====================================================
    # RANDOM FOREST
    # =====================================================

    model = RandomForestClassifier(
        n_estimators=300,

        random_state=42,

        n_jobs=-1,

        class_weight="balanced",

        max_features="sqrt",
    )

    print()
    print(
        "Training ALIGNED_XYZ "
        "Random Forest..."
    )

    model.fit(
        X,
        y,
    )

    print(
        "Training complete."
    )

    # =====================================================
    # SAVE MODEL PACKAGE
    # =====================================================

    os.makedirs(
        MODEL_DIR,
        exist_ok=True,
    )

    model_package = {
        "model": model,

        "feature_names":
            HEAD_FEATURE_NAMES,

        "labels":
            LABELS,

        "representation":
            "ALIGNED_XYZ",

        "alignment":
            "outer_eye_line_horizontal",

        "training_sessions":
            unique_sessions,

        "training_sample_count":
            len(X),

        "feature_count":
            len(
                HEAD_FEATURE_NAMES
            ),
    }

    joblib.dump(
        model_package,
        MODEL_PATH,
    )

    print()
    print(
        "Model saved successfully:"
    )

    print(
        MODEL_PATH
    )

    print()
    print(
        "Representation: ALIGNED_XYZ"
    )

    print(
        "Feature count:",
        len(
            HEAD_FEATURE_NAMES
        ),
    )

    print(
        "Training sessions:",
        len(
            unique_sessions
        ),
    )

    print()

    print(
        "NOTE:"
    )

    print(
        "This model uses all 3 current sessions."
    )

    print(
        "Cross-session evaluation was performed "
        "separately before final training."
    )

    print(
        "It is not yet validated on unseen people."
    )

    print()


if __name__ == "__main__":
    main()