import cv2
import mediapipe as mp

from backend.ml.head_direction_predictor import (
    HeadDirectionPredictor,
)


MODEL_PATH = (
    "models/mediapipe/"
    "face_landmarker.task"
)


def main():

    # =====================================================
    # MEDIAPIPE SETUP
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
    # LOAD NINO ML HEAD-DIRECTION MODEL
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
    print("NINO ML Head Direction Test")
    print("---------------------------")
    print()
    print("Test these positions slowly:")
    print("1. FORWARD")
    print("2. LEFT")
    print("3. RIGHT")
    print("4. UP")
    print("5. DOWN")
    print()
    print("Predictions will also be printed")
    print("in the terminal.")
    print()
    print("Press Q to quit.")
    print()

    timestamp = 0

    # Used so terminal does not print the same
    # prediction 30 times every second.
    last_direction = None

    # =====================================================
    # MEDIAPIPE LOOP
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

            # Keep this consistent with the camera
            # orientation used during dataset collection.
            frame = cv2.flip(
                frame,
                1,
            )

            # -------------------------------------------------
            # OpenCV uses BGR.
            # MediaPipe expects RGB.
            # -------------------------------------------------

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB,
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame,
            )

            # -------------------------------------------------
            # Detect face landmarks
            # -------------------------------------------------

            result = landmarker.detect_for_video(
                mp_image,
                timestamp,
            )

            timestamp += 33

            # =================================================
            # FACE DETECTED
            # =================================================

            if result.face_landmarks:

                face_landmarks = (
                    result.face_landmarks[0]
                )

                prediction = (
                    predictor.predict_with_confidence(
                        face_landmarks
                    )
                )

                if prediction is not None:

                    direction = (
                        prediction[
                            "direction"
                        ]
                    )

                    confidence = (
                        prediction[
                            "confidence"
                        ]
                    )

                    probabilities = (
                        prediction[
                            "probabilities"
                        ]
                    )

                    # =========================================
                    # TERMINAL OUTPUT
                    #
                    # Print only when predicted direction
                    # changes.
                    # =========================================

                    if (
                        direction
                        != last_direction
                    ):

                        print()
                        print(
                            "Prediction:",
                            direction,
                        )

                        print(
                            "Confidence:",
                            f"{confidence:.2f}",
                        )

                        print(
                            "Probabilities:"
                        )

                        for label in [
                            "FORWARD",
                            "LEFT",
                            "RIGHT",
                            "UP",
                            "DOWN",
                        ]:

                            probability = (
                                probabilities.get(
                                    label,
                                    0.0,
                                )
                            )

                            print(
                                f"  {label:<8}: "
                                f"{probability:.2f}"
                            )

                        last_direction = (
                            direction
                        )

                    # =========================================
                    # CAMERA DISPLAY
                    # =========================================

                    cv2.putText(
                        frame,
                        (
                            "Prediction: "
                            f"{direction}"
                        ),
                        (20, 45),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1.0,
                        (0, 255, 0),
                        2,
                    )

                    cv2.putText(
                        frame,
                        (
                            "Confidence: "
                            f"{confidence:.2f}"
                        ),
                        (20, 85),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (255, 255, 0),
                        2,
                    )

                    # =========================================
                    # SHOW ALL CLASS PROBABILITIES
                    # =========================================

                    y = 135

                    display_order = [
                        "FORWARD",
                        "LEFT",
                        "RIGHT",
                        "UP",
                        "DOWN",
                    ]

                    for label in display_order:

                        probability = (
                            probabilities.get(
                                label,
                                0.0,
                            )
                        )

                        text = (
                            f"{label:<7}: "
                            f"{probability:.2f}"
                        )

                        cv2.putText(
                            frame,
                            text,
                            (20, y),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.65,
                            (255, 255, 255),
                            2,
                        )

                        y += 32

                else:

                    cv2.putText(
                        frame,
                        "FEATURE EXTRACTION FAILED",
                        (20, 45),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 0, 255),
                        2,
                    )

            # =================================================
            # NO FACE
            # =================================================

            else:

                cv2.putText(
                    frame,
                    "NO FACE DETECTED",
                    (20, 45),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 0, 255),
                    2,
                )

            # =================================================
            # DISPLAY WINDOW
            # =================================================

            cv2.imshow(
                "NINO - ML Head Direction",
                frame,
            )

            # Q = quit
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
    print(
        "NINO ML head-direction test stopped."
    )


if __name__ == "__main__":
    main()