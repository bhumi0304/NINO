import cv2
import mediapipe as mp

MODEL_PATH = "models/mediapipe/face_landmarker.task"

BaseOptions = mp.tasks.BaseOptions
FaceLandmarker = mp.tasks.vision.FaceLandmarker
FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
RunningMode = mp.tasks.vision.RunningMode


def main():
    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
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

    frame_timestamp = 0

    with FaceLandmarker.create_from_options(options) as landmarker:

        while True:
            success, frame = camera.read()

            if not success:
                print("❌ Could not read frame")
                break

            frame = cv2.flip(frame, 1)

            # OpenCV uses BGR, MediaPipe expects RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )

            result = landmarker.detect_for_video(
                mp_image,
                frame_timestamp
            )

            frame_timestamp += 33

            # Draw facial landmarks
            if result.face_landmarks:

                for face_landmarks in result.face_landmarks:

                    height, width, _ = frame.shape

                    for landmark in face_landmarks:

                        x = int(landmark.x * width)
                        y = int(landmark.y * height)

                        cv2.circle(
                            frame,
                            (x, y),
                            1,
                            (0, 255, 0),
                            -1
                        )

            cv2.imshow(
                "Driver Safety - Face Landmarks",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()