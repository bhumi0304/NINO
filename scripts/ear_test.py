import cv2
import mediapipe as mp

from backend.features.eye_features import calculate_ear
from backend.detection.landmark_indices import LEFT_EYE, RIGHT_EYE
from backend.features.eye_state import EyeStateDetector
from backend.alerts.alarm import Alarm


MODEL_PATH = "models/mediapipe/face_landmarker.task"


def get_eye_points(face_landmarks, indices):
    """Get the required eye landmarks."""
    return [face_landmarks[index] for index in indices]


def main():

    # MediaPipe setup
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
        print("❌ Could not open camera")
        return

    print("✅ Camera started")
    print("Press Q to quit")

    timestamp = 0
    eye_detector = EyeStateDetector(
    ear_threshold=0.20
)
    alarm = Alarm()
    

    with FaceLandmarker.create_from_options(options) as landmarker:

        while True:

            success, frame = camera.read()

            if not success:
                print("❌ Could not read frame")
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

                left_eye_points = get_eye_points(
                    face,
                    LEFT_EYE
                )

                right_eye_points = get_eye_points(
                    face,
                    RIGHT_EYE
                )

                left_ear = calculate_ear(
                    left_eye_points
                )

                right_ear = calculate_ear(
                    right_eye_points
                )

                ear = (
                    left_ear +
                    right_ear
                ) / 2
                eye_state, closed_duration, event = eye_detector.update(ear)
                if eye_state == "CLOSED" and closed_duration >= 0.8:
                    alarm.start()
                else:
                    alarm.stop()
                
                
                # Display values
                cv2.putText(
                    frame,
                    f"Left EAR: {left_ear:.3f}",
                    (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"Right EAR: {right_ear:.3f}",
                    (20, 65),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )

                cv2.putText(
                    frame,
                    f"EAR: {ear:.3f}",
                    (20, 95),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 255),
                    2
                )
            # --------------------------------
# DRIVER EYE STATUS
# --------------------------------

            if eye_state == "OPEN":
                eye_color = (0, 255, 0)

            else:
                eye_color = (0, 0, 255)


            cv2.putText(
                frame,
                f"Eye State: {eye_state}",
                (20, 130),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                eye_color,
                2
            )

            cv2.putText(
                frame,
                f"Eye Closed: {closed_duration:.2f}s",
                (20, 165),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2
            )


            # --------------------------------
            # EVENT
            # --------------------------------

            if event:

                cv2.putText(
                    frame,
                    f"EVENT: {event}",
                    (20, 205),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 0, 255),
                    2
                )

                print(f"EVENT: {event}")

            # Draw eye landmarks
            height, width, _ = frame.shape

            for point in left_eye_points + right_eye_points:

                x = int(point.x * width)
                y = int(point.y * height)

                cv2.circle(
                    frame,
                    (x, y),
                    3,
                    (255, 0, 0),
                    -1
                )

            cv2.imshow(
                "Driver Safety - EAR Test",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()