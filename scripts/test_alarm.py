import winsound

print("Playing alarm...")

winsound.PlaySound(
    "backend/alerts/alarm.wav",
    winsound.SND_FILENAME
)

print("Finished")