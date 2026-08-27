import cv2
import numpy as np
import math


MODEL_POINTS = np.array([
    (0.0, 0.0, 0.0),
    (0.0, -330.0, -65.0),
    (-225.0, 170.0, -135.0),
    (225.0, 170.0, -135.0),
    (-150.0, -150.0, -125.0),
    (150.0, -150.0, -125.0)
], dtype=np.float64)


def calculate_head_pose(face_landmarks, image_width, image_height):

    image_points = np.array([
        (face_landmarks[1].x * image_width, face_landmarks[1].y * image_height),
        (face_landmarks[152].x * image_width, face_landmarks[152].y * image_height),
        (face_landmarks[33].x * image_width, face_landmarks[33].y * image_height),
        (face_landmarks[263].x * image_width, face_landmarks[263].y * image_height),
        (face_landmarks[61].x * image_width, face_landmarks[61].y * image_height),
        (face_landmarks[291].x * image_width, face_landmarks[291].y * image_height)
    ], dtype=np.float64)

    focal_length = image_width
    camera_matrix = np.array([
        [focal_length, 0, image_width / 2],
        [0, focal_length, image_height / 2],
        [0, 0, 1]
    ], dtype=np.float64)

    distortion = np.zeros((4, 1), dtype=np.float64)

    success, rotation_vector, translation_vector = cv2.solvePnP(
        MODEL_POINTS,
        image_points,
        camera_matrix,
        distortion,
        flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        return None

    rotation_matrix, _ = cv2.Rodrigues(rotation_vector)

    # -----------------------------------------------------
    # Decompose into pitch/yaw/roll using the projection
    # matrix method (more numerically stable near neutral
    # than a hand-rolled atan2 Euler extraction).
    # -----------------------------------------------------

    projection_matrix = np.hstack((rotation_matrix, translation_vector))
    euler_angles = cv2.decomposeProjectionMatrix(projection_matrix)[6]

    pitch, yaw, roll = [float(a[0]) for a in euler_angles]

    # -----------------------------------------------------
    # Unwrap pitch.
    #
    # decomposeProjectionMatrix returns pitch that flips
    # around +/-180 near the frontal position for this
    # point model, which is why "forward" was reading as
    # a large negative value (misread as DOWN).
    # -----------------------------------------------------

    if pitch < -90:
        pitch = -(pitch + 180)
    elif pitch > 90:
        pitch = 180 - pitch

    return yaw, pitch, roll