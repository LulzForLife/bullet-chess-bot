import subprocess
import sys
import time

KEYBOARD_INTERRUPT = 0
API_KEY_ERROR = 100
UNKNOWN_BOT_EXCEPTION = 101
UNKNOWN_RESPONSE_EXCEPTION = 102

exception_descriptions = {
    KEYBOARD_INTERRUPT: "Keyboard interrupt",
    API_KEY_ERROR: "Api key parsing/validation error",
    UNKNOWN_BOT_EXCEPTION: "Unknown exception (bot)",
    UNKNOWN_RESPONSE_EXCEPTION: "Unknown exception (response)"
}

while True:
    result = subprocess.run([sys.executable, "_lichess_bot.py"])
    if result.returncode == KEYBOARD_INTERRUPT:
        break
    elif result.returncode == API_KEY_ERROR:
        break
    description = exception_descriptions.get(result.returncode, "Unknown exception")
    print(f"Bot exited with code {result.returncode} ({description})")
    print("Restarting in 5 seconds...")
    time.sleep(5)
