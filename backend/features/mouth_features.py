import math


def distance(point1, point2):
    """Calculate distance between two facial landmarks."""

    return math.sqrt(
        (point1.x - point2.x) ** 2 +
        (point1.y - point2.y) ** 2
    )


def calculate_mar(mouth_landmarks):
    """
    Calculate Mouth Aspect Ratio (MAR).

    Expected landmarks:
        p1 = left corner
        p2 = upper inner point 1
        p3 = upper inner point 2
        p4 = right corner
        p5 = lower inner point 2
        p6 = lower inner point 1
    """

    p1, p2, p3, p4, p5, p6 = mouth_landmarks

    vertical_1 = distance(p2, p6)
    vertical_2 = distance(p3, p5)

    horizontal = distance(p1, p4)

    if horizontal == 0:
        return 0.0

    mar = (
        vertical_1 + vertical_2
    ) / (2.0 * horizontal)

    return mar