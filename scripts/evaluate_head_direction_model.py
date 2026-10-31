
from pathlib import Path
import json
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.features.head_landmark_features import align_head_landmark_features

DATASET_PATH = PROJECT_ROOT / "data" / "head_direction" / "head_direction_landmark_samples.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "head_direction" / "random_forest_head_direction_aligned.joblib"
OUTPUT_DIR = PROJECT_ROOT / "data" / "model_evaluation"

LABEL_ORDER = ["FORWARD", "LEFT", "RIGHT", "UP", "DOWN"]


def load_classifier():
    package = joblib.load(MODEL_PATH)

    if isinstance(package, dict):
        classifier = (
            package.get("model")
            or package.get("classifier")
            or package.get("estimator")
        )

        if classifier is None:
            for value in package.values():
                if hasattr(value, "predict") and hasattr(value, "classes_"):
                    classifier = value
                    break
    else:
        classifier = package

    if classifier is None:
        raise RuntimeError("Could not find the trained classifier inside the joblib file.")

    return classifier


def get_feature_columns(df):
    feature_columns = [
        column
        for column in df.columns
        if column not in {"session_id", "timestamp", "label"}
    ]

    if len(feature_columns) != 36:
        raise RuntimeError(
            f"Expected exactly 36 landmark features, but found {len(feature_columns)}.\n"
            f"Detected columns:\n{feature_columns}"
        )

    return feature_columns


def build_aligned_matrix(df, feature_columns):
    rows = []

    for row_index, row in df.iterrows():
        raw_features = {
            column: float(row[column])
            for column in feature_columns
        }

        aligned = align_head_landmark_features(raw_features)

        if aligned is None:
            raise RuntimeError(f"Alignment failed for CSV row {row_index}.")

        aligned_vector = [
            float(aligned[column])
            for column in feature_columns
        ]

        rows.append(aligned_vector)

    X = np.asarray(rows, dtype=float)

    if X.shape[1] != 36:
        raise RuntimeError(f"Aligned feature matrix has incorrect shape: {X.shape}")

    return X


def main():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found:\n{DATASET_PATH}")

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found:\n{MODEL_PATH}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATASET_PATH)

    print("CSV shape:", df.shape)

    feature_columns = get_feature_columns(df)

    print("Feature count:", len(feature_columns))

    X = build_aligned_matrix(df, feature_columns)

    y_true = df["label"].astype(str).str.upper().to_numpy()

    model = load_classifier()

    y_pred = np.asarray(model.predict(X)).astype(str)
    y_pred = np.char.upper(y_pred)

    labels = [
        label
        for label in LABEL_ORDER
        if label in set(y_true) or label in set(y_pred)
    ]

    matrix = confusion_matrix(y_true, y_pred, labels=labels)

    report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )

    full_dataset_accuracy = accuracy_score(y_true, y_pred)

    per_class = {}

    for label in labels:
        metrics = report.get(label, {})
        per_class[label] = {
            "precision": float(metrics.get("precision", 0.0)),
            "recall": float(metrics.get("recall", 0.0)),
            "f1": float(metrics.get("f1-score", 0.0)),
            "support": int(metrics.get("support", 0)),
        }

    feature_importance = []

    if hasattr(model, "feature_importances_"):
        ranked = sorted(
            zip(feature_columns, model.feature_importances_),
            key=lambda item: item[1],
            reverse=True,
        )

        feature_importance = [
            {
                "feature": name,
                "importance": float(value),
            }
            for name, value in ranked
        ]

    result = {
        "samples": int(len(df)),
        "feature_count": 36,
        "classes": labels,
        "cross_session_accuracy": 0.8596,
        "cross_session_macro_f1": 0.8415,
        "cross_session_accuracy_std": 0.0744,
        "full_dataset_accuracy": float(full_dataset_accuracy),
        "confusion_matrix": matrix.tolist(),
        "per_class": per_class,
        "feature_importance": feature_importance,
        "feature_columns": feature_columns,
        "important_note": (
            "The confusion matrix and per-class metrics here come from the final saved model "
            "evaluated on the complete 1,322-sample dataset. Because that final model was trained "
            "on the complete dataset, these are descriptive/training-set results, not held-out "
            "generalization results. The defensible held-out generalization metrics remain "
            "85.96% cross-session accuracy and 84.15% macro F1."
        ),
    }

    json_path = OUTPUT_DIR / "head_direction_evaluation.json"
    matrix_path = OUTPUT_DIR / "confusion_matrix.csv"
    importance_path = OUTPUT_DIR / "feature_importance.csv"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    matrix_df = pd.DataFrame(
        matrix,
        index=[f"TRUE_{label}" for label in labels],
        columns=[f"PRED_{label}" for label in labels],
    )

    matrix_df.to_csv(matrix_path)

    if feature_importance:
        pd.DataFrame(feature_importance).to_csv(importance_path, index=False)

    print()
    print("=" * 68)
    print("NINO HEAD-DIRECTION MODEL EVALUATION")
    print("=" * 68)
    print(f"Samples: {len(df)}")
    print("Feature representation: ALIGNED_XYZ")
    print(f"Features: {len(feature_columns)}")
    print(f"Classes: {', '.join(labels)}")

    print()
    print("HELD-OUT CROSS-SESSION RESULTS")
    print("Accuracy: 85.96%")
    print("Macro F1: 84.15%")
    print("Accuracy std: 7.44%")

    print()
    print("FINAL MODEL ON COMPLETE DATASET")
    print(f"Accuracy: {full_dataset_accuracy * 100:.2f}%")
    print("NOTE: This is NOT held-out accuracy.")

    print()
    print("CONFUSION MATRIX")
    print(matrix_df.to_string())

    print()
    print("PER-CLASS METRICS")

    for label in labels:
        values = per_class[label]
        print(
            f"{label:8s}  "
            f"P={values['precision']:.3f}  "
            f"R={values['recall']:.3f}  "
            f"F1={values['f1']:.3f}  "
            f"N={values['support']}"
        )

    if feature_importance:
        print()
        print("TOP 10 FEATURE IMPORTANCES")

        for item in feature_importance[:10]:
            print(f"{item['feature']:30s} {item['importance']:.5f}")

    print()
    print("SAVED FILES")
    print(json_path)
    print(matrix_path)

    if feature_importance:
        print(importance_path)


if __name__ == "__main__":
    main()
