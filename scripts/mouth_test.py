import cv2
import mediapipe as mp

from backend.features.mouth_features import calculate_mar
from backend.detection.landmark_indices import MOUTH


MODEL_PATH = "models/mediapipe/face_landmarker.task"


def get_mouth_points(face_landmarks):

    return [
        face_landmarks[index]
        for index in MOUTH
    ]


def main():

    BaseOptions = mp.tasks.BaseOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
    RunningMode = mp.tasks.vision.RunningMode

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

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Could not open camera")
        return

    print("Camera started")
    print("Press Q to quit")

    timestamp = 0

    with FaceLandmarker.create_from_options(options) as landmarker:

        while True:

            success, frame = camera.read()

            if not success:
                break

            frame = cv2.flip(frame, 1)

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )

            result = landmarker.detect_for_video(
                mp_image,
                timestamp
            )

            timestamp += 33

            if result.face_landmarks:

                face = result.face_landmarks[0]

                mouth_points = get_mouth_points(face)

                mar = calculate_mar(
                    mouth_points
                )

                height, width, _ = frame.shape

                for point in mouth_points:

                    x = int(point.x * width)
                    y = int(point.y * height)

                    cv2.circle(
                        frame,
                        (x, y),
                        4,
                        (255, 0, 255),
                        -1
                    )

                cv2.putText(
                    frame,
                    f"MAR: {mar:.3f}",
                    (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 0),
                    2
                )

            cv2.imshow(
                "NINO - Mouth Analysis",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()