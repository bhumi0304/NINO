
from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import median
from typing import Any


# =========================================================
# DATE / TYPE HELPERS
# =========================================================

def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except Exception:
        return None


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


# =========================================================
# PERCLOS
# =========================================================

def compute_perclos(
    samples: list[dict[str, Any]] | None,
) -> float:
    """
    Approximate PERCLOS from stored telemetry samples.

    PERCLOS = percentage of observed time during which the
    driver's eyes are classified as closed.

    NINO stores telemetry samples rather than raw video.
    This implementation is therefore an approximate,
    time-weighted PERCLOS suitable for the academic
    prototype, not a clinical/automotive certification
    metric.

    Returns a percentage in [0, 100].
    """

    samples = list(
        samples
        or
        []
    )

    if not samples:
        return 0.0

    rows = []

    for sample in samples:
        timestamp = _parse_iso(
            sample.get(
                "captured_at"
            )
        )

        if timestamp is None:
            continue

        rows.append(
            (
                timestamp,
                sample,
            )
        )

    if not rows:
        return 0.0

    rows.sort(
        key=lambda item: item[0]
    )

    deltas = []

    for index in range(
        len(rows) - 1
    ):
        delta = (
            rows[index + 1][0]
            -
            rows[index][0]
        ).total_seconds()

        if delta > 0:
            deltas.append(
                delta
            )

    typical_interval = (
        median(
            deltas
        )
        if deltas
        else
        0.5
    )

    # Avoid one network pause making a single sample count
    # for many seconds.
    max_interval = max(
        1.0,
        typical_interval * 3.0,
    )

    total_time = 0.0
    closed_time = 0.0

    for index, (
        timestamp,
        sample,
    ) in enumerate(
        rows
    ):
        if (
            index
            <
            len(rows) - 1
        ):
            duration = (
                rows[index + 1][0]
                -
                timestamp
            ).total_seconds()

            duration = max(
                0.0,
                min(
                    duration,
                    max_interval,
                ),
            )

        else:
            duration = typical_interval

        total_time += duration

        eye_state = str(
            sample.get(
                "eye_state",
                ""
            )
        ).upper()

        eyes_closed = (
            "CLOSED"
            in
            eye_state
            or
            "DROWS"
            in
            eye_state
        )

        if eyes_closed:
            closed_time += duration

    if total_time <= 0:
        return 0.0

    return round(
        min(
            100.0,
            max(
                0.0,
                (
                    closed_time
                    /
                    total_time
                )
                *
                100.0,
            ),
        ),
        2,
    )


# =========================================================
# SAFETY SCORE
# =========================================================

def compute_safety_score(
    summary: dict[str, Any] | None,
    perclos_percent: float,
) -> dict[str, Any]:
    """
    Transparent heuristic Driver Safety Score.

    IMPORTANT:
    This is NOT accident probability and is not a validated
    medical/automotive risk model.

    Formula
    -------
    Start at 100.

    - 0.60 points for each percentage point of confirmed
      sustained distraction.
    - 8 points per drowsiness event.
    - 3 points per long eye closure.
    - 2 points per yawn.
    - PERCLOS penalty only above 10%, at 0.50 points for
      every excess percentage point.

    Final score is clipped to 0..100.
    """

    summary = (
        summary
        or
        {}
    )

    confirmed_distraction = _number(
        summary.get(
            "confirmed_distraction_percent"
        )
    )

    drowsiness_events = int(
        _number(
            summary.get(
                "drowsiness_event_count"
            )
        )
    )

    long_closures = int(
        _number(
            summary.get(
                "long_eye_closure_count"
            )
        )
    )

    yawns = int(
        _number(
            summary.get(
                "yawn_count"
            )
        )
    )

    distraction_penalty = (
        confirmed_distraction
        *
        0.60
    )

    drowsiness_penalty = (
        drowsiness_events
        *
        8.0
    )

    long_closure_penalty = (
        long_closures
        *
        3.0
    )

    yawn_penalty = (
        yawns
        *
        2.0
    )

    perclos_penalty = (
        max(
            0.0,
            perclos_percent
            -
            10.0,
        )
        *
        0.50
    )

    total_penalty = (
        distraction_penalty
        +
        drowsiness_penalty
        +
        long_closure_penalty
        +
        yawn_penalty
        +
        perclos_penalty
    )

    score = round(
        min(
            100.0,
            max(
                0.0,
                100.0
                -
                total_penalty,
            ),
        ),
        1,
    )

    if score >= 90:
        label = "Excellent"
    elif score >= 75:
        label = "Good"
    elif score >= 60:
        label = "Fair"
    else:
        label = "Needs attention"

    return {
        "score":
            score,

        "label":
            label,

        "formula_version":
            "NINO_HEURISTIC_V1",

        "is_validated_risk_probability":
            False,

        "penalties": {
            "confirmed_distraction":
                round(
                    distraction_penalty,
                    2,
                ),

            "drowsiness":
                round(
                    drowsiness_penalty,
                    2,
                ),

            "long_eye_closure":
                round(
                    long_closure_penalty,
                    2,
                ),

            "yawn":
                round(
                    yawn_penalty,
                    2,
                ),

            "perclos":
                round(
                    perclos_penalty,
                    2,
                ),
        },
    }


# =========================================================
# DRIVE INSIGHTS
# =========================================================

def compute_drive_insights(
    *,
    summary: dict[str, Any] | None,
    samples: list[dict[str, Any]] | None,
    events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """
    Build user-facing insights for a completed drive.
    """

    summary = (
        summary
        or
        {}
    )

    samples = list(
        samples
        or
        []
    )

    events = list(
        events
        or
        []
    )

    perclos_percent = (
        compute_perclos(
            samples
        )
    )

    safety_score = (
        compute_safety_score(
            summary,
            perclos_percent,
        )
    )

    longest_distraction = 0.0

    head_directions = []

    for sample in samples:

        longest_distraction = max(
            longest_distraction,
            _number(
                sample.get(
                    "distraction_duration"
                )
            ),
        )

        direction = str(
            sample.get(
                "head_direction",
                ""
            )
        ).upper()

        if direction in {
            "LEFT",
            "RIGHT",
            "UP",
            "DOWN",
        }:
            head_directions.append(
                direction
            )

    most_common_away_direction = None

    if head_directions:
        most_common_away_direction = (
            Counter(
                head_directions
            )
            .most_common(
                1
            )[0][0]
        )

    critical_alert_count = sum(
        1
        for event
        in events
        if "CRITICAL"
        in
        str(
            event.get(
                "message",
                ""
            )
        ).upper()
        or
        "CRITICAL"
        in
        str(
            event.get(
                "event_type",
                ""
            )
        ).upper()
    )

    return {
        "perclos_percent":
            perclos_percent,

        "perclos_note":
            (
                "Approximate time-weighted PERCLOS "
                "from stored telemetry samples; "
                "raw video is not stored."
            ),

        "driver_safety_score":
            safety_score,

        "longest_confirmed_distraction_seconds":
            round(
                longest_distraction,
                2,
            ),

        "most_common_away_direction":
            most_common_away_direction,

        "critical_alert_count":
            critical_alert_count,

        "privacy": {
            "video_stored":
                False,

            "telemetry_stored":
                True,
        },
    }
