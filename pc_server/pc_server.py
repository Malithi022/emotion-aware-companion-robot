import os
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["TF_KERAS_LOG_LEVEL"] = "0"

import warnings
warnings.filterwarnings("ignore")

import json
import tempfile
import csv
from datetime import datetime
from faster_whisper import WhisperModel
from flask import Flask, request, jsonify
from deepface import DeepFace
from openai import OpenAI

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
OPENAI_API_KEY = "paste-your-api-key-here"
WHISPER_MODEL  = "base"
PORT           = 5000

# ── INITIALISE ────────────────────────────────────────────────────────────────
app    = Flask(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

print("[SERVER] Loading Whisper model...")
whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
print("[SERVER] Whisper model loaded")

VALID_EMOTIONS = ["happy", "sad", "angry", "fear", "disgust", "surprised", "neutral"]

# ── HELPER FUNCTIONS ──────────────────────────────────────────────────────────

def parse_response(response):
    try:
        return json.loads(response)
    except:
        return None


def log_session(emotion, conversation_history):
    filename = "pi_session_log.csv"
    file_exists = os.path.isfile(filename)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    turn_count = sum(1 for m in conversation_history if m.get("role") == "user")
    with open(filename, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "emotion", "turns", "conversation"])
        writer.writerow([timestamp, emotion, turn_count, json.dumps(conversation_history)])
    print(f"[SERVER] Session logged to {filename}")


# ── ENDPOINT 1: Analyse emotion from photo ────────────────────────────────────
@app.route("/analyze_emotion", methods=["POST"])
def analyze_emotion():
    if "image" not in request.files:
        return jsonify({"error": "No image file received"}), 400

    image_file = request.files["image"]
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        image_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        print(f"[SERVER] Running DeepFace on received image...")
        result = DeepFace.analyze(
            tmp_path,
            actions=["emotion"],
            enforce_detection=False,
            detector_backend="opencv"
        )
        emotion_scores   = result[0]["emotion"]
        dominant_emotion = result[0]["dominant_emotion"]
        face_confidence  = result[0].get("face_confidence", 0)
        print(f"[SERVER] Dominant emotion: {dominant_emotion} (confidence: {face_confidence:.2f})")
        return jsonify({
            "dominant_emotion": dominant_emotion,
            "emotion_scores":   emotion_scores,
            "face_confidence":  face_confidence
        })
    except Exception as e:
        print(f"[SERVER] DeepFace error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp_path)


# ── ENDPOINT 2: Transcribe audio ──────────────────────────────────────────────
@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file received"}), 400

    audio_file  = request.files["audio"]
    prompt_hint = request.form.get("prompt_hint", "")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        print(f"[SERVER] Transcribing audio...")
        segments, info = whisper_model.transcribe(tmp_path, initial_prompt=prompt_hint)
        segments  = list(segments)
        no_speech = segments[0].no_speech_prob if segments else 1.0
        text      = " ".join(s.text for s in segments).strip()
        print(f"[SERVER] Transcribed: '{text}' (no_speech_prob: {no_speech:.2f})")

        if no_speech > 0.6:
            text = ""
        if "robot" in text.lower() or "conversation" in text.lower():
            text = ""

        return jsonify({"text": text, "no_speech_prob": no_speech})
    except Exception as e:
        print(f"[SERVER] Whisper error: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp_path)


# ── ENDPOINT 3: Generate chat response ────────────────────────────────────────
@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data or "conversation_history" not in data:
        return jsonify({"error": "No conversation history received"}), 400

    conversation_history = data["conversation_history"]
    final_emotion        = data.get("emotion", "neutral")

    system_prompt = f"""You are a companion robot. You MUST respond ONLY with a valid JSON object.
Never write plain text. Never explain yourself. Only output JSON.

The user is feeling {final_emotion}. Respond with empathy and ask follow-up questions to keep
the conversation going naturally. Aim for 2-4 sentences in speech_text.

You MUST use exactly this format and nothing else:
{{"speech_text": "your response here", "eye_animation": "value", "vibration_pattern": "value"}}

eye_animation must be one of: sad_soft, happy_wide, neutral, focused, calm, surprised
vibration_pattern must be one of: none, slow_pulse, short_pulse, steady_light

Any response that is not valid JSON will break the system. Output JSON only."""

    if not conversation_history or conversation_history[0].get("role") != "system":
        conversation_history = [{"role": "system", "content": system_prompt}] + conversation_history

    try:
        print(f"[SERVER] Calling ChatGPT...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history,
            timeout=30
        )
        result = response.choices[0].message.content.strip()
        result = result.replace("{{", "{").replace("}}", "}")
        print(f"[SERVER] ChatGPT response: {result}")
    except Exception as e:
        print(f"[SERVER] OpenAI error: {e}")
        return jsonify({
            "speech_text":       "I'm having trouble thinking right now.",
            "eye_animation":     "neutral",
            "vibration_pattern": "none"
        })

    parsed = parse_response(result)
    if not parsed:
        print("[SERVER] Invalid JSON, retrying...")
        retry_history = conversation_history + [
            {"role": "user", "content": "Your last response was not valid JSON. Reply only with the JSON object, nothing else."}
        ]
        try:
            response2 = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=retry_history,
                timeout=30
            )
            result = response2.choices[0].message.content.strip()
            parsed = parse_response(result)
        except:
            pass

    if not parsed:
        parsed = {
            "speech_text":       "I'm here for you. Tell me more.",
            "eye_animation":     "neutral",
            "vibration_pattern": "none"
        }

    if len(parsed.get("speech_text", "")) > 400:
        parsed["speech_text"] = parsed["speech_text"][:400]

    return jsonify(parsed)


# ── ENDPOINT 4: Log session ───────────────────────────────────────────────────
@app.route("/log_session", methods=["POST"])
def log_session_endpoint():
    data         = request.get_json()
    emotion      = data.get("emotion", "unknown")
    conversation = data.get("conversation_history", [])
    log_session(emotion, conversation)
    return jsonify({"status": "logged"})


# ── HEALTH CHECK ──────────────────────────────────────────────────────────────
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "message": "PC server is running"})


# ── START SERVER ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[SERVER] Starting PC server on port {PORT}...")
    print(f"[SERVER] Endpoints: GET /ping | POST /analyze_emotion /transcribe /chat /log_session")

    import numpy as np
    import cv2
    print("[SERVER] Warming up DeepFace...")
    dummy = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.imwrite("/tmp/dummy.jpg", dummy)
    try:
        DeepFace.analyze("/tmp/dummy.jpg", actions=["emotion"],
                         enforce_detection=False, detector_backend="opencv")
    except:
        pass
    print("[SERVER] DeepFace warmed up!")

    app.run(host="0.0.0.0", port=PORT, debug=False)
