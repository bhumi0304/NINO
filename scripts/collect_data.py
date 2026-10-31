import cv2
import csv
import os
from datetime import datetime

import mediapipe as mp

from backend.features.eye_features import calculate_ear
from backend.features.mouth_features import calculate_mar
from backend.features.head_pose import calculate_head_pose
from backend.features.feature_extractor import FeatureExtractor


DATASET_PATH = "data/datasets/driver_features.csv"

COLUMNS = [
    "SessionID",
    "Timestamp",
    "EAR",
    "MAR",
    "Yaw",
    "Pitch",
    "Roll",
    "BlinkCount",
    "YawnCount",
    "EyeClosedDuration",
    "MouthOpenDuration",
    "HeadDirection",
    "DriverState"
]


def create_dataset():

    os.makedirs(
        "data/datasets",
        exist_ok=True
    )

    if not os.path.exists(DATASET_PATH):

        with open(
            DATASET_PATH,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=COLUMNS
            )

            writer.writeheader()


def choose_label():

    print()
    print("=" * 40)
    print("       SELECT DRIVER STATE")
    print("=" * 40)
    print()
    print("1 → ALERT")
    print("2 → DROWSY")
    print("3 → YAWNING")
    print("4 → DISTRACTED")
    print()

    while True:

        choice = input("Enter choice: ").strip()

        labels = {
            "1": "ALERT",
            "2": "DROWSY",
            "3": "YAWNING",
            "4": "DISTRACTED"
        }

        if choice in labels:
            return labels[choice]

        print("Invalid choice. Enter 1, 2, 3 or 4.")


def save_row(
    session_id,
    features,
    driver_state
):

    row = {
        "SessionID": session_id,

        "Timestamp": datetime.now().isoformat(
            timespec="milliseconds"
        ),

        "EAR": features.get("EAR", 0.0),
        "MAR": features.get("MAR", 0.0),

        "Yaw": features.get("Yaw", 0.0),
        "Pitch": features.get("Pitch", 0.0),
        "Roll": features.get("Roll", 0.0),

        "BlinkCount": features.get(
            "BlinkCount",
            0
        ),

        "YawnCount": features.get(
            "YawnCount",
            0
        ),

        "EyeClosedDuration": features.get(
            "EyeClosedDuration",
            0.0
        ),

        "MouthOpenDuration": features.get(
            "MouthOpenDuration",
            0.0
        ),

        "HeadDirection": features.get(
            "HeadDirection",
            "FORWARD"
        ),

        "DriverState": driver_state
    }

    with open(
        DATASET_PATH,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=COLUMNS
        )

        writer.writerow(row)


def main():

    create_dataset()

    label = choose_label()

    session_id = datetime.now().strftime(
        "SESSION_%Y%m%d_%H%M%S"
    )

    print()
    print(f"Selected state : {label}")
    print(f"Session ID     : {session_id}")
    print()
    print("Starting camera...")
    print("Press Q to stop.")
    print()

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("ERROR: Could not open camera.")
        return

    extractor = FeatureExtractor()

    mp_face_mesh = mp.solutions.face_mesh

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:

        while True:

            success, frame = camera.read()

            if not success:
                break

            frame = cv2.flip(frame, 1)

            height, width, _ = frame.shape

            rgb = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            result = face_mesh.process(rgb)

            if result.multi_face_landmarks:

                face = result.multi_face_landmarks[0]

                # -----------------------------
                # Eye
                # -----------------------------

                ear = calculate_ear(
                    face.landmark
                )

                # -----------------------------
                # Mouth
                # -----------------------------

                mar = calculate_mar(
                    face.landmark
                )

                # -----------------------------
                # Head
                # -----------------------------

                pose = calculate_head_pose(
                    face.landmark,
                    width,
                    height
                )

                if pose is not None:

                    yaw, pitch, roll = pose

                else:

                    yaw = 0.0
                    pitch = 0.0
                    roll = 0.0

                # -----------------------------
                # Temporary values
                # -----------------------------

                features = extractor.extract(
                    ear=ear,
                    mar=mar,
                    yaw=yaw,
                    pitch=pitch,
                    roll=roll,
                    eye_closed_duration=0.0,
                    mouth_open_duration=0.0,
                    blink_count=0,
                    yawn_count=0,
                    head_direction="FORWARD"
                )

                # -----------------------------
                # Save
                # -----------------------------

                save_row(
                    session_id,
                    features,
                    label
                )

                # -----------------------------
                # Display
                # -----------------------------

                cv2.putText(
                    frame,
                    f"STATE: {label}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"EAR: {ear:.2f}",
                    (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"MAR: {mar:.2f}",
                    (20, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    "Recording: YES",
                    (20, 145),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

            else:

                cv2.putText(
                    frame,
                    "NO FACE DETECTED",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )

            cv2.imshow(
                "NINO - Data Collection",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    camera.release()
    cv2.destroyAllWindows()

    print()
    print("Data collection finished.")
    print(f"Saved to: {DATASET_PATH}")


if __name__ == "__main__":
    main()