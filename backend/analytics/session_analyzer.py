import csv
import json
import statistics
import sys

from collections import Counter
from pathlib import Path


class DriveSessionAnalyzer:
    """
    Analyze one NINO drive-session CSV.

    Analytics are time-weighted using elapsed_seconds.

    Important distinction
    ---------------------
    Head away:
        Driver's head is LEFT / RIGHT / UP / DOWN.

    Confirmed distraction:
        NINO's temporal distraction detector has actually
        reached DISTRACTED_* state.

    These are deliberately NOT treated as the same thing.
    """

    DIRECTIONS = (
        "FORWARD",
        "LEFT",
        "RIGHT",
        "UP",
        "DOWN",
    )

    # =====================================================
    # SUPPORT BOTH OLD AND NEW ALERT-MANAGER NAMES
    # =====================================================

    IMPORTANT_ALERTS = (
        # Older/current names
        "DROWSINESS_ALERT",
        "DISTRACTION_ALERT",

        # New multi-stage names
        "EARLY_EYE_WARNING",
        "CRITICAL_DROWSINESS_ALERT",
        "EARLY_DISTRACTION_WARNING",
        "CRITICAL_DISTRACTION_ALERT",
    )

    def __init__(
        self,
        csv_path,
        summary_directory="data/session_summaries",
    ):

        self.csv_path = Path(
            csv_path
        )

        self.summary_directory = Path(
            summary_directory
        )

        self.summary_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not self.csv_path.exists():

            raise FileNotFoundError(
                "Drive session not found: "
                f"{self.csv_path}"
            )

        self.rows = []

    # =====================================================
    # SAFE CONVERSION HELPERS
    # =====================================================

    @staticmethod
    def _float(
        value,
        default=0.0,
    ):

        try:

            if value in (
                None,
                "",
                "None",
            ):

                return default

            return float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return default

    @staticmethod
    def _int(
        value,
        default=0,
    ):

        try:

            if value in (
                None,
                "",
                "None",
            ):

                return default

            return int(
                float(value)
            )

        except (
            TypeError,
            ValueError,
        ):

            return default

    @staticmethod
    def _bool(
        value,
    ):

        if isinstance(
            value,
            bool,
        ):

            return value

        return (
            str(value)
            .strip()
            .lower()
            in (
                "true",
                "1",
                "yes",
            )
        )

    # =====================================================
    # LOAD CSV
    # =====================================================

    def load(
        self,
    ):

        with open(
            self.csv_path,
            "r",
            newline="",
            encoding="utf-8",
        ) as file:

            reader = csv.DictReader(
                file
            )

            self.rows = list(
                reader
            )

        if not self.rows:

            raise ValueError(
                "Drive session CSV contains no data rows."
            )

        self.rows.sort(
            key=lambda row:
                self._float(
                    row.get(
                        "elapsed_seconds"
                    )
                )
        )

        return self.rows

    # =====================================================
    # ESTIMATE FINAL SAMPLE INTERVAL
    # =====================================================

    def _estimate_tail_interval(
        self,
    ):

        gaps = []

        for index in range(
            len(self.rows) - 1
        ):

            current_time = (
                self._float(
                    self.rows[
                        index
                    ].get(
                        "elapsed_seconds"
                    )
                )
            )

            next_time = (
                self._float(
                    self.rows[
                        index + 1
                    ].get(
                        "elapsed_seconds"
                    )
                )
            )

            gap = (
                next_time
                -
                current_time
            )

            if (
                gap > 0.02
                and
                gap < 1.0
            ):

                gaps.append(
                    gap
                )

        if not gaps:

            return 0.2

        return float(
            statistics.median(
                gaps
            )
        )

    # =====================================================
    # TIME INTERVALS
    # =====================================================

    def _time_intervals(
        self,
    ):

        tail_interval = (
            self._estimate_tail_interval()
        )

        intervals = []

        for index, row in enumerate(
            self.rows
        ):

            current_time = (
                self._float(
                    row.get(
                        "elapsed_seconds"
                    )
                )
            )

            if (
                index
                <
                len(self.rows) - 1
            ):

                next_time = (
                    self._float(
                        self.rows[
                            index + 1
                        ].get(
                            "elapsed_seconds"
                        )
                    )
                )

                duration = max(
                    0.0,
                    next_time
                    -
                    current_time,
                )

            else:

                duration = (
                    tail_interval
                )

            # Prevent a large pause from dominating
            # analytics.
            duration = min(
                duration,
                1.0,
            )

            intervals.append(
                (
                    row,
                    duration,
                )
            )

        return intervals

    # =====================================================
    # MAXIMUM CUMULATIVE COUNTER
    # =====================================================

    def _max_counter(
        self,
        column,
    ):

        return max(
            self._int(
                row.get(
                    column
                )
            )
            for row
            in self.rows
        )

    # =====================================================
    # MAIN ANALYSIS
    # =====================================================

    def analyze(
        self,
    ):

        if not self.rows:

            self.load()

        intervals = (
            self._time_intervals()
        )

        # =================================================
        # SESSION INFORMATION
        # =================================================

        session_id = (
            self.rows[0].get(
                "session_id"
            )
        )

        start_timestamp = (
            self.rows[0].get(
                "timestamp_utc"
            )
        )

        end_timestamp = (
            self.rows[-1].get(
                "timestamp_utc"
            )
        )

        first_elapsed = (
            self._float(
                self.rows[0].get(
                    "elapsed_seconds"
                )
            )
        )

        last_elapsed = (
            self._float(
                self.rows[-1].get(
                    "elapsed_seconds"
                )
            )
        )

        drive_duration = max(
            0.0,
            last_elapsed
            -
            first_elapsed,
        )

        # =================================================
        # TIME ACCUMULATORS
        # =================================================

        face_visible_seconds = 0.0

        no_face_seconds = 0.0

        attentive_seconds = 0.0

        head_away_seconds = 0.0

        confirmed_distraction_seconds = (
            0.0
        )

        drowsy_seconds = 0.0

        direction_seconds = {
            direction: 0.0
            for direction
            in self.DIRECTIONS
        }

        # =================================================
        # PROCESS TIME-WEIGHTED STATE
        # =================================================

        for (
            row,
            duration,
        ) in intervals:

            face_detected = (
                self._bool(
                    row.get(
                        "face_detected"
                    )
                )
            )

            # ---------------------------------------------
            # NO FACE
            # ---------------------------------------------

            if not face_detected:

                no_face_seconds += (
                    duration
                )

                continue

            face_visible_seconds += (
                duration
            )

            # ---------------------------------------------
            # HEAD DIRECTION
            # ---------------------------------------------

            direction = str(
                row.get(
                    "head_direction",
                    "UNKNOWN",
                )
            )

            if direction in (
                self.DIRECTIONS
            ):

                direction_seconds[
                    direction
                ] += duration

            head_is_away = (
                direction
                in
                (
                    "LEFT",
                    "RIGHT",
                    "UP",
                    "DOWN",
                )
            )

            if head_is_away:

                head_away_seconds += (
                    duration
                )

            # ---------------------------------------------
            # DROWSINESS
            # ---------------------------------------------

            is_drowsy = (
                self._bool(
                    row.get(
                        "is_drowsy"
                    )
                )
            )

            if is_drowsy:

                drowsy_seconds += (
                    duration
                )

            # ---------------------------------------------
            # CONFIRMED DISTRACTION
            # ---------------------------------------------

            distraction_state = str(
                row.get(
                    "distraction_state",
                    "UNKNOWN",
                )
            )

            confirmed_distracted = (
                distraction_state.startswith(
                    "DISTRACTED_"
                )
            )

            if confirmed_distracted:

                confirmed_distraction_seconds += (
                    duration
                )

            # ---------------------------------------------
            # ATTENTIVE TIME
            #
            # Operational NINO definition:
            #
            # face visible
            # NOT drowsy
            # NOT confirmed distracted
            #
            # A brief normal head turn is therefore not
            # automatically treated as unsafe.
            # ---------------------------------------------

            if (
                not is_drowsy
                and
                not confirmed_distracted
            ):

                attentive_seconds += (
                    duration
                )

        # =================================================
        # PERCENTAGE HELPER
        # =================================================

        def percentage(
            seconds,
        ):

            if (
                face_visible_seconds
                <= 0
            ):

                return 0.0

            return (
                seconds
                /
                face_visible_seconds
                *
                100.0
            )

        attentive_percent = (
            percentage(
                attentive_seconds
            )
        )

        head_away_percent = (
            percentage(
                head_away_seconds
            )
        )

        confirmed_distraction_percent = (
            percentage(
                confirmed_distraction_seconds
            )
        )

        drowsy_percent = (
            percentage(
                drowsy_seconds
            )
        )

        # =================================================
        # HEAD-DIRECTION DISTRIBUTION
        # =================================================

        direction_percentages = {}

        for direction in (
            self.DIRECTIONS
        ):

            direction_percentages[
                direction
            ] = percentage(
                direction_seconds[
                    direction
                ]
            )

        # =================================================
        # ALERT COUNTS
        #
        # Count actual alert-emission states.
        # =================================================

        alert_counter = Counter()

        for row in self.rows:

            alert_state = str(
                row.get(
                    "alert_state",
                    ""
                )
            )

            if alert_state in (
                self.IMPORTANT_ALERTS
            ):

                alert_counter[
                    alert_state
                ] += 1

        # =================================================
        # LOGGER REASONS
        # =================================================

        log_reason_counter = Counter(
            str(
                row.get(
                    "log_reason",
                    "MISSING",
                )
            )
            for row
            in self.rows
        )

        # =================================================
        # SUMMARY
        # =================================================

        summary = {
            # =============================================
            # SESSION
            # =============================================

            "session_id":
                session_id,

            "source_csv":
                str(
                    self.csv_path
                ),

            "start_timestamp_utc":
                start_timestamp,

            "end_timestamp_utc":
                end_timestamp,

            "drive_duration_seconds":
                round(
                    drive_duration,
                    2,
                ),

            "logged_rows":
                len(
                    self.rows
                ),

            # =============================================
            # VISIBILITY
            # =============================================

            "face_visible_seconds":
                round(
                    face_visible_seconds,
                    2,
                ),

            "no_face_seconds":
                round(
                    no_face_seconds,
                    2,
                ),

            # =============================================
            # ATTENTION / SAFETY
            # =============================================

            "attentive_seconds":
                round(
                    attentive_seconds,
                    2,
                ),

            "attentive_percent":
                round(
                    attentive_percent,
                    2,
                ),

            # =============================================
            # RAW HEAD-AWAY BEHAVIOUR
            # =============================================

            "head_away_seconds":
                round(
                    head_away_seconds,
                    2,
                ),

            "head_away_percent":
                round(
                    head_away_percent,
                    2,
                ),

            # =============================================
            # CONFIRMED DISTRACTION
            # =============================================

            "confirmed_distraction_seconds":
                round(
                    confirmed_distraction_seconds,
                    2,
                ),

            "confirmed_distraction_percent":
                round(
                    confirmed_distraction_percent,
                    2,
                ),

            "distraction_event_count":
                self._max_counter(
                    "distraction_event_count"
                ),

            # =============================================
            # DROWSINESS
            # =============================================

            "drowsy_seconds":
                round(
                    drowsy_seconds,
                    2,
                ),

            "drowsy_percent":
                round(
                    drowsy_percent,
                    2,
                ),

            "blink_count":
                self._max_counter(
                    "blink_count"
                ),

            "long_eye_closure_count":
                self._max_counter(
                    "long_eye_closure_count"
                ),

            "drowsiness_event_count":
                self._max_counter(
                    "drowsiness_event_count"
                ),

            # =============================================
            # MOUTH
            # =============================================

            "mouth_movement_count":
                self._max_counter(
                    "mouth_movement_count"
                ),

            "yawn_count":
                self._max_counter(
                    "yawn_count"
                ),

            # =============================================
            # HEAD DIRECTION
            # =============================================

            "head_direction_seconds": {
                direction:
                    round(
                        seconds,
                        2,
                    )
                for (
                    direction,
                    seconds,
                ) in direction_seconds.items()
            },

            "head_direction_percent": {
                direction:
                    round(
                        value,
                        2,
                    )
                for (
                    direction,
                    value,
                ) in direction_percentages.items()
            },

            # =============================================
            # ALERTS
            # =============================================

            "alerts": {
                alert:
                    alert_counter.get(
                        alert,
                        0,
                    )
                for alert
                in self.IMPORTANT_ALERTS
            },

            "total_safety_alerts":
                sum(
                    alert_counter.values()
                ),

            # =============================================
            # DATA QUALITY
            # =============================================

            "log_reason_counts":
                dict(
                    log_reason_counter
                ),
        }

        return summary

    # =====================================================
    # SAVE JSON SUMMARY
    # =====================================================

    def save_summary(
        self,
        summary,
    ):

        filename = (
            self.csv_path.stem
            +
            "_summary.json"
        )

        output_path = (
            self.summary_directory
            /
            filename
        )

        with open(
            output_path,
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                summary,
                file,
                indent=4,
            )

        return output_path


