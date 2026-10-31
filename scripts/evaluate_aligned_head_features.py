import csv
import math

import numpy as np

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
)

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
)


DATASET_PATH = (
    "data/head_direction/"
    "head_direction_landmark_samples.csv"
)


# =========================================================
# DATA LOADING
# =========================================================

def load_dataset():

    rows = []

    with open(
        DATASET_PATH,
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            rows.append(row)

    return rows


def get_sessions(rows):

    sessions = []
    seen = set()

    for row in rows:

        session = row["session_id"]

        if session not in seen:

            seen.add(session)
            sessions.append(session)

    return sessions


# =========================================================
# RANDOM FOREST
# =========================================================

def create_model():

    return RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
        max_features="sqrt",
    )


# =========================================================
# EYE-LINE ALIGNMENT
# =========================================================

def align_features(row):
    """
    Rotate the normalized X/Y facial landmark coordinates
    so that the eye line becomes horizontal.

    Existing normalization already handles:
        - translation
        - scale

    This additionally handles:
        - in-plane face/camera rotation
    """

    # -----------------------------------------------------
    # Eye coordinates
    # -----------------------------------------------------

    left_x = float(
        row["left_eye_outer_x"]
    )

    left_y = float(
        row["left_eye_outer_y"]
    )

    right_x = float(
        row["right_eye_outer_x"]
    )

    right_y = float(
        row["right_eye_outer_y"]
    )

    # -----------------------------------------------------
    # Angle of the eye line
    # -----------------------------------------------------

    dx = right_x - left_x
    dy = right_y - left_y

    angle = math.atan2(
        dy,
        dx,
    )

    cos_a = math.cos(angle)
    sin_a = math.sin(angle)

    aligned = {}

    # -----------------------------------------------------
    # Rotate every landmark X/Y coordinate by -angle
    # -----------------------------------------------------

    landmark_names = []

    for feature_name in HEAD_FEATURE_NAMES:

        landmark_name = (
            feature_name.rsplit(
                "_",
                1,
            )[0]
        )

        if landmark_name not in landmark_names:

            landmark_names.append(
                landmark_name
            )

    for landmark_name in landmark_names:

        x = float(
            row[
                f"{landmark_name}_x"
            ]
        )

        y = float(
            row[
                f"{landmark_name}_y"
            ]
        )

        z = float(
            row[
                f"{landmark_name}_z"
            ]
        )

        # Rotate by -angle
        aligned_x = (
            x * cos_a
            +
            y * sin_a
        )

        aligned_y = (
            -x * sin_a
            +
            y * cos_a
        )

        aligned[
            f"{landmark_name}_x"
        ] = aligned_x

        aligned[
            f"{landmark_name}_y"
        ] = aligned_y

        # Z is not changed by 2D rotation.
        aligned[
            f"{landmark_name}_z"
        ] = z

    return aligned


# =========================================================
# FEATURE SET CREATION
# =========================================================

def build_features(
    rows,
    mode,
):

    X = []

    for row in rows:

        if mode.startswith("ALIGNED"):

            source = align_features(
                row
            )

        else:

            source = row

        feature_vector = []

        for feature_name in HEAD_FEATURE_NAMES:

            # ---------------------------------------------
            # Decide which coordinate axes to include
            # ---------------------------------------------

            if mode in (
                "RAW_XY",
                "ALIGNED_XY",
            ):

                if feature_name.endswith(
                    "_z"
                ):
                    continue

            # ---------------------------------------------

            feature_vector.append(
                float(
                    source[
                        feature_name
                    ]
                )
            )

        X.append(
            feature_vector
        )

    return np.array(
        X,
        dtype=np.float64,
    )


# =========================================================
# EVALUATION
# =========================================================

def evaluate_mode(
    rows,
    sessions,
    mode,
):

    X = build_features(
        rows,
        mode,
    )

    y = np.array([
        row["label"]
        for row in rows
    ])

    row_sessions = np.array([
        row["session_id"]
        for row in rows
    ])

    accuracies = []
    balanced_scores = []
    f1_scores = []

    print()
    print("=" * 65)
    print(mode)
    print("=" * 65)

    for fold, test_session in enumerate(
        sessions,
        start=1,
    ):

        train_mask = (
            row_sessions
            != test_session
        )

        test_mask = (
            row_sessions
            == test_session
        )

        X_train = X[
            train_mask
        ]

        y_train = y[
            train_mask
        ]

        X_test = X[
            test_mask
        ]

        y_test = y[
            test_mask
        ]

        model = create_model()

        model.fit(
            X_train,
            y_train,
        )

        predictions = model.predict(
            X_test
        )

        accuracy = accuracy_score(
            y_test,
            predictions,
        )

        balanced = balanced_accuracy_score(
            y_test,
            predictions,
        )

        macro_f1 = f1_score(
            y_test,
            predictions,
            average="macro",
            zero_division=0,
        )

        accuracies.append(
            accuracy
        )

        balanced_scores.append(
            balanced
        )

        f1_scores.append(
            macro_f1
        )

        print(
            f"Session {fold} held out: "
            f"Accuracy={accuracy:.4f}  "
            f"Balanced={balanced:.4f}  "
            f"Macro F1={macro_f1:.4f}"
        )

    result = {
        "accuracy":
            np.mean(accuracies),

        "balanced":
            np.mean(
                balanced_scores
            ),

        "f1":
            np.mean(f1_scores),

        "std":
            np.std(accuracies),
    }

    print()

    print(
        "Average Accuracy:",
        f"{result['accuracy']:.4f}"
    )

    print(
        "Average Balanced:",
        f"{result['balanced']:.4f}"
    )

    print(
        "Average Macro F1:",
        f"{result['f1']:.4f}"
    )

    print(
        "Accuracy std:",
        f"{result['std']:.4f}"
    )

    return result


# =========================================================
# MAIN
# =========================================================

def main():

    print()
    print(
        "NINO Eye-Aligned Head Feature Experiment"
    )

    print(
        "========================================"
    )

    rows = load_dataset()

    sessions = get_sessions(
        rows
    )

    print()
    print(
        "Samples:",
        len(rows)
    )

    print(
        "Sessions:",
        len(sessions)
    )

    # -----------------------------------------------------
    # Compare four representations
    # -----------------------------------------------------

    modes = [
        "RAW_XYZ",
        "RAW_XY",
        "ALIGNED_XYZ",
        "ALIGNED_XY",
    ]

    results = {}

    for mode in modes:

        results[mode] = (
            evaluate_mode(
                rows,
                sessions,
                mode,
            )
        )

    # =====================================================
    # SUMMARY
    # =====================================================

    print()
    print("=" * 65)

    print(
        "FINAL FEATURE REPRESENTATION SUMMARY"
    )

    print("=" * 65)

    for mode in modes:

        result = results[
            mode
        ]

        print(
            f"{mode:<12} "
            f"Accuracy="
            f"{result['accuracy']:.4f}  "
            f"Macro F1="
            f"{result['f1']:.4f}  "
            f"Std="
            f"{result['std']:.4f}"
        )

    best_mode = max(
        modes,
        key=lambda mode:
            results[mode]["f1"]
    )

    print()

    print(
        "Best representation by Macro F1:",
        best_mode,
    )


if __name__ == "__main__":
    main()