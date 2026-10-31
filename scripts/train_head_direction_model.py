import csv
import os

import joblib
import numpy as np

from sklearn.ensemble import RandomForestClassifier

from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
)


DATASET_PATH = (
    "data/head_direction/"
    "head_direction_landmark_samples.csv"
)

MODEL_DIR = "models/head_direction"

MODEL_PATH = os.path.join(
    MODEL_DIR,
    "random_forest_head_direction.joblib"
)


LABELS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
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
                for name in HEAD_FEATURE_NAMES
            ]

            X.append(features)
            y.append(row["label"])
            sessions.append(
                row["session_id"]
            )

    return (
        np.array(X, dtype=np.float64),
        np.array(y),
        np.array(sessions),
    )


def get_session_order(sessions):
    """
    Preserve the order in which sessions first
    appeared in the CSV.
    """

    seen = set()
    ordered = []

    for session in sessions:

        if session not in seen:

            seen.add(session)
            ordered.append(session)

    return ordered


def main():

    print()
    print("NINO Head Direction Random Forest")
    print("=================================")

    # =====================================================
    # LOAD DATA
    # =====================================================

    X, y, sessions = load_dataset()

    session_order = get_session_order(
        sessions
    )

    print()
    print("Samples:", len(X))
    print("Features:", X.shape[1])
    print("Sessions:", len(session_order))

    print()
    print("Session order:")

    for index, session in enumerate(
        session_order,
        start=1,
    ):

        print(
            f"Session {index}: {session}"
        )

    # =====================================================
    # REQUIRE AT LEAST 3 SESSIONS
    # =====================================================

    if len(session_order) < 3:

        print()
        print(
            "ERROR: At least 3 sessions are "
            "required for this experiment."
        )

        return

    # =====================================================
    # SESSION-WISE SPLIT
    #
    # First two sessions -> train
    # Third session      -> test
    # =====================================================

    train_sessions = (
        session_order[:2]
    )

    test_session = (
        session_order[2]
    )

    train_mask = np.isin(
        sessions,
        train_sessions,
    )

    test_mask = (
        sessions == test_session
    )

    X_train = X[train_mask]
    y_train = y[train_mask]

    X_test = X[test_mask]
    y_test = y[test_mask]

    print()
    print("Split")
    print("-----")

    print(
        "Training sessions:",
        train_sessions,
    )

    print(
        "Testing session:",
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
        "Training Random Forest..."
    )

    model.fit(
        X_train,
        y_train,
    )

    print(
        "Training complete."
    )

    # =====================================================
    # PREDICTION
    # =====================================================

    predictions = model.predict(
        X_test
    )

    # =====================================================
    # METRICS
    # =====================================================

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

    precision = precision_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0,
    )

    recall = recall_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0,
    )

    f1 = f1_score(
        y_test,
        predictions,
        average="macro",
        zero_division=0,
    )

    print()
    print("Overall Metrics")
    print("---------------")

    print(
        f"Accuracy:          "
        f"{accuracy:.4f}"
    )

    print(
        f"Balanced Accuracy: "
        f"{balanced_accuracy:.4f}"
    )

    print(
        f"Macro Precision:   "
        f"{precision:.4f}"
    )

    print(
        f"Macro Recall:      "
        f"{recall:.4f}"
    )

    print(
        f"Macro F1:          "
        f"{f1:.4f}"
    )

    # =====================================================
    # PER-CLASS REPORT
    # =====================================================

    print()
    print("Classification Report")
    print("---------------------")

    print(
        classification_report(
            y_test,
            predictions,
            labels=LABELS,
            zero_division=0,
        )
    )

    # =====================================================
    # CONFUSION MATRIX
    # =====================================================

    matrix = confusion_matrix(
        y_test,
        predictions,
        labels=LABELS,
    )

    print("Confusion Matrix")
    print("----------------")

    print(
        "Rows    = actual"
    )

    print(
        "Columns = predicted"
    )

    print()

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

    # =====================================================
    # FEATURE IMPORTANCE
    # =====================================================

    importances = (
        model.feature_importances_
    )

    ranked_indices = np.argsort(
        importances
    )[::-1]

    print()
    print("Top 10 Feature Importances")
    print("--------------------------")

    for rank, index in enumerate(
        ranked_indices[:10],
        start=1,
    ):

        print(
            f"{rank:>2}. "
            f"{HEAD_FEATURE_NAMES[index]:<25} "
            f"{importances[index]:.4f}"
        )

    # =====================================================
    # SAVE MODEL
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

        "training_sessions":
            train_sessions,

        "held_out_test_session":
            test_session,

        "metrics": {
            "accuracy":
                accuracy,

            "balanced_accuracy":
                balanced_accuracy,

            "macro_precision":
                precision,

            "macro_recall":
                recall,

            "macro_f1":
                f1,
        },
    }

    joblib.dump(
        model_package,
        MODEL_PATH,
    )

    print()
    print(
        "Model saved:"
    )

    print(
        MODEL_PATH
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "This model has only been tested "
        "across sessions of the current subject."
    )

    print(
        "It is NOT yet validated on unseen people."
    )

    print()


if __name__ == "__main__":
    main()