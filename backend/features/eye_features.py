import math


def distance(point1, point2):
    """Calculate the distance between two facial landmarks."""
    return math.sqrt(
        (point1.x - point2.x) ** 2 +
        (point1.y - point2.y) ** 2
    )


def calculate_ear(eye_landmarks):
    """
    Calculate Eye Aspect Ratio (EAR).

    Expected landmarks:
        p1, p2, p3, p4, p5, p6

    EAR = (vertical1 + vertical2) / (2 * horizontal)
    """

    p1, p2, p3, p4, p5, p6 = eye_landmarks

    vertical_1 = distance(p2, p6)
    vertical_2 = distance(p3, p5)

    horizontal = distance(p1, p4)

    if horizontal == 0:
        return 0.0

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)

    return ear