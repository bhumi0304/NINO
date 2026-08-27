import cv2
import mediapipe as mp

from backend.features.head_pose import calculate_head_pose
from backend.features.head_state import HeadStateDetector


MODEL_PATH = "models/mediapipe/face_landmarker.task"


def main():

    # --------------------------------
    # MediaPipe setup
    # --------------------------------

    BaseOptions = mp.tasks.BaseOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = mp.tasks.vision.FaceLandmarkerOptions
    RunningMode = mp.tasks.vision.RunningMode

    options = FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=MODEL_PATH),
        running_mode=RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )

    # --------------------------------
    # Camera
    # --------------------------------

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():
        print("Could not open camera")
        return

    print("Camera started")
    print("Press Q to quit")

    # --------------------------------
    # Head detector + calibration state
    # (initialized ONCE, outside the loop)
    # --------------------------------

    head_detector = HeadStateDetector()

    calibration_frames = 0
    yaw_values = []
    pitch_values = []

    timestamp = 0
    direction = "CALIBRATING..."
    relative_yaw = 0.0
    relative_pitch = 0.0

    # --------------------------------
    # Start MediaPipe
    # --------------------------------

    with FaceLandmarker.create_from_options(options) as landmarker:

        while True:

            success, frame = camera.read()

            if not success:
                print("Could not read camera frame")
                break

            # Mirror camera
            frame = cv2.flip(frame, 1)

            height, width, _ = frame.shape

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            mp_image = mp.Image(
                image_format=mp.ImageFormat.SRGB,
                data=rgb_frame
            )

            result = landmarker.detect_for_video(mp_image, timestamp)
            timestamp += 33

            if result.face_landmarks:

                face = result.face_landmarks[0]

                yaw, pitch, roll = calculate_head_pose(face, width, height)

                # --------------------------------
                # CALIBRATION (runs only until 30 frames collected)
                # --------------------------------

                if calibration_frames < 30:

                    yaw_values.append(yaw)
                    pitch_values.append(pitch)
                    calibration_frames += 1

                    direction = "CALIBRATING..."

                    if calibration_frames == 30:

                        average_yaw = sum(yaw_values) / len(yaw_values)
                        average_pitch = sum(pitch_values) / len(pitch_values)

                        head_detector.calibrate(average_yaw, average_pitch)

                # --------------------------------
                # NORMAL DETECTION
                # --------------------------------

                else:

                    direction = head_detector.update(yaw, pitch)

                relative_yaw, relative_pitch = head_detector.get_relative_angles(yaw, pitch)

                # --------------------------------
                # Display values
                # --------------------------------

                cv2.putText(frame, f"Yaw: {yaw:.2f}", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, f"Pitch: {pitch:.2f}", (20, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, f"Roll: {roll:.2f}", (20, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, f"Direction: {direction}", (20, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, f"Rel Yaw: {relative_yaw:.2f}", (20, 180),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                cv2.putText(frame, f"Rel Pitch: {relative_pitch:.2f}", (20, 215),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            else:

                cv2.putText(frame, "NO FACE DETECTED", (20, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

            cv2.imshow("NINO - Head Pose", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    camera.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()