import subprocess
import threading


class Alarm:

    def __init__(self):
        self.active = False
        self.thread = None

    def _speak_warning(self):

        while self.active:

            command = [
                "powershell",
                "-Command",
                """
                Add-Type -AssemblyName System.Speech;
                $voice = New-Object System.Speech.Synthesis.SpeechSynthesizer;
                $voice.Volume = 100;
                $voice.Rate = 1;
                $voice.Speak('WAKE UP! DROWSINESS DETECTED! PLEASE PAY ATTENTION!');
                """
            ]

            subprocess.run(
                command,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

    def start(self):

        if self.active:
            return

        self.active = True

        self.thread = threading.Thread(
            target=self._speak_warning,
            daemon=True
        )

        self.thread.start()

    def stop(self):

        self.active = False