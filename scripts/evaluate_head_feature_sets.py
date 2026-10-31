import csv

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
    "head_direction_calibrated_samples.csv"
)


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

    ordered = []
    seen = set()

    for row in rows:

        session = row["session_id"]

        if session not in seen:

            seen.add(session)
            ordered.append(session)

    return ordered


def create_model():

    return RandomForestClassifier(
        n_estimators=300,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
        max_features="sqrt",
    )


def evaluate_feature_set(
    rows,
    sessions,
    feature_names,
    title,
):

    print()
    print("=" * 65)
    print(title)
    print("=" * 65)

    X = np.array(
        [
            [
                float(
                    row[
                        f"delta_{feature}"
                    ]
                )
                for feature in feature_names
            ]
            for row in rows
        ],
        dtype=np.float64,
    )

    y = np.array(
        [
            row["label"]
            for row in rows
        ]
    )

    row_sessions = np.array(
        [
            row["session_id"]
            for row in rows
        ]
    )

    accuracies = []
    balanced_scores = []
    f1_scores = []

    for fold, test_session in enumerate(
        sessions,
        start=1,
    ):

        train_mask = (
            row_sessions != test_session
        )

        test_mask = (
            row_sessions == test_session
        )

        X_train = X[train_mask]
        y_train = y[train_mask]

        X_test = X[test_mask]
        y_test = y[test_mask]

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

    print()
    print(
        f"Average Accuracy: "
        f"{np.mean(accuracies):.4f}"
    )

    print(
        f"Average Balanced Accuracy: "
        f"{np.mean(balanced_scores):.4f}"
    )

    print(
        f"Average Macro F1: "
        f"{np.mean(f1_scores):.4f}"
    )

    print(
        f"Accuracy std: "
        f"{np.std(accuracies):.4f}"
    )

    return (
        np.mean(accuracies),
        np.mean(f1_scores),
    )


def main():

    print()
    print(
        "NINO Head Feature-Subset Experiment"
    )

    print(
        "==================================="
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

    # =====================================================
    # FEATURE GROUPS
    # =====================================================

    all_features = (
        HEAD_FEATURE_NAMES
    )

    xy_features = [
        feature
        for feature in HEAD_FEATURE_NAMES
        if (
            feature.endswith("_x")
            or
            feature.endswith("_y")
        )
    ]

    z_features = [
        feature
        for feature in HEAD_FEATURE_NAMES
        if feature.endswith("_z")
    ]

    x_features = [
        feature
        for feature in HEAD_FEATURE_NAMES
        if feature.endswith("_x")
    ]

    y_features = [
        feature
        for feature in HEAD_FEATURE_NAMES
        if feature.endswith("_y")
    ]

    # =====================================================
    # TEST
    # =====================================================

    results = {}

    results["XYZ"] = evaluate_feature_set(
        rows,
        sessions,
        all_features,
        "ALL FEATURES (X + Y + Z)",
    )

    results["XY"] = evaluate_feature_set(
        rows,
        sessions,
        xy_features,
        "2D FEATURES ONLY (X + Y)",
    )

    results["Z"] = evaluate_feature_set(
        rows,
        sessions,
        z_features,
        "DEPTH FEATURES ONLY (Z)",
    )

    results["X"] = evaluate_feature_set(
        rows,
        sessions,
        x_features,
        "X FEATURES ONLY",
    )

    results["Y"] = evaluate_feature_set(
        rows,
        sessions,
        y_features,
        "Y FEATURES ONLY",
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    print()
    print("=" * 65)
    print("FEATURE-SET SUMMARY")
    print("=" * 65)

    for name, (
        accuracy,
        macro_f1,
    ) in results.items():

        print(
            f"{name:<5} "
            f"Accuracy={accuracy:.4f}  "
            f"Macro F1={macro_f1:.4f}"
        )

    best = max(
        results,
        key=lambda name:
            results[name][1]
    )

    print()
    print(
        "Best feature set by Macro F1:",
        best,
    )


if __name__ == "__main__":
    main()