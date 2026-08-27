import time

from backend.features.distraction import DistractionDetector


def main():

    detector = DistractionDetector(
        required_duration=1.5,
        fps=30
    )

    print("Testing distraction detector")
    print()

    # Simulate looking left
    for frame in range(60):

        state = detector.update(
            "LOOKING_LEFT"
        )

        if frame % 10 == 0:
            print(
                f"Frame {frame}: {state}"
            )

        time.sleep(1 / 30)

    print()
    print("Returning to forward")

    for frame in range(30):

        state = detector.update(
            "FORWARD"
        )

        if frame % 10 == 0:
            print(
                f"Frame {frame}: {state}"
            )

        time.sleep(1 / 30)


if __name__ == "__main__":
    main()