# =========================================================
# FIND LATEST DRIVE
# =========================================================

def find_latest_drive(
    directory="data/drive_sessions",
):

    directory = Path(
        directory
    )

    csv_files = list(
        directory.glob(
            "drive_*.csv"
        )
    )

    if not csv_files:

        raise FileNotFoundError(
            "No drive-session CSV files found."
        )

    return max(
        csv_files,
        key=lambda path:
            path.stat().st_mtime,
    )


# =========================================================
# PRINT SUMMARY
# =========================================================

def print_summary(
    summary,
):

    print()
    print("=" * 64)

    print(
        "NINO DRIVE SESSION SUMMARY"
    )

    print("=" * 64)

    print()

    print(
        "Session:",
        summary[
            "session_id"
        ],
    )

    print(
        "Duration:",
        summary[
            "drive_duration_seconds"
        ],
        "seconds",
    )

    print(
        "Logged rows:",
        summary[
            "logged_rows"
        ],
    )

    # =====================================================
    # ATTENTION
    # =====================================================

    print()
    print("ATTENTION / SAFETY")
    print("-" * 32)

    print(
        "Attentive:",
        f"{summary['attentive_percent']:.2f}%",
    )

    print(
        "Head away:",
        f"{summary['head_away_percent']:.2f}%",
    )

    print(
        "Confirmed distraction:",
        (
            f"{summary['confirmed_distraction_percent']:.2f}%"
        ),
    )

    print(
        "Confirmed distraction time:",
        summary[
            "confirmed_distraction_seconds"
        ],
        "sec",
    )

    print(
        "No face:",
        summary[
            "no_face_seconds"
        ],
        "sec",
    )

    # =====================================================
    # DROWSINESS
    # =====================================================

    print()
    print("DROWSINESS")
    print("-" * 32)

    print(
        "Blinks:",
        summary[
            "blink_count"
        ],
    )

    print(
        "Long closures:",
        summary[
            "long_eye_closure_count"
        ],
    )

    print(
        "Drowsiness events:",
        summary[
            "drowsiness_event_count"
        ],
    )

    print(
        "Drowsy time:",
        summary[
            "drowsy_seconds"
        ],
        "sec",
    )

    # =====================================================
    # MOUTH
    # =====================================================

    print()
    print("MOUTH")
    print("-" * 32)

    print(
        "Possible yawns:",
        summary[
            "yawn_count"
        ],
    )

    # =====================================================
    # DISTRACTION
    # =====================================================

    print()
    print("DISTRACTION")
    print("-" * 32)

    print(
        "Distraction events:",
        summary[
            "distraction_event_count"
        ],
    )

    # =====================================================
    # HEAD DIRECTION
    # =====================================================

    print()
    print("HEAD DIRECTION")
    print("-" * 32)

    for (
        direction,
        value,
    ) in summary[
        "head_direction_percent"
    ].items():

        print(
            f"{direction:<8}: "
            f"{value:.2f}%"
        )

    # =====================================================
    # ALERTS
    # =====================================================

    print()
    print("SAFETY ALERTS")
    print("-" * 32)

    displayed_alerts = 0

    for (
        alert,
        count,
    ) in summary[
        "alerts"
    ].items():

        if count > 0:

            displayed_alerts += 1

            print(
                f"{alert:<32}: "
                f"{count}"
            )

    if displayed_alerts == 0:

        print(
            "No safety alerts."
        )

    print()

    print(
        "Total safety alerts:",
        summary[
            "total_safety_alerts"
        ],
    )

    # =====================================================
    # LOGGER HEALTH
    # =====================================================

    print()
    print("LOGGER")
    print("-" * 32)

    for (
        reason,
        count,
    ) in summary[
        "log_reason_counts"
    ].items():

        print(
            f"{reason:<28}: "
            f"{count}"
        )

    print()


# =========================================================
# MAIN
# =========================================================

def main():

    # User may optionally provide a specific CSV:
    #
    # python -m backend.analytics.session_analyzer path.csv
    #
    # Otherwise use newest drive.

    if len(
        sys.argv
    ) > 1:

        csv_path = Path(
            sys.argv[1]
        )

    else:

        csv_path = (
            find_latest_drive()
        )

    print()
    print(
        "Analyzing:",
        csv_path,
    )

    analyzer = (
        DriveSessionAnalyzer(
            csv_path
        )
    )

    summary = (
        analyzer.analyze()
    )

    output_path = (
        analyzer.save_summary(
            summary
        )
    )

    print_summary(
        summary
    )

    print(
        "Summary saved:"
    )

    print(
        output_path
    )

    print()


if __name__ == "__main__":
    main()