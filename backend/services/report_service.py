
import csv
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# =========================================================
# SMALL HELPERS
# =========================================================

def _safe(value: Any, default: str = "—") -> str:
    if value is None:
        return default

    text = str(value).strip()
    return text if text else default


def _number(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "0.0"


def _duration(seconds: Any) -> str:
    try:
        total = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        total = 0

    minutes = total // 60
    remaining = total % 60

    return f"{minutes}:{remaining:02d}"


# =========================================================
# PDF REPORT
# =========================================================

def build_pdf_report(
    *,
    detail: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """
    Create a compact NINO drive PDF report.

    detail is expected to have:
      summary
      insights
      events
      samples

    Video/images are not embedded or stored.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary = (
        detail.get("summary")
        or
        {}
    )

    insights = (
        detail.get("insights")
        or
        {}
    )

    events = list(
        detail.get("events")
        or
        []
    )

    score = (
        insights.get(
            "driver_safety_score"
        )
        or
        {}
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="NINO Drive Safety Report",
        author="NINO",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "NinoTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=8,
    )

    subtitle_style = ParagraphStyle(
        "NinoSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#64756F"),
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    section_style = ParagraphStyle(
        "NinoSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1F6F55"),
        spaceBefore=10,
        spaceAfter=7,
    )

    body_style = ParagraphStyle(
        "NinoBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#27332F"),
    )

    small_style = ParagraphStyle(
        "NinoSmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#65756F"),
    )

    story = []

    story.append(
        Paragraph(
            "NINO — Drive Safety Report",
            title_style,
        )
    )

    story.append(
        Paragraph(
            (
                "AI-assisted driver monitoring • "
                "Computer Vision • Random Forest • "
                "Safety Analytics"
            ),
            subtitle_style,
        )
    )

    session_id = _safe(
        summary.get("session_id")
    )

    start_time = _safe(
        summary.get("start_timestamp_utc")
    )

    end_time = _safe(
        summary.get("end_timestamp_utc")
    )

    overview_data = [
        [
            "Session ID",
            session_id,
        ],
        [
            "Start",
            start_time,
        ],
        [
            "End",
            end_time,
        ],
        [
            "Duration",
            _duration(
                summary.get(
                    "drive_duration_seconds"
                )
            ),
        ],
    ]

    overview = Table(
        overview_data,
        colWidths=[
            42 * mm,
            118 * mm,
        ],
    )

    overview.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#F0F6F3"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#1F6F55"),
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (1, 0),
                    (1, -1),
                    "Helvetica",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8.5,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#DDE8E3"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(overview)

    story.append(
        Paragraph(
            "Safety Summary",
            section_style,
        )
    )

    safety_data = [
        [
            "Driver Safety Score",
            (
                f"{_number(score.get('score'), 0)}/100 "
                f"({_safe(score.get('label'))})"
            ),
        ],
        [
            "Safe / attentive",
            (
                f"{_number(summary.get('attentive_percent'))}%"
            ),
        ],
        [
            "Confirmed distraction",
            (
                f"{_number(summary.get('confirmed_distraction_percent'))}%"
            ),
        ],
        [
            "PERCLOS",
            (
                f"{_number(insights.get('perclos_percent'))}%"
            ),
        ],
        [
            "Longest distraction",
            (
                f"{_number(insights.get('longest_confirmed_distraction_seconds'))} s"
            ),
        ],
        [
            "Most common away direction",
            _safe(
                insights.get(
                    "most_common_away_direction"
                )
            ),
        ],
        [
            "Critical alerts",
            _safe(
                insights.get(
                    "critical_alert_count"
                ),
                "0",
            ),
        ],
    ]

    safety_table = Table(
        safety_data,
        colWidths=[
            70 * mm,
            90 * mm,
        ],
    )

    safety_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    8.5,
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.3,
                    colors.HexColor("#E3EAE6"),
                ),
                (
                    "ROWBACKGROUNDS",
                    (0, 0),
                    (-1, -1),
                    [
                        colors.white,
                        colors.HexColor("#FAFCFB"),
                    ],
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(safety_table)

    story.append(
        Paragraph(
            "Detected Events",
            section_style,
        )
    )

    if events:
        event_rows = [
            [
                "Time",
                "Type",
                "Message",
            ]
        ]

        for event in events[:40]:
            event_rows.append(
                [
                    (
                        f"{_number(event.get('elapsed_seconds'))} s"
                    ),
                    _safe(
                        event.get("event_type")
                    ).replace(
                        "_",
                        " ",
                    ),
                    _safe(
                        event.get("message")
                    ),
                ]
            )

        event_table = Table(
            event_rows,
            repeatRows=1,
            colWidths=[
                22 * mm,
                45 * mm,
                93 * mm,
            ],
        )

        event_table.setStyle(
            TableStyle(
                [
                    (
                        "BACKGROUND",
                        (0, 0),
                        (-1, 0),
                        colors.HexColor("#1F6F55"),
                    ),
                    (
                        "TEXTCOLOR",
                        (0, 0),
                        (-1, 0),
                        colors.white,
                    ),
                    (
                        "FONTNAME",
                        (0, 0),
                        (-1, 0),
                        "Helvetica-Bold",
                    ),
                    (
                        "FONTNAME",
                        (0, 1),
                        (-1, -1),
                        "Helvetica",
                    ),
                    (
                        "FONTSIZE",
                        (0, 0),
                        (-1, -1),
                        7.5,
                    ),
                    (
                        "GRID",
                        (0, 0),
                        (-1, -1),
                        0.25,
                        colors.HexColor("#DDE8E3"),
                    ),
                    (
                        "VALIGN",
                        (0, 0),
                        (-1, -1),
                        "TOP",
                    ),
                    (
                        "TOPPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                    (
                        "BOTTOMPADDING",
                        (0, 0),
                        (-1, -1),
                        5,
                    ),
                ]
            )
        )

        story.append(event_table)

    else:
        story.append(
            Paragraph(
                "No significant safety events were recorded.",
                body_style,
            )
        )

    story.append(
        Paragraph(
            "Interpretation",
            section_style,
        )
    )

    story.append(
        Paragraph(
            (
                "The Driver Safety Score is a transparent heuristic "
                "derived from observed distraction, drowsiness, eye "
                "closure, yawns and approximate PERCLOS. It is not an "
                "accident probability, medical diagnosis, or certified "
                "automotive safety rating."
            ),
            body_style,
        )
    )

    story.append(
        Spacer(
            1,
            6,
        )
    )

    story.append(
        Paragraph(
            (
                "Privacy: NINO stores telemetry and safety events for "
                "analytics. Video frames are processed live for inference "
                "and are not stored in the session database."
            ),
            small_style,
        )
    )

    doc.build(
        story
    )

    return output_path


# =========================================================
# CSV EXPORT
# =========================================================

def build_csv_export(
    *,
    detail: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """
    Export stored telemetry samples for one drive.
    """

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    samples = list(
        detail.get("samples")
        or
        []
    )

    fieldnames = [
        "captured_at",
        "ear",
        "mar",
        "eye_state",
        "head_direction",
        "head_direction_confidence",
        "distraction_state",
        "distraction_duration",
        "alert_state",
        "prob_forward",
        "prob_left",
        "prob_right",
        "prob_up",
        "prob_down",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for sample in samples:

            probabilities = (
                sample.get(
                    "head_direction_probabilities"
                )
                or
                {}
            )

            writer.writerow(
                {
                    "captured_at":
                        sample.get(
                            "captured_at"
                        ),

                    "ear":
                        sample.get(
                            "ear"
                        ),

                    "mar":
                        sample.get(
                            "mar"
                        ),

                    "eye_state":
                        sample.get(
                            "eye_state"
                        ),

                    "head_direction":
                        sample.get(
                            "head_direction"
                        ),

                    "head_direction_confidence":
                        sample.get(
                            "head_direction_confidence"
                        ),

                    "distraction_state":
                        sample.get(
                            "distraction_state"
                        ),

                    "distraction_duration":
                        sample.get(
                            "distraction_duration"
                        ),

                    "alert_state":
                        sample.get(
                            "alert_state"
                        ),

                    "prob_forward":
                        probabilities.get(
                            "FORWARD"
                        ),

                    "prob_left":
                        probabilities.get(
                            "LEFT"
                        ),

                    "prob_right":
                        probabilities.get(
                            "RIGHT"
                        ),

                    "prob_up":
                        probabilities.get(
                            "UP"
                        ),

                    "prob_down":
                        probabilities.get(
                            "DOWN"
                        ),
                }
            )

    return output_path
