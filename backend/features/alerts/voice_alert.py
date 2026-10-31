import subprocess
import threading
import time


class VoiceAlert:
    """
    Non-blocking spoken warning system for NINO.

    Uses Windows PowerShell System.Speech.

    Features:
        - speech runs in a background thread
        - prevents overlapping warnings
        - cooldown prevents repeated shouting
    """

    def __init__(
        self,
        cooldown_seconds=4.0,
    ):

        self.cooldown_seconds = (
            cooldown_seconds
        )

        self.last_alert_time = 0.0

        self.is_speaking = False

        self.lock = threading.Lock()

    # =====================================================
    # INTERNAL SPEECH FUNCTION
    # =====================================================

    def _speak_worker(
        self,
        message,
    ):

        try:

            # Escape apostrophes for PowerShell.
            safe_message = message.replace(
                "'",
                "''",
            )

            command = (
                "Add-Type -AssemblyName System.Speech; "
                "$speaker = New-Object "
                "System.Speech.Synthesis."
                "SpeechSynthesizer; "
                "$speaker.Volume = 100; "
                "$speaker.Rate = 1; "
                f"$speaker.Speak('{safe_message}');"
            )

            subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    command,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

        finally:

            with self.lock:

                self.is_speaking = False

    # =====================================================
    # PUBLIC ALERT METHOD
    # =====================================================

    def speak(
        self,
        message,
        force=False,
    ):
        """
        Speak an alert without blocking the camera loop.

        Returns
        -------
        bool
            True  -> warning started
            False -> warning suppressed
        """

        current_time = time.monotonic()

        with self.lock:

            # Do not overlap voices.
            if self.is_speaking:
                return False

            # Prevent repeating the same type of alert
            # every video frame.
            if (
                not force
                and
                current_time
                -
                self.last_alert_time
                <
                self.cooldown_seconds
            ):
                return False

            self.is_speaking = True

            self.last_alert_time = (
                current_time
            )

        thread = threading.Thread(
            target=self._speak_worker,
            args=(message,),
            daemon=True,
        )

        thread.start()

        return True


# =========================================================
# STANDALONE TEST
# =========================================================

if __name__ == "__main__":

    alert = VoiceAlert(
        cooldown_seconds=3.0
    )

    print(
        "Testing NINO voice alert..."
    )

    started = alert.speak(
        "Warning! Please pay attention to the road.",
        force=True,
    )

    print(
        "Alert started:",
        started,
    )

    # Keep test program alive long enough
    # for background speech to finish.
    time.sleep(4)

    print(
        "Voice alert test complete."
    )