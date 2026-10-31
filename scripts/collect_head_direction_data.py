import csv
import os
import time
import uuid

import cv2
import mediapipe as mp

from backend.features.head_landmark_features import (
    HEAD_FEATURE_NAMES,
    HeadLandmarkCalibrator,
    extract_head_landmark_features,
)


MODEL_PATH = "models/mediapipe/face_landmarker.task"

OUTPUT_FILE = (
    "data/head_direction/"
    "head_direction_calibrated_samples.csv"
)


CALIBRATION_FRAMES = 30

PREPARE_SECONDS = 2.0
STABILIZE_SECONDS = 1.0
COLLECT_SECONDS = 3.0


DIRECTIONS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
]


# We explicitly call these DELTA features so that
# they can never be confused with the old absolute
# landmark dataset.
DELTA_FEATURE_NAMES = [
    f"delta_{name}"
    for name in HEAD_FEATURE_NAMES
]


CSV_COLUMNS = [
    "session_id",
    "timestamp",
    "label",
] + DELTA_FEATURE_NAMES


def append_sample(row):

    file_exists = os.path.exists(
        OUTPUT_FILE
    )

    with open(
        OUTPUT_FILE,
        "a",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=CSV_COLUMNS,
        )

        if not file_exists:
            writer.writeheader()

        writer.writerow(row)


