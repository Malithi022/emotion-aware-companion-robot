import RPi.GPIO as GPIO
import time
import threading

VIBRATION_PIN = 26

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(VIBRATION_PIN, GPIO.OUT)

_current_thread = None
_stop_flag      = False


def _run_pattern(pattern):
    global _stop_flag
    _stop_flag = False

    if pattern == "short_pulse":
        for _ in range(3):
            if _stop_flag: break
            GPIO.output(VIBRATION_PIN, GPIO.HIGH)
            time.sleep(0.15)
            GPIO.output(VIBRATION_PIN, GPIO.LOW)
            time.sleep(0.15)

    elif pattern == "slow_pulse":
        # Cat purr — rapid rhythmic bursts
        for _ in range(6):
            if _stop_flag: break
            for _ in range(6):
                if _stop_flag: break
                GPIO.output(VIBRATION_PIN, GPIO.HIGH)
                time.sleep(0.02)
                GPIO.output(VIBRATION_PIN, GPIO.LOW)
                time.sleep(0.02)
            time.sleep(0.25)

    elif pattern == "steady_light":
        # Gentle continuous purr
        for _ in range(30):
            if _stop_flag: break
            GPIO.output(VIBRATION_PIN, GPIO.HIGH)
            time.sleep(0.03)
            GPIO.output(VIBRATION_PIN, GPIO.LOW)
            time.sleep(0.03)

    GPIO.output(VIBRATION_PIN, GPIO.LOW)


def vibrate(pattern):
    global _current_thread, _stop_flag
    if pattern == "none":
        stop()
        return
    _stop_flag = True
    if _current_thread and _current_thread.is_alive():
        _current_thread.join(timeout=1)
    _current_thread = threading.Thread(
        target=_run_pattern, args=(pattern,), daemon=True
    )
    _current_thread.start()


def stop():
    global _stop_flag
    _stop_flag = True
    try:
        GPIO.output(VIBRATION_PIN, GPIO.LOW)
    except:
        pass


def cleanup():
    global _stop_flag
    _stop_flag = True
    try:
        GPIO.output(VIBRATION_PIN, GPIO.LOW)
    except:
        pass
    try:
        GPIO.cleanup()
    except:
        pass


if __name__ == "__main__":
    patterns = ["short_pulse", "slow_pulse", "steady_light"]
    for p in patterns:
        print(f"Testing: {p}")
        vibrate(p)
        time.sleep(3)
    cleanup()
    print("Done!")
