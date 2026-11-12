import os
import json
import time
import requests
import subprocess
from picamera2 import Picamera2
from eye_animations import init_displays, show_emotion, blink, clear_screens, cleanup as cleanup_displays
from vibration import vibrate, cleanup as cleanup_vibration

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
PC_SERVER      = "http://192.168.100.99:5000"   # ← replace with your laptop's IP
AUDIO_DURATION = 8
FRAME_COUNT    = 4

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def speak(text):
    print(f"[PI] Speaking: {text}")
    subprocess.run(
        ["espeak", "-v", "en+f3", "-s", "130", "-a", "170", "-p", "65", text],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )


def record_audio(filename, duration=AUDIO_DURATION):
    try:
        print(f"[PI] Recording for {duration} seconds...")
        subprocess.run([
            "arecord", "-D", "plughw:3,0",
            "-f", "S32_LE", "-r", "48000", "-c", "2",
            "-d", str(duration), "/tmp/raw_recording.wav"
        ], capture_output=True)
        subprocess.run([
            "sox", "/tmp/raw_recording.wav",
            "-r", "44100", "-c", "1", "-b", "16",
            filename, "gain", "20"
        ], capture_output=True)
        print(f"[PI] Audio saved to {filename}")
        return True
    except Exception as e:
        print(f"[PI] Audio recording failed: {e}")
        return False


def capture_photo(filename, picam2):
    print(f"[PI] Capturing photo...")
    picam2.capture_file(filename)
    print(f"[PI] Photo saved to {filename}")


def ping_server():
    try:
        response = requests.get(f"{PC_SERVER}/ping", timeout=5)
        return response.status_code == 200
    except:
        return False


def send_photo_for_emotion(photo_path):
    try:
        with open(photo_path, "rb") as f:
            response = requests.post(
                f"{PC_SERVER}/analyze_emotion",
                files={"image": ("photo.jpg", f, "image/jpeg")},
                timeout=30
            )
        data = response.json()
        if "error" in data:
            return "neutral", 0
        return data["dominant_emotion"], data["face_confidence"]
    except Exception as e:
        print(f"[PI] Failed to send photo: {e}")
        return "neutral", 0


def send_audio_for_transcription(audio_path, prompt_hint=""):
    try:
        with open(audio_path, "rb") as f:
            response = requests.post(
                f"{PC_SERVER}/transcribe",
                files={"audio": ("audio.wav", f, "audio/wav")},
                data={"prompt_hint": prompt_hint},
                timeout=60
            )
        data = response.json()
        text = data.get("text", "")
        print(f"[PI] Transcribed: '{text}'")
        return text
    except Exception as e:
        print(f"[PI] Failed to send audio: {e}")
        return ""


def send_chat(conversation_history, emotion):
    try:
        response = requests.post(
            f"{PC_SERVER}/chat",
            json={"conversation_history": conversation_history, "emotion": emotion},
            timeout=60
        )
        return response.json()
    except Exception as e:
        print(f"[PI] Failed to send chat: {e}")
        return {"speech_text": "I'm having trouble connecting.", "eye_animation": "neutral", "vibration_pattern": "none"}


def save_session_log(emotion, conversation_history):
    try:
        requests.post(
            f"{PC_SERVER}/log_session",
            json={"emotion": emotion, "conversation_history": conversation_history},
            timeout=10
        )
        print("[PI] Session logged.")
    except Exception as e:
        print(f"[PI] Logging failed: {e}")


# ── MAIN PIPELINE ─────────────────────────────────────────────────────────────

