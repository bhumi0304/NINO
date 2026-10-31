import csv
import math
import os
from collections import Counter, defaultdict

import numpy as np

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
)


DATASET_PATH = (
    "data/head_direction/"
    "head_direction_landmark_samples.csv"
)

EXPECTED_LABELS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
]


def load_dataset():
    """
    Load and validate the landmark dataset.
    """

    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}"
        )

    samples = []

    invalid_rows = 0

    with open(
        DATASET_PATH,
        "r",
        newline="",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        required_columns = {
            "session_id",
            "timestamp",
            "label",
            *HEAD_FEATURE_NAMES,
        }

        missing_columns = (
            required_columns
            - set(reader.fieldnames or [])
        )

        if missing_columns:
            raise ValueError(
                "Missing CSV columns: "
                + ", ".join(
                    sorted(missing_columns)
                )
            )

        for row in reader:

            label = row["label"].strip()

            if label not in EXPECTED_LABELS:
                invalid_rows += 1
                continue

            feature_values = []

            valid = True

            for feature_name in HEAD_FEATURE_NAMES:

                try:
                    value = float(
                        row[feature_name]
                    )

                    if not math.isfinite(value):
                        valid = False
                        break

                    feature_values.append(
                        value
                    )

                except (
                    ValueError,
                    TypeError,
                    KeyError,
                ):
                    valid = False
                    break

            if not valid:
                invalid_rows += 1
                continue

            samples.append(
                {
                    "session_id":
                        row["session_id"],

                    "label":
                        label,

                    "features":
                        np.array(
                            feature_values,
                            dtype=np.float64,
                        ),
                }
            )

    return samples, invalid_rows


def calculate_fisher_scores(
    X,
    labels,
):
    """
    Calculate a simple Fisher-style separability score
    for each feature.

    Higher score means:
        class means are far apart
        compared with variation inside each class.

    This is NOT model training.
    It is only a dataset-quality diagnostic.
    """

    unique_labels = sorted(
        set(labels)
    )

    overall_mean = np.mean(
        X,
        axis=0,
    )

    between_class = np.zeros(
        X.shape[1],
        dtype=np.float64,
    )

    within_class = np.zeros(
        X.shape[1],
        dtype=np.float64,
    )

    for label in unique_labels:

        indices = [
            index
            for index, item
            in enumerate(labels)
            if item == label
        ]

        class_data = X[
            indices
        ]

        class_mean = np.mean(
            class_data,
            axis=0,
        )

        class_size = len(
            class_data
        )

        between_class += (
            class_size
            *
            (
                class_mean
                - overall_mean
            ) ** 2
        )

        within_class += np.sum(
            (
                class_data
                - class_mean
            ) ** 2,
            axis=0,
        )

    epsilon = 1e-9

    fisher_scores = (
        between_class
        /
        (within_class + epsilon)
    )

    return fisher_scores


def print_class_feature_summary(
    X,
    labels,
    feature_index,
    feature_name,
):
    """
    Print mean and standard deviation of one feature
    for every direction.
    """

    print()
    print(
        f"Feature: {feature_name}"
    )

    for label in EXPECTED_LABELS:

        indices = [
            index
            for index, item
            in enumerate(labels)
            if item == label
        ]

        if not indices:
            continue

        values = X[
            indices,
            feature_index,
        ]

        print(
            f"  {label:<8} "
            f"mean={np.mean(values): .4f}  "
            f"std={np.std(values): .4f}"
        )


def main():

    print()
    print(
        "NINO Head Direction Dataset Analysis"
    )

    print(
        "===================================="
    )

    # =====================================================
    # LOAD
    # =====================================================

    samples, invalid_rows = (
        load_dataset()
    )

    if not samples:

        print(
            "No valid samples found."
        )

        return

    labels = [
        sample["label"]
        for sample in samples
    ]

    X = np.vstack([
        sample["features"]
        for sample in samples
    ])

    session_ids = {
        sample["session_id"]
        for sample in samples
    }

    # =====================================================
    # BASIC DATASET INFORMATION
    # =====================================================

    print()
    print(
        "Dataset:"
    )

    print(
        DATASET_PATH
    )

    print()

    print(
        "Valid samples:",
        len(samples),
    )

    print(
        "Invalid rows:",
        invalid_rows,
    )

    print(
        "Feature count:",
        X.shape[1],
    )

    print(
        "Sessions:",
        len(session_ids),
    )

    # =====================================================
    # CLASS DISTRIBUTION
    # =====================================================

    print()
    print(
        "Class distribution"
    )

    print(
        "------------------"
    )

    counts = Counter(
        labels
    )

    for label in EXPECTED_LABELS:

        count = counts.get(
            label,
            0,
        )

        percentage = (
            count
            / len(samples)
            * 100
        )

        print(
            f"{label:<8}: "
            f"{count:<5} "
            f"({percentage:.1f}%)"
        )

    # =====================================================
    # BALANCE CHECK
    # =====================================================

    non_zero_counts = [
        counts[label]
        for label in EXPECTED_LABELS
        if counts[label] > 0
    ]

    print()
    print(
        "Balance check"
    )

    print(
        "-------------"
    )

    if len(non_zero_counts) != len(
        EXPECTED_LABELS
    ):

        print(
            "WARNING: One or more classes "
            "have zero samples."
        )

    else:

        largest = max(
            non_zero_counts
        )

        smallest = min(
            non_zero_counts
        )

        ratio = (
            largest / smallest
        )

        print(
            f"Largest/smallest class ratio: "
            f"{ratio:.2f}"
        )

        if ratio <= 1.25:

            print(
                "Class balance looks good."
            )

        elif ratio <= 1.50:

            print(
                "Class balance is acceptable, "
                "but could be improved."
            )

        else:

            print(
                "WARNING: Dataset is noticeably "
                "imbalanced."
            )

    # =====================================================
    # FEATURE RANGE CHECK
    # =====================================================

    print()
    print(
        "Feature-value check"
    )

    print(
        "-------------------"
    )

    overall_min = np.min(
        X
    )

    overall_max = np.max(
        X
    )

    print(
        f"Overall minimum: "
        f"{overall_min:.4f}"
    )

    print(
        f"Overall maximum: "
        f"{overall_max:.4f}"
    )

    if (
        not np.all(
            np.isfinite(X)
        )
    ):

        print(
            "WARNING: NaN or infinity detected."
        )

    else:

        print(
            "No NaN or infinity detected."
        )

    # =====================================================
    # FEATURE SEPARABILITY
    # =====================================================

    fisher_scores = (
        calculate_fisher_scores(
            X,
            labels,
        )
    )

    ranked_indices = np.argsort(
        fisher_scores
    )[::-1]

    print()
    print(
        "Top 10 potentially useful features"
    )

    print(
        "----------------------------------"
    )

    for rank, index in enumerate(
        ranked_indices[:10],
        start=1,
    ):

        print(
            f"{rank:>2}. "
            f"{HEAD_FEATURE_NAMES[index]:<24} "
            f"score="
            f"{fisher_scores[index]:.4f}"
        )

    # +=====================================================+
    # SHOW CLASS STATISTICS FOR TOP FEATURES
    # +=====================================================+

    print()
    print(
        "Class behavior for top 3 features"
    )

    print(
        "================================="
    )

    for index in ranked_indices[:3]:

        print_class_feature_summary(
            X,
            labels,
            index,
            HEAD_FEATURE_NAMES[index],
        )

    # =====================================================
    # FINAL BASIC CHECK
    # =====================================================

    print()
    print(
        "Basic validation result"
    )

    print(
        "-----------------------"
    )

    all_classes_present = all(
        counts.get(
            label,
            0,
        ) > 0
        for label in EXPECTED_LABELS
    )

    enough_samples = all(
        counts.get(
            label,
            0,
        ) >= 30
        for label in EXPECTED_LABELS
    )

    finite_values = np.all(
        np.isfinite(X)
    )

    if (
        all_classes_present
        and enough_samples
        and finite_values
    ):

        print(
            "PASS: Dataset is structurally "
            "usable for further validation."
        )

    else:

        print(
            "NOT READY: Fix the warnings "
            "above before ML training."
        )

    print()
    print(
        "Important: PASS does NOT mean the "
        "model is ready for deployment."
    )

    print(
        "It only means this dataset is "
        "structurally suitable for the "
        "next ML experiment."
    )

    print()


if __name__ == "__main__":
    main()