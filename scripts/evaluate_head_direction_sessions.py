import csv

import numpy as np

from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    confusion_matrix,
)

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
)


DATASET_PATH = (
    "data/head_direction/"
    "head_direction_calibrated_samples.csv"
)


LABELS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
]
FEATURE_NAMES = [
    f"delta_{name}"
    for name in HEAD_FEATURE_NAMES
]


def load_dataset():

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

            features = [
                float(row[name])
                for name in FEATURE_NAMES
            ]

            X.append(features)
            y.append(row["label"])
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


def get_session_order(sessions):

    seen = set()
    ordered = []

    for session in sessions:

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


def print_confusion_matrix(
    y_true,
    y_pred,
):

    matrix = confusion_matrix(
        y_true,
        y_pred,
        labels=LABELS,
    )

    print()
    print("Confusion Matrix")
    print("----------------")

    print(
        "          "
        + " ".join(
            f"{label[:5]:>6}"
            for label in LABELS
        )
    )

    for label, row in zip(
        LABELS,
        matrix,
    ):

        values = " ".join(
            f"{value:>6}"
            for value in row
        )

        print(
            f"{label[:8]:>8} "
            + values
        )


def main():

    print()
    print(
        "NINO Leave-One-Session-Out Evaluation"
    )

    print(
        "====================================="
    )

    X, y, sessions = load_dataset()

    session_order = get_session_order(
        sessions
    )

    print()
    print(
        "Total samples:",
        len(X),
    )

    print(
        "Sessions:",
        len(session_order),
    )

    print()

    for index, session in enumerate(
        session_order,
        start=1,
    ):

        print(
            f"Session {index}: {session}"
        )

    if len(session_order) < 3:

        print()
        print(
            "ERROR: At least 3 sessions "
            "are required."
        )

        return

    # -----------------------------------------------------
    # Store metrics from each held-out session
    # -----------------------------------------------------

    fold_accuracies = []
    fold_balanced_accuracies = []
    fold_f1_scores = []

    # =====================================================
    # LEAVE ONE SESSION OUT
    # =====================================================

    for fold_number, test_session in enumerate(
        session_order,
        start=1,
    ):

        train_sessions = [
            session
            for session in session_order
            if session != test_session
        ]

        train_mask = np.isin(
            sessions,
            train_sessions,
        )

        test_mask = (
            sessions == test_session
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

        print()
        print(
            "=" * 60
        )

        print(
            f"FOLD {fold_number}"
        )

        print(
            "=" * 60
        )

        print(
            "Training sessions:",
            train_sessions,
        )

        print(
            "Held-out session:",
            test_session,
        )

        print(
            "Training samples:",
            len(X_train),
        )

        print(
            "Testing samples:",
            len(X_test),
        )

        # -------------------------------------------------
        # Train
        # -------------------------------------------------

        model = create_model()

        model.fit(
            X_train,
            y_train,
        )

        # -------------------------------------------------
        # Predict
        # -------------------------------------------------

        predictions = model.predict(
            X_test
        )

        # -------------------------------------------------
        # Metrics
        # -------------------------------------------------

        accuracy = accuracy_score(
            y_test,
            predictions,
        )

        balanced_accuracy = (
            balanced_accuracy_score(
                y_test,
                predictions,
            )
        )

        macro_f1 = f1_score(
            y_test,
            predictions,
            average="macro",
            zero_division=0,
        )

        fold_accuracies.append(
            accuracy
        )

        fold_balanced_accuracies.append(
            balanced_accuracy
        )

        fold_f1_scores.append(
            macro_f1
        )

        print()
        print(
            f"Accuracy:          "
            f"{accuracy:.4f}"
        )

        print(
            f"Balanced Accuracy: "
            f"{balanced_accuracy:.4f}"
        )

        print(
            f"Macro F1:          "
            f"{macro_f1:.4f}"
        )

        print_confusion_matrix(
            y_test,
            predictions,
        )

    # =====================================================
    # COMBINED RESULTS
    # =====================================================

    print()
    print(
        "=" * 60
    )

    print(
        "FINAL CROSS-SESSION RESULTS"
    )

    print(
        "=" * 60
    )

    for index in range(
        len(session_order)
    ):

        print(
            f"Session {index + 1} held out:"
            f"  Accuracy="
            f"{fold_accuracies[index]:.4f}"
            f"  Balanced="
            f"{fold_balanced_accuracies[index]:.4f}"
            f"  Macro F1="
            f"{fold_f1_scores[index]:.4f}"
        )

    print()
    print(
        "Average Accuracy:          "
        f"{np.mean(fold_accuracies):.4f}"
    )

    print(
        "Average Balanced Accuracy: "
        f"{np.mean(fold_balanced_accuracies):.4f}"
    )

    print(
        "Average Macro F1:          "
        f"{np.mean(fold_f1_scores):.4f}"
    )

    print()

    print(
        "Accuracy std deviation:    "
        f"{np.std(fold_accuracies):.4f}"
    )

    print(
        "Macro F1 std deviation:    "
        f"{np.std(fold_f1_scores):.4f}"
    )

    print()

    print(
        "NOTE:"
    )

    print(
        "This evaluates cross-session consistency "
        "for the current subject."
    )

    print(
        "It does not yet measure performance "
        "on unseen people."
    )

    print()


if __name__ == "__main__":
    main()