def main():
    print("[PI] Checking PC server connection...")
    if not ping_server():
        print("[PI] ERROR: Cannot reach PC server.")
        return
    print("[PI] PC server is reachable. Starting session...")

    print("[PI] Initialising displays...")
    disp1, disp2 = init_displays()
    show_emotion(disp1, disp2, "neutral")
    print("[PI] Displays ready!")

    print("[PI] Starting camera...")
    picam2 = Picamera2()
    config = picam2.create_still_configuration()
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    print("[PI] Camera ready!")

    try:
        while True:

            # ── STEP 1: Wait for user ──────────────────────────────────────
            print("[PI] Waiting for user to appear...")
            show_emotion(disp1, disp2, "neutral")
            user_detected = False
            while not user_detected:
                photo_path = "/tmp/presence.jpg"
                capture_photo(photo_path, picam2)
                _, confidence = send_photo_for_emotion(photo_path)
                print(f"[PI] Presence check confidence: {confidence:.2f}")
                if confidence > 0.5:
                    user_detected = True
                    print("[PI] User detected!")
                else:
                    time.sleep(2)

            speak("Hello! I am glad you are here. Let me take a look at you.")

            # ── STEP 2: Capture frames for emotion detection ───────────────
            emotion_results = []
            for i in range(FRAME_COUNT):
                photo_path = f"/tmp/capture_{i}.jpg"
                capture_photo(photo_path, picam2)
                emotion, confidence = send_photo_for_emotion(photo_path)
                print(f"[PI] Frame {i+1}: {emotion} (confidence: {confidence:.2f})")
                if confidence > 0.5:
                    emotion_results.append(emotion)
                time.sleep(1)

            detected_emotion = max(set(emotion_results), key=emotion_results.count) if emotion_results else "neutral"
            print(f"[PI] Final detected emotion: {detected_emotion}")
            show_emotion(disp1, disp2, detected_emotion)

            # ── STEP 3: Confirm emotion ────────────────────────────────────
            speak(f"I think you are feeling {detected_emotion}. Am I correct?")
            speak("Please say yes if I am correct, or say your actual emotion.")

            audio_path = "/tmp/confirmation.wav"
            if record_audio(audio_path, duration=5):
                user_response = send_audio_for_transcription(
                    audio_path,
                    prompt_hint="The user will say yes or no, or name an emotion like happy, sad, angry, surprised, or neutral."
                )
            else:
                user_response = ""

            print(f"[PI] User said: '{user_response}'")

            if "yes" in user_response.lower():
                final_emotion = detected_emotion
            else:
                speak("Please say your emotion out loud.")
                if record_audio(audio_path, duration=5):
                    corrected = send_audio_for_transcription(
                        audio_path,
                        prompt_hint="The user is saying one emotion: happy, sad, angry, fear, disgust, surprised, or neutral."
                    )
                else:
                    corrected = ""
                valid_emotions = ["happy", "sad", "angry", "fear", "disgust", "surprised", "neutral"]
                final_emotion = next((e for e in valid_emotions if e in corrected.lower()), "neutral")
                if not corrected:
                    speak("I couldn't hear you. I will assume you are feeling neutral.")

            print(f"[PI] Final emotion: {final_emotion}")
            show_emotion(disp1, disp2, final_emotion)

            # ── STEP 4: Conversation ───────────────────────────────────────
            conversation_history = [
                {
                    "role":    "user",
                    "content": f"I am feeling {final_emotion}.{(' ' + user_response.strip()) if user_response.strip() else ''}"
                }
            ]

            speak("Let's talk. Say bye whenever you want to end our conversation.")
            silent_turns = 0

            while True:
                response  = send_chat(conversation_history, final_emotion)
                speech    = response.get("speech_text",       "I'm here for you.")
                eyes      = response.get("eye_animation",     "neutral")
                vibration = response.get("vibration_pattern", "none")

                print(f"[PI] Robot: {speech}")
                print(f"[PI] Eyes: {eyes} | Vibration: {vibration}")

                show_emotion(disp1, disp2, eyes)
                vibrate(vibration)
                speak(speech)

                conversation_history.append({"role": "assistant", "content": speech})
                blink(disp1, disp2, eyes)

                audio_path = "/tmp/conversation.wav"
                if record_audio(audio_path):
                    user_input = send_audio_for_transcription(
                        audio_path,
                        prompt_hint="I feel happy today. How are you?"
                    )
                else:
                    user_input = ""

                if not user_input:
                    silent_turns += 1
                    if silent_turns >= 2:
                        ret_frame = "/tmp/presence_check.jpg"
                        capture_photo(ret_frame, picam2)
                        _, confidence = send_photo_for_emotion(ret_frame)
                        if confidence < 0.3:
                            speak("It seems like you have left. Goodbye! Take care.")
                            save_session_log(final_emotion, conversation_history)
                            break
                        speak("Are you still there? I have not heard from you in a while.")
                        silent_turns = 0
                    else:
                        speak("I didn't catch that. Could you say that again?")
                    continue

                print(f"[PI] You: {user_input}")
                silent_turns = 0

                if "bye" in user_input.lower():
                    speak("Goodbye! I hope you feel better soon. Take care.")
                    save_session_log(final_emotion, conversation_history)
                    show_emotion(disp1, disp2, "neutral")
                    break

                conversation_history.append({"role": "user", "content": user_input})

            speak("I am ready for the next person.")
            show_emotion(disp1, disp2, "neutral")
            time.sleep(2)

    finally:
        picam2.stop()
        picam2.close()
        clear_screens(disp1, disp2)
        cleanup_displays(disp1, disp2)
        cleanup_vibration()
        print("[PI] Cleanup done.")


if __name__ == "__main__":
    main()
