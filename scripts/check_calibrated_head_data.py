import csv
import math
import numpy as np

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
)


DATASET_PATH = (
    "data/head_direction/"
    "head_direction_calibrated_samples.csv"
)

DELTA_FEATURE_NAMES = [
    f"delta_{name}"
    for name in HEAD_FEATURE_NAMES
]

LABELS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
]


def main():

    rows = []

    with open(
        DATASET_PATH,
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            values = []

            valid = True

            for feature in DELTA_FEATURE_NAMES:

                try:
                    value = float(
                        row[feature]
                    )

                    if not math.isfinite(value):
                        valid = False
                        break

                    values.append(value)

                except (ValueError, TypeError, KeyError):

                    valid = False
                    break

            if valid:

                rows.append(
                    {
                        "session_id":
                            row["session_id"],

                        "label":
                            row["label"],

                        "features":
                            np.array(
                                values,
                                dtype=np.float64,
                            ),
                    }
                )

    if not rows:

        print("No valid rows found.")
        return

    sessions = {
        row["session_id"]
        for row in rows
    }

    print()
    print("NINO Calibrated Dataset Check")
    print("=============================")

    print(
        "Samples:",
        len(rows)
    )

    print(
        "Sessions:",
        len(sessions)
    )

    print(
        "Features:",
        len(
            DELTA_FEATURE_NAMES
        )
    )

    # =====================================================
    # COUNTS
    # =====================================================

    print()
    print("Class counts")
    print("------------")

    for label in LABELS:

        count = sum(
            row["label"] == label
            for row in rows
        )

        print(
            f"{label:<8}: {count}"
        )

    # =====================================================
    # FORWARD CHECK
    # =====================================================

    forward_data = np.vstack([
        row["features"]
        for row in rows
        if row["label"] == "FORWARD"
    ])

    forward_abs_mean = np.mean(
        np.abs(forward_data)
    )

    print()
    print("Neutral / FORWARD check")
    print("-----------------------")

    print(
        "Mean absolute FORWARD delta:",
        f"{forward_abs_mean:.4f}"
    )

    # =====================================================
    # FEATURE SEPARATION
    # =====================================================

    X = np.vstack([
        row["features"]
        for row in rows
    ])

    y = [
        row["label"]
        for row in rows
    ]

    overall_mean = np.mean(
        X,
        axis=0,
    )

    between = np.zeros(
        X.shape[1]
    )

    within = np.zeros(
        X.shape[1]
    )

    for label in LABELS:

        indices = [
            i
            for i, current_label
            in enumerate(y)
            if current_label == label
        ]

        class_data = X[
            indices
        ]

        class_mean = np.mean(
            class_data,
            axis=0,
        )

        between += (
            len(class_data)
            *
            (
                class_mean
                - overall_mean
            ) ** 2
        )

        within += np.sum(
            (
                class_data
                - class_mean
            ) ** 2,
            axis=0,
        )

    scores = (
        between
        /
        (within + 1e-9)
    )

    ranking = np.argsort(
        scores
    )[::-1]

    print()
    print("Top 8 delta features")
    print("--------------------")

    for rank, index in enumerate(
        ranking[:8],
        start=1,
    ):

        print(
            f"{rank}. "
            f"{DELTA_FEATURE_NAMES[index]:<30} "
            f"{scores[index]:.4f}"
        )

    # =====================================================
    # TOP FEATURE CLASS MEANS
    # =====================================================

    print()
    print("Top feature class means")
    print("-----------------------")

    for index in ranking[:3]:

        feature_name = (
            DELTA_FEATURE_NAMES[
                index
            ]
        )

        print()
        print(feature_name)

        for label in LABELS:

            values = np.array([
                row["features"][index]
                for row in rows
                if row["label"] == label
            ])

            print(
                f"  {label:<8} "
                f"mean={np.mean(values): .4f} "
                f"std={np.std(values): .4f}"
            )

    print()
    print(
        "Calibrated dataset check complete."
    )


if __name__ == "__main__":
    main()