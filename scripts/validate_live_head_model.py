import time
from collections import Counter

import cv2
import mediapipe as mp
import numpy as np

from backend.ml.head_direction_predictor import (
    HeadDirectionPredictor,
)


MODEL_PATH = (
    "models/mediapipe/"
    "face_landmarker.task"
)


DIRECTIONS = [
    "FORWARD",
    "LEFT",
    "RIGHT",
    "UP",
    "DOWN",
]


PREPARE_SECONDS = 2.0
STABILIZE_SECONDS = 1.0

# Instead of testing for a fixed number of seconds,
# require this many VALID model predictions.
REQUIRED_VALID_SAMPLES = 45

# Safety timeout so the test cannot get stuck forever.
MAX_COLLECTION_SECONDS = 8.0


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
    # MODEL
    # =====================================================

    predictor = HeadDirectionPredictor()

    # =====================================================
    # CAMERA
    # =====================================================

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("Could not open camera")
        return

    print()
    print("NINO Robust Live Head Validation")
    print("--------------------------------")
    print()
    print("Follow the instructions on screen.")
    print()
    print(
        "IMPORTANT: LEFT and RIGHT mean YOUR left "
        "and YOUR right."
    )
    print()
    print("Press Q to stop.")
    print()

    timestamp = 0

    direction_index = 0

    phase = "PREPARE"

    phase_start = time.perf_counter()

    probability_samples = []

    prediction_labels = []

    final_results = []

    # =====================================================
    # LOOP
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

            # Must stay consistent with training.
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
                timestamp,
            )

            timestamp += 33

            # =================================================
            # FINISHED
            # =================================================

            if direction_index >= len(
                DIRECTIONS
            ):

                draw_text(
                    frame,
                    "VALIDATION COMPLETE",
                    50,
                    (0, 255, 0),
                    1.0,
                )

                draw_text(
                    frame,
                    "Press Q to exit",
                    100,
                )

            else:

                target = DIRECTIONS[
                    direction_index
                ]

                elapsed = (
                    time.perf_counter()
                    -
                    phase_start
                )

                # =============================================
                # PREPARE
                # =============================================

                if phase == "PREPARE":

                    remaining = max(
                        0.0,
                        PREPARE_SECONDS
                        -
                        elapsed,
                    )

                    draw_text(
                        frame,
                        "GET READY",
                        45,
                        (0, 255, 255),
                    )

                    draw_text(
                        frame,
                        f"LOOK {target}",
                        95,
                        (0, 255, 255),
                        1.1,
                    )

                    draw_text(
                        frame,
                        (
                            "YOUR "
                            f"{target}"
                            if target
                            in ("LEFT", "RIGHT")
                            else target
                        ),
                        135,
                        (0, 255, 255),
                    )

                    draw_text(
                        frame,
                        f"Move now: {remaining:.1f}s",
                        180,
                    )

                    if (
                        elapsed
                        >= PREPARE_SECONDS
                    ):

                        phase = "STABILIZE"

                        phase_start = (
                            time.perf_counter()
                        )

                # =============================================
                # STABILIZE
                # =============================================

                elif phase == "STABILIZE":

                    remaining = max(
                        0.0,
                        STABILIZE_SECONDS
                        -
                        elapsed,
                    )

                    draw_text(
                        frame,
                        f"LOOK {target}",
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
                            "Testing in "
                            f"{remaining:.1f}s"
                        ),
                        145,
                    )

                    if (
                        elapsed
                        >= STABILIZE_SECONDS
                    ):

                        probability_samples = []

                        prediction_labels = []

                        phase = "COLLECT"

                        phase_start = (
                            time.perf_counter()
                        )

                # =============================================
                # COLLECT VALID MODEL OUTPUTS
                # =============================================

                elif phase == "COLLECT":

                    valid_count = len(
                        probability_samples
                    )

                    draw_text(
                        frame,
                        f"LOOK {target}",
                        45,
                        (0, 255, 0),
                        1.1,
                    )

                    draw_text(
                        frame,
                        "HOLD STILL",
                        90,
                        (0, 255, 0),
                    )

                    draw_text(
                        frame,
                        (
                            "Valid samples: "
                            f"{valid_count}/"
                            f"{REQUIRED_VALID_SAMPLES}"
                        ),
                        135,
                    )

                    face_detected = bool(
                        result.face_landmarks
                    )

                    if face_detected:

                        prediction = (
                            predictor
                            .predict_with_confidence(
                                result.face_landmarks[0]
                            )
                        )

                        if prediction is not None:

                            prediction_labels.append(
                                prediction[
                                    "direction"
                                ]
                            )

                            probability_samples.append(
                                [
                                    prediction[
                                        "probabilities"
                                    ].get(
                                        label,
                                        0.0,
                                    )
                                    for label
                                    in DIRECTIONS
                                ]
                            )

                            draw_text(
                                frame,
                                (
                                    "Current prediction: "
                                    f"{prediction['direction']}"
                                ),
                                185,
                            )

                            draw_text(
                                frame,
                                (
                                    "Current confidence: "
                                    f"{prediction['confidence']:.2f}"
                                ),
                                225,
                            )

                    else:

                        draw_text(
                            frame,
                            "FACE NOT DETECTED",
                            185,
                            (0, 0, 255),
                        )

                    # =========================================
                    # SUCCESSFUL SAMPLE COLLECTION
                    # =========================================

                    if (
                        len(probability_samples)
                        >= REQUIRED_VALID_SAMPLES
                    ):

                        probabilities = np.array(
                            probability_samples,
                            dtype=np.float64,
                        )

                        average_probabilities = (
                            np.mean(
                                probabilities,
                                axis=0,
                            )
                        )

                        best_index = int(
                            np.argmax(
                                average_probabilities
                            )
                        )

                        average_prediction = (
                            DIRECTIONS[
                                best_index
                            ]
                        )

                        average_confidence = float(
                            average_probabilities[
                                best_index
                            ]
                        )

                        votes = Counter(
                            prediction_labels
                        )

                        majority_prediction = (
                            votes.most_common(1)[0][0]
                        )

                        majority_votes = (
                            votes[
                                majority_prediction
                            ]
                        )

                        majority_ratio = (
                            majority_votes
                            /
                            len(prediction_labels)
                        )

                        result_summary = {
                            "target":
                                target,

                            "predicted":
                                average_prediction,

                            "confidence":
                                average_confidence,

                            "majority_prediction":
                                majority_prediction,

                            "majority_ratio":
                                majority_ratio,

                            "valid_samples":
                                len(
                                    probability_samples
                                ),

                            "probabilities": {
                                label:
                                    float(
                                        average_probabilities[
                                            index
                                        ]
                                    )
                                for index, label
                                in enumerate(
                                    DIRECTIONS
                                )
                            },
                        }

                        final_results.append(
                            result_summary
                        )

                        print()
                        print(
                            "Target:",
                            target,
                        )

                        print(
                            "Average-probability prediction:",
                            average_prediction,
                        )

                        print(
                            "Average confidence:",
                            f"{average_confidence:.3f}",
                        )

                        print(
                            "Majority prediction:",
                            majority_prediction,
                        )

                        print(
                            "Majority ratio:",
                            f"{majority_ratio:.3f}",
                        )

                        print(
                            "Valid samples:",
                            len(
                                probability_samples
                            ),
                        )

                        print(
                            "Average probabilities:"
                        )

                        for (
                            label,
                            probability,
                        ) in result_summary[
                            "probabilities"
                        ].items():

                            print(
                                f"  {label:<8}: "
                                f"{probability:.3f}"
                            )

                        direction_index += 1

                        phase = "PREPARE"

                        phase_start = (
                            time.perf_counter()
                        )

                    # =========================================
                    # TIMEOUT
                    # =========================================

                    elif (
                        elapsed
                        >= MAX_COLLECTION_SECONDS
                    ):

                        print()
                        print(
                            f"Target: {target}"
                        )

                        print(
                            "TEST FAILED: only "
                            f"{len(probability_samples)} "
                            "valid samples were collected."
                        )

                        print(
                            "Retrying the same direction."
                        )

                        # Important:
                        # DO NOT advance to the next direction.
                        phase = "PREPARE"

                        phase_start = (
                            time.perf_counter()
                        )

            # =================================================
            # WINDOW
            # =================================================

            cv2.imshow(
                "NINO - Robust ML Validation",
                frame,
            )

            if (
                cv2.waitKey(1)
                &
                0xFF
            ) == ord("q"):

                break

    camera.release()

    cv2.destroyAllWindows()

    # =====================================================
    # FINAL RESULTS
    # =====================================================

    print()
    print("=" * 70)
    print("FINAL ROBUST LIVE VALIDATION")
    print("=" * 70)

    correct = 0

    for result in final_results:

        is_correct = (
            result["target"]
            ==
            result["predicted"]
        )

        if is_correct:
            correct += 1

        status = (
            "PASS"
            if is_correct
            else "FAIL"
        )

        print(
            f"{result['target']:<8}"
            f" -> "
            f"{result['predicted']:<8}"
            f" avg_conf="
            f"{result['confidence']:.3f}"
            f" majority="
            f"{result['majority_prediction']:<8}"
            f" vote_ratio="
            f"{result['majority_ratio']:.3f}"
            f"  {status}"
        )

    print()

    print(
        "Correct poses:",
        f"{correct}/{len(final_results)}"
    )

    print()


if __name__ == "__main__":
    main()