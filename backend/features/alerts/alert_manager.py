
import os
import subprocess
import threading
import time


class SafetyAlertManager:
    """
    NINO safety alert engine.

    Design goals
    ------------
    1. Use real elapsed time rather than frame counts.
    2. Require sustained unsafe states before warning.
    3. Tolerate short ML / landmark flicker.
    4. Emit at most one early + one critical escalation
       per continuous unsafe episode.
    5. Enforce per-alert cooldown across episodes to prevent
       alert fatigue.
    6. Keep speech non-blocking.

    Default timing
    --------------
    Eye closure:
        early warning     : 0.8 s
        critical warning  : 1.5 s

    Head distraction:
        early warning     : 1.2 s
        critical warning  : 2.0 s

    Recovery grace:
        eye open          : 0.35 s
        looking forward   : 0.50 s

    Per-alert repeat cooldown:
        5.0 s
    """

    def __init__(
        self,
        eye_early_duration=0.80,
        eye_critical_duration=1.50,
        distraction_early_duration=1.20,
        distraction_critical_duration=2.00,
        eye_recovery_grace=0.35,
        direction_recovery_grace=0.50,
        alert_cooldown=5.0,
        speech_cooldown=5.0,
    ):
        self.eye_early_duration = float(
            eye_early_duration
        )
        self.eye_critical_duration = float(
            eye_critical_duration
        )

        self.distraction_early_duration = float(
            distraction_early_duration
        )
        self.distraction_critical_duration = float(
            distraction_critical_duration
        )

        self.eye_recovery_grace = float(
            eye_recovery_grace
        )
        self.direction_recovery_grace = float(
            direction_recovery_grace
        )

        self.alert_cooldown = float(
            alert_cooldown
        )
        self.speech_cooldown = float(
            speech_cooldown
        )

        # Continuous unsafe-state timers.
        self.eye_closed_started_at = None
        self.looking_away_started_at = None

        # Recovery timers. These prevent one clean frame from
        # resetting an entire episode.
        self.eye_open_started_at = None
        self.forward_started_at = None

        # 0 = normal, 1 = early, 2 = critical.
        self.eye_alert_level = 0
        self.distraction_alert_level = 0

        # Event counters count confirmed critical episodes,
        # not every repeated alert frame.
        self.drowsiness_event_count = 0
        self.distraction_event_count = 0

        # Cooldown memory for actual alert emissions.
        self.last_alert_emitted_at = {}
        self.last_spoken_at = {}

        # Non-blocking Windows speech.
        self._speech_lock = threading.Lock()
        self._speech_process = None
        self._speech_priority = 0

    # =====================================================
    # SPEECH
    # =====================================================

    def _speak(
        self,
        text,
        key,
        priority=1,
    ):
        if os.name != "nt":
            return

        now = time.monotonic()

        last_time = self.last_spoken_at.get(
            key,
            0.0,
        )

        if (
            now - last_time
            <
            self.speech_cooldown
        ):
            return

        escaped_text = (
            text.replace(
                "'",
                "''",
            )
        )

        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$voice = New-Object "
            "System.Speech.Synthesis.SpeechSynthesizer; "
            "$voice.Volume = 100; "
            "$voice.Rate = 1; "
            f"$voice.Speak('{escaped_text}');"
        )

        with self._speech_lock:
            existing = self._speech_process

            if (
                existing is not None
                and
                existing.poll() is None
            ):
                # Critical can interrupt early speech.
                if priority > self._speech_priority:
                    try:
                        existing.terminate()
                    except Exception:
                        pass
                else:
                    return

            creation_flags = 0

            if hasattr(
                subprocess,
                "CREATE_NO_WINDOW",
            ):
                creation_flags = (
                    subprocess.CREATE_NO_WINDOW
                )

            try:
                process = subprocess.Popen(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-Command",
                        script,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creation_flags,
                )
            except Exception as error:
                print(
                    "NINO voice warning error:",
                    error,
                )
                return

            self.last_spoken_at[key] = now
            self._speech_process = process
            self._speech_priority = priority

            threading.Thread(
                target=self._clear_speech_process,
                args=(process,),
                daemon=True,
            ).start()

    def _clear_speech_process(
        self,
        process,
    ):
        try:
            process.wait()
        except Exception:
            pass

        with self._speech_lock:
            if self._speech_process is process:
                self._speech_process = None
                self._speech_priority = 0

    # =====================================================
    # ALERT EMISSION COOLDOWN
    # =====================================================

    def _can_emit(
        self,
        key,
        now,
    ):
        last_time = (
            self.last_alert_emitted_at.get(
                key,
                0.0,
            )
        )

        return (
            now - last_time
            >=
            self.alert_cooldown
        )

    def _mark_emitted(
        self,
        key,
        now,
    ):
        self.last_alert_emitted_at[
            key
        ] = now

    # =====================================================
    # RESET HELPERS
    # =====================================================

    def _complete_eye_recovery(
        self,
    ):
        self.eye_closed_started_at = None
        self.eye_open_started_at = None
        self.eye_alert_level = 0

    def _complete_distraction_recovery(
        self,
    ):
        self.looking_away_started_at = None
        self.forward_started_at = None
        self.distraction_alert_level = 0

    # =====================================================
    # MAIN UPDATE
    # =====================================================

    def update(
        self,
        driver_data,
    ):
        if not driver_data:
            return "NO_DATA"

        now = time.monotonic()

        face_detected = bool(
            driver_data.get(
                "face_detected",
                False,
            )
        )

        # -------------------------------------------------
        # NO FACE
        #
        # Do not invent drowsiness/distraction while face
        # tracking is unavailable.
        # -------------------------------------------------

        if not face_detected:
            self._complete_eye_recovery()
            self._complete_distraction_recovery()

            driver_data[
                "eye_closed_duration"
            ] = 0.0

            driver_data[
                "distraction_duration"
            ] = 0.0

            driver_data[
                "is_drowsy"
            ] = False

            return "NO_FACE"

        # =================================================
        # EYE STATE WITH RECOVERY GRACE
        # =================================================

        eye_state = str(
            driver_data.get(
                "eye_state",
                "UNKNOWN",
            )
        ).upper()

        eyes_closed = (
            eye_state == "CLOSED"
        )

        if eyes_closed:
            self.eye_open_started_at = None

            if self.eye_closed_started_at is None:
                self.eye_closed_started_at = now

        else:
            if self.eye_closed_started_at is not None:
                if self.eye_open_started_at is None:
                    self.eye_open_started_at = now

                open_duration = (
                    now
                    -
                    self.eye_open_started_at
                )

                if (
                    open_duration
                    >=
                    self.eye_recovery_grace
                ):
                    self._complete_eye_recovery()

        eye_duration = 0.0

        if self.eye_closed_started_at is not None:
            eye_duration = max(
                0.0,
                now
                -
                self.eye_closed_started_at,
            )

        driver_data[
            "eye_closed_duration"
        ] = round(
            eye_duration,
            3,
        )

        driver_data[
            "is_drowsy"
        ] = (
            eye_duration
            >=
            self.eye_critical_duration
        )

        # =================================================
        # DISTRACTION STATE WITH RECOVERY GRACE
        # =================================================

        direction = str(
            driver_data.get(
                "head_direction",
                "UNKNOWN",
            )
        ).upper()

        looking_away = (
            direction
            in {
                "LEFT",
                "RIGHT",
                "UP",
                "DOWN",
            }
        )

        if looking_away:
            self.forward_started_at = None

            if self.looking_away_started_at is None:
                self.looking_away_started_at = now

        else:
            if self.looking_away_started_at is not None:
                if self.forward_started_at is None:
                    self.forward_started_at = now

                forward_duration = (
                    now
                    -
                    self.forward_started_at
                )

                if (
                    forward_duration
                    >=
                    self.direction_recovery_grace
                ):
                    self._complete_distraction_recovery()

        away_duration = 0.0

        if self.looking_away_started_at is not None:
            away_duration = max(
                0.0,
                now
                -
                self.looking_away_started_at,
            )

        driver_data[
            "distraction_duration"
        ] = round(
            away_duration,
            3,
        )

        # =================================================
        # EYE ALERT LEVEL
        # =================================================

        eye_level = 0

        if (
            eye_duration
            >=
            self.eye_critical_duration
        ):
            eye_level = 2

        elif (
            eye_duration
            >=
            self.eye_early_duration
        ):
            eye_level = 1

        # Early eye warning: one per episode + cooldown.
        if (
            eye_level == 1
            and
            self.eye_alert_level == 0
            and
            self._can_emit(
                "early_eye",
                now,
            )
        ):
            self._mark_emitted(
                "early_eye",
                now,
            )

            print(
                "NINO ALERT: EARLY EYE WARNING"
            )

            self._speak(
                "Please keep your eyes open and stay alert.",
                key="early_eye",
                priority=1,
            )

        # Critical drowsiness: one escalation per episode.
        if (
            eye_level == 2
            and
            self.eye_alert_level < 2
        ):
            if self._can_emit(
                "critical_drowsiness",
                now,
            ):
                self._mark_emitted(
                    "critical_drowsiness",
                    now,
                )

                self.drowsiness_event_count += 1

                print(
                    "NINO ALERT: CRITICAL DROWSINESS"
                )

                self._speak(
                    (
                        "Drowsiness detected. "
                        "Please stay alert."
                    ),
                    key="critical_drowsiness",
                    priority=2,
                )

        self.eye_alert_level = max(
            self.eye_alert_level,
            eye_level,
        )

        # =================================================
        # DISTRACTION ALERT LEVEL
        # =================================================

        distraction_level = 0

        if (
            away_duration
            >=
            self.distraction_critical_duration
        ):
            distraction_level = 2

        elif (
            away_duration
            >=
            self.distraction_early_duration
        ):
            distraction_level = 1

        if (
            distraction_level == 1
            and
            self.distraction_alert_level == 0
            and
            self._can_emit(
                "early_distraction",
                now,
            )
        ):
            self._mark_emitted(
                "early_distraction",
                now,
            )

            print(
                "NINO ALERT: EARLY DISTRACTION",
                direction,
            )

            self._speak(
                "Please keep your eyes on the road.",
                key="early_distraction",
                priority=1,
            )

        if (
            distraction_level == 2
            and
            self.distraction_alert_level < 2
        ):
            if self._can_emit(
                "critical_distraction",
                now,
            ):
                self._mark_emitted(
                    "critical_distraction",
                    now,
                )

                self.distraction_event_count += 1

                print(
                    "NINO ALERT: CRITICAL DISTRACTION",
                    direction,
                )

                self._speak(
                    (
                        "Warning. Sustained distraction detected. "
                        "Eyes on the road."
                    ),
                    key="critical_distraction",
                    priority=2,
                )

        self.distraction_alert_level = max(
            self.distraction_alert_level,
            distraction_level,
        )

        # =================================================
        # COUNTERS
        # =================================================

        existing_drowsiness = int(
            driver_data.get(
                "drowsiness_event_count",
                0,
            )
            or
            0
        )

        driver_data[
            "drowsiness_event_count"
        ] = max(
            existing_drowsiness,
            self.drowsiness_event_count,
        )

        existing_distraction = int(
            driver_data.get(
                "distraction_event_count",
                0,
            )
            or
            0
        )

        driver_data[
            "distraction_event_count"
        ] = max(
            existing_distraction,
            self.distraction_event_count,
        )

        # =================================================
        # DRIVER-FACING STATE
        # =================================================

        if distraction_level == 2:
            driver_data[
                "distraction_state"
            ] = (
                f"DISTRACTED_{direction}"
            )

        elif distraction_level == 1:
            driver_data[
                "distraction_state"
            ] = (
                f"WARNING_{direction}"
            )

        elif self.looking_away_started_at is not None:
            driver_data[
                "distraction_state"
            ] = (
                f"LOOKING_{direction}"
            )

        else:
            driver_data[
                "distraction_state"
            ] = "ATTENTIVE"

        # =================================================
        # CURRENT ALERT STATE
        #
        # Current state stays visible while the unsafe state
        # persists, but event counters / sound are not emitted
        # every frame.
        # =================================================

        if eye_level == 2:
            return "CRITICAL_DROWSINESS_ALERT"

        if distraction_level == 2:
            return "CRITICAL_DISTRACTION_ALERT"

        if eye_level == 1:
            return "EARLY_EYE_WARNING"

        if distraction_level == 1:
            return "EARLY_DISTRACTION_WARNING"

        if self.eye_closed_started_at is not None:
            return "EYE_CLOSURE_ACTIVE"

        if self.looking_away_started_at is not None:
            return "LOOKING_AWAY"

        return "NORMAL"