def draw_text(
    frame,
    text,
    y,
    color=(255, 255, 255),
    scale=0.8,
):

    cv2.putText(
        frame,
        text,
        (20, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        2,
    )


def main():

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True,
    )

    session_id = str(
        uuid.uuid4()
    )[:8]

    # =====================================================
    # MEDIAPIPE
    # =====================================================

    BaseOptions = mp.tasks.BaseOptions

    FaceLandmarker = (
        mp.tasks.vision.FaceLandmarker
    )

    FaceLandmarkerOptions = (
        mp.tasks.vision.FaceLandmarkerOptions
    )

    RunningMode = (
        mp.tasks.vision.RunningMode
    )

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(
            model_asset_path=MODEL_PATH
        ),
        running_mode=RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    # =====================================================
    # NEUTRAL LANDMARK CALIBRATOR
    # =====================================================

    calibrator = HeadLandmarkCalibrator(
        required_frames=CALIBRATION_FRAMES
    )

    # =====================================================
    # CAMERA
    # =====================================================

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("Could not open camera")
        return

    print()
    print("NINO Calibrated Head Dataset Collector")
    print("--------------------------------------")
    print("Session:", session_id)
    print()
    print("First look FORWARD for calibration.")
    print("After calibration, follow the directions.")
    print("Press Q to quit.")
    print()

    current_direction_index = 0

    phase = "CALIBRATION"

    phase_start_time = None

    samples_collected = 0

    samples_per_label = {
        label: 0
        for label in DIRECTIONS
    }

    mediapipe_timestamp = 0

    # =====================================================
    # MAIN LOOP
    # =====================================================

    with FaceLandmarker.create_from_options(
        options
    ) as landmarker:

        while True:

            success, frame = camera.read()

            if not success:

                print(
                    "Could not read camera frame"
                )

                break

            frame = cv2.flip(
                frame,
                1,
            )

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame,
            )

            result = landmarker.detect_for_video(
                mp_image,
                mediapipe_timestamp,
            )

            mediapipe_timestamp += 33

            # =================================================
            # EXTRACT RAW NORMALIZED FEATURES
            # =================================================

            raw_features = None

            if result.face_landmarks:

                face_landmarks = (
                    result.face_landmarks[0]
                )

                raw_features = (
                    extract_head_landmark_features(
                        face_landmarks
                    )
                )

            # =================================================
            # CALIBRATION
            # =================================================

            if not calibrator.is_calibrated:

                draw_text(
                    frame,
                    "CALIBRATING",
                    45,
                    (0, 255, 255),
                    1.0,
                )

                draw_text(
                    frame,
                    "LOOK STRAIGHT AT CAMERA",
                    95,
                    (0, 255, 255),
                    0.9,
                )

                progress = int(
                    calibrator.progress
                    * 100
                )

                draw_text(
                    frame,
                    f"Progress: {progress}%",
                    140,
                )

                draw_text(
                    frame,
                    "Keep head still",
                    180,
                )

                if raw_features is not None:

                    calibrator.add_calibration_sample(
                        raw_features
                    )

                else:

                    draw_text(
                        frame,
                        "FACE NOT DETECTED",
                        225,
                        (0, 0, 255),
                    )

                # Calibration just completed.
                if calibrator.is_calibrated:

                    phase = "PREPARE"

                    phase_start_time = (
                        time.perf_counter()
                    )

            # =================================================
            # NORMAL DATA COLLECTION
            # =================================================

            else:

                # Convert raw face geometry into deviation
                # from this session's neutral face geometry.
                relative_features = (
                    calibrator.transform(
                        raw_features
                    )
                )

                # =============================================
                # COLLECTION FINISHED
                # =============================================

                if (
                    current_direction_index
                    >= len(DIRECTIONS)
                ):

                    draw_text(
                        frame,
                        "COLLECTION COMPLETE",
                        50,
                        (0, 255, 0),
                        1.0,
                    )

                    draw_text(
                        frame,
                        (
                            "Total samples: "
                            f"{samples_collected}"
                        ),
                        95,
                    )

                    y = 140

                    for label in DIRECTIONS:

                        draw_text(
                            frame,
                            (
                                f"{label}: "
                                f"{samples_per_label[label]}"
                            ),
                            y,
                        )

                        y += 35

                    draw_text(
                        frame,
                        "Press Q to exit",
                        y + 20,
                        (0, 255, 255),
                    )

                else:

                    current_label = (
                        DIRECTIONS[
                            current_direction_index
                        ]
                    )

                    current_time = (
                        time.perf_counter()
                    )

                    elapsed = (
                        current_time
                        - phase_start_time
                    )

                    # =========================================
                    # PREPARE
                    # =========================================

                    if phase == "PREPARE":

                        remaining = max(
                            0.0,
                            PREPARE_SECONDS
                            - elapsed,
                        )

                        draw_text(
                            frame,
                            "GET READY",
                            45,
                            (0, 255, 255),
                        )

                        draw_text(
                            frame,
                            f"LOOK {current_label}",
                            95,
                            (0, 255, 255),
                            1.1,
                        )

                        draw_text(
                            frame,
                            (
                                "Move into position: "
                                f"{remaining:.1f}s"
                            ),
                            145,
                        )

                        if (
                            elapsed
                            >= PREPARE_SECONDS
                        ):

                            phase = "STABILIZE"

                            phase_start_time = (
                                time.perf_counter()
                            )

                    # =========================================
                    # STABILIZE
                    # =========================================

                    elif phase == "STABILIZE":

                        remaining = max(
                            0.0,
                            STABILIZE_SECONDS
                            - elapsed,
                        )

                        draw_text(
                            frame,
                            f"LOOK {current_label}",
                            50,
                            (0, 255, 255),
                            1.1,
                        )

                        draw_text(
                            frame,
                            "HOLD STILL",
                            100,
                            (0, 255, 255),
                        )

                        draw_text(
                            frame,
                            (
                                "Recording in "
                                f"{remaining:.1f}s"
                            ),
                            145,
                        )

                        if (
                            elapsed
                            >= STABILIZE_SECONDS
                        ):

                            phase = "COLLECT"

                            phase_start_time = (
                                time.perf_counter()
                            )

                    # =========================================
                    # COLLECT
                    # =========================================

                    elif phase == "COLLECT":

                        remaining = max(
                            0.0,
                            COLLECT_SECONDS
                            - elapsed,
                        )

                        draw_text(
                            frame,
                            f"LOOK {current_label}",
                            50,
                            (0, 255, 0),
                            1.1,
                        )

                        draw_text(
                            frame,
                            "RECORDING - HOLD STILL",
                            100,
                            (0, 255, 0),
                        )

                        draw_text(
                            frame,
                            f"{remaining:.1f}s",
                            145,
                        )

                        # -------------------------------------
                        # Save only valid relative features.
                        # -------------------------------------

                        if (
                            relative_features
                            is not None
                        ):

                            row = {
                                "session_id":
                                    session_id,

                                "timestamp":
                                    time.time(),

                                "label":
                                    current_label,
                            }

                            for (
                                feature_name
                            ) in HEAD_FEATURE_NAMES:

                                row[
                                    f"delta_{feature_name}"
                                ] = (
                                    relative_features[
                                        feature_name
                                    ]
                                )

                            append_sample(
                                row
                            )

                            samples_collected += 1

                            samples_per_label[
                                current_label
                            ] += 1

                        else:

                            draw_text(
                                frame,
                                "FACE NOT DETECTED",
                                195,
                                (0, 0, 255),
                            )

                        draw_text(
                            frame,
                            (
                                "Label samples: "
                                f"{samples_per_label[current_label]}"
                            ),
                            215,
                        )

                        draw_text(
                            frame,
                            (
                                "Total samples: "
                                f"{samples_collected}"
                            ),
                            255,
                        )

                        # -------------------------------------
                        # Next direction
                        # -------------------------------------

                        if (
                            elapsed
                            >= COLLECT_SECONDS
                        ):

                            current_direction_index += 1

                            phase = "PREPARE"

                            phase_start_time = (
                                time.perf_counter()
                            )

            # =================================================
            # DISPLAY
            # =================================================

            cv2.imshow(
                "NINO - Calibrated ML Data Collection",
                frame,
            )

            if (
                cv2.waitKey(1) & 0xFF
            ) == ord("q"):

                break

    # =====================================================
    # CLEANUP
    # =====================================================

    camera.release()

    cv2.destroyAllWindows()

    print()
    print("Collection finished.")

    print(
        "Dataset:",
        OUTPUT_FILE,
    )

    print(
        "Session:",
        session_id,
    )

    print(
        "Total samples:",
        samples_collected,
    )

    for label in DIRECTIONS:

        print(
            f"{label}: "
            f"{samples_per_label[label]}"
        )


if __name__ == "__main__":
    main()