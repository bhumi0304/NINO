import cv2
import mediapipe as mp

from backend.pipeline.driver_monitor import DriverMonitor

from backend.alerts.alert_manager import (
    SafetyAlertManager,
)

from backend.data.session_logger import (
    DriveSessionLogger,
)


MODEL_PATH = "models/mediapipe/face_landmarker.task"
FPS = 30


def format_value(value, decimals=2):

    if value is None:
        return "N/A"

    return f"{value:.{decimals}f}"


def main():

    # =====================================================
    # MEDIAPIPE
    # =====================================================

    BaseOptions = mp.tasks.BaseOptions
    FaceLandmarker = mp.tasks.vision.FaceLandmarker
    FaceLandmarkerOptions = (
        mp.tasks.vision.FaceLandmarkerOptions
    )
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

    # =====================================================
    # NINO COMPONENTS
    # =====================================================

    monitor = DriverMonitor(
        fps=FPS,
        calibration_frames=30,
        drowsiness_duration=0.9,
        head_smoothing_frames=3,
    )

    alert_manager = SafetyAlertManager()

    session_logger = DriveSessionLogger(
        sample_interval_seconds=0.2
    )

    # =====================================================
    # CAMERA
    # =====================================================

    camera = cv2.VideoCapture(0)

    if not camera.isOpened():

        print("Could not open camera")
        return

    print()
    print("NINO Driver Monitoring System")
    print("=============================")
    print()
    print("S = Start Drive")
    print("E = End Drive")
    print("Q = Quit")
    print()

    timestamp = 0

    try:

        with FaceLandmarker.create_from_options(
            options
        ) as landmarker:

            while True:

                success, frame = camera.read()

                if not success:
                    break

                # Same mirrored orientation used by
                # our head-direction training.
                frame = cv2.flip(
                    frame,
                    1,
                )

                height, width, _ = frame.shape

                # =========================================
                # MEDIAPIPE
                # =========================================

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

                # =========================================
                # DRIVER MONITOR
                # =========================================

                if result.face_landmarks:

                    driver_data = monitor.update(
                        result.face_landmarks[0],
                        width,
                        height,
                    )

                else:

                    driver_data = monitor.update(
                        None,
                        width,
                        height,
                    )

                # =========================================
                # SAFETY ALERTS
                # =========================================

                alert_state = alert_manager.update(
                    driver_data
                )

                # =========================================
                # SESSION DATA LOGGING
                # =========================================

                if session_logger.active:

                    session_logger.log(
                        driver_data,
                        alert_state,
                    )

                # =========================================
                # DISPLAY
                # =========================================

                y = 30

                def draw(
                    text,
                    color=(255, 255, 255),
                ):

                    nonlocal y

                    cv2.putText(
                        frame,
                        text,
                        (20, y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.62,
                        color,
                        2,
                    )

                    y += 28

                # -----------------------------------------
                # DRIVE STATUS
                # -----------------------------------------

                if session_logger.active:

                    draw(
                        "DRIVE: ACTIVE",
                        (0, 255, 0),
                    )

                    draw(
                        "Session: "
                        + str(
                            session_logger.session_id
                        ),
                        (0, 255, 0),
                    )

                else:

                    draw(
                        "DRIVE: STOPPED - Press S",
                        (0, 255, 255),
                    )

                # -----------------------------------------
                # ALERT
                # -----------------------------------------

                if (
                    "CRITICAL" in str(alert_state)
                    or
                    "DROWSINESS" in str(alert_state)
                ):

                    alert_color = (
                        0,
                        0,
                        255,
                    )

                elif (
                    "WARNING" in str(alert_state)
                    or
                    "LOOKING_AWAY"
                    in str(alert_state)
                ):

                    alert_color = (
                        0,
                        165,
                        255,
                    )

                else:

                    alert_color = (
                        0,
                        255,
                        0,
                    )

                draw(
                    "ALERT: "
                    + str(alert_state),
                    alert_color,
                )

                # -----------------------------------------
                # FACE
                # -----------------------------------------

                if not driver_data[
                    "face_detected"
                ]:

                    draw(
                        "NO FACE DETECTED",
                        (0, 0, 255),
                    )

                else:

                    draw(
                        "EAR: "
                        + format_value(
                            driver_data["ear"]
                        )
                    )

                    draw(
                        "Eye: "
                        + str(
                            driver_data[
                                "eye_state"
                            ]
                        )
                    )

                    draw(
                        "Eye closed: "
                        + format_value(
                            driver_data[
                                "eye_closed_duration"
                            ]
                        )
                        + " s"
                    )

                    draw(
                        "Blinks: "
                        + str(
                            driver_data[
                                "blink_count"
                            ]
                        )
                    )

                    draw(
                        "MAR: "
                        + format_value(
                            driver_data["mar"]
                        )
                    )

                    draw(
                        "Yawns: "
                        + str(
                            driver_data[
                                "yawn_count"
                            ]
                        )
                    )

                    draw(
                        "Direction: "
                        + str(
                            driver_data[
                                "head_direction"
                            ]
                        )
                    )

                    draw(
                        "Direction confidence: "
                        + format_value(
                            driver_data[
                                "head_direction_confidence"
                            ]
                        )
                    )

                    draw(
                        "Distraction: "
                        + str(
                            driver_data[
                                "distraction_state"
                            ]
                        )
                    )

                    draw(
                        "Away duration: "
                        + format_value(
                            driver_data[
                                "distraction_duration"
                            ]
                        )
                        + " s"
                    )

                    draw(
                        "Distraction events: "
                        + str(
                            driver_data[
                                "distraction_event_count"
                            ]
                        )
                    )

                # =========================================
                # CONTROLS
                # =========================================

                cv2.putText(
                    frame,
                    "S: Start | E: End | Q: Quit",
                    (20, height - 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    (255, 255, 255),
                    2,
                )

                cv2.imshow(
                    "NINO - Driver Monitor",
                    frame,
                )

                key = (
                    cv2.waitKey(1)
                    &
                    0xFF
                )

                # =========================================
                # START DRIVE
                # =========================================

                if key == ord("s"):

                    if not session_logger.active:

                        session_logger.start_session()

                    else:

                        print(
                            "Drive already active."
                        )

                # =========================================
                # END DRIVE
                # =========================================

                elif key == ord("e"):

                    if session_logger.active:

                        session_logger.end_session()

                    else:

                        print(
                            "No active drive session."
                        )

                # =========================================
                # QUIT
                # =========================================

                elif key == ord("q"):

                    if session_logger.active:

                        session_logger.end_session()

                    break

    finally:

        if session_logger.active:

            session_logger.end_session()

        camera.release()

        cv2.destroyAllWindows()

        print()
        print(
            "NINO Driver Monitor stopped."
        )


if __name__ == "__main__":
    main()