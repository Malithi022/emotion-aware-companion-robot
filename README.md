# Emotion-Aware Companion Robot with Human-in-the-Loop FER & Multimodal LLM Dialogue

A stationary, low-cost companion robot designed to mitigate academic stress through real-time facial expression recognition, speech-driven emotion verification, and context-aware conversational feedback[cite: 32, 38, 48]. 

Built on a **distributed Raspberry Pi 4 + PC server architecture**, the system decouples real-world sensor/actuator I/O from heavy neural inference pipelines (DeepFace, Faster-Whisper, and GPT-4o-mini)[cite: 32, 51, 52, 63, 64].

![Robot Physical Appearance](https://github.com/Malithi022/emotion-aware-companion-robot/blob/main/robot_front_view.png)

---

## 💡 Key Architectural Insights

1. **Human-in-the-Loop Emotion Confirmation:** Standard FER models underperform under unconstrained lighting and variable poses[cite: 39, 44]. Instead of responding directly to raw vision classifications, the robot asks for verbal confirmation (e.g., *"I think you are feeling sad. Am I correct?"*), enabling the user to confirm or correct their emotional state before shaping the conversation[cite: 32, 49, 54].
2. **Distributed Pi/PC Split Architecture:** Heavy AI inference is offloaded over local HTTP APIs to a host PC, allowing responsive performance without requiring dedicated hardware accelerators on the robot[cite: 32, 51, 52].
3. **Trimodal Affective Output:** Combines synthetic voice, dynamic animated LCD eyes across two SPI displays, and haptic vibration feedback in real time[cite: 32, 48, 55].

---

## 🛠 System Hardware & Pinout

![Hardware Block Diagram](https://github.com/Malithi022/emotion-aware-companion-robot/blob/main/robot_dual_eyes.png)

### Hardware Components
* **Embedded Controller:** Raspberry Pi 4 Model B (4GB / 8GB)[cite: 55, 56]
* **Camera Module:** Raspberry Pi Camera Module v1.3 (Sony OV5647, CSI ribbon)[cite: 55, 56]
* **Microphone:** INMP441 MEMS Digital Microphone (I2S interface)[cite: 55, 57]
* **Eye Displays:** 2× ST7735 1.44" $128 \times 128$ SPI TFT LCDs[cite: 55, 57]
* **Haptic Actuator:** Eccentric Rotating Mass (ERM) Vibration Motor Module[cite: 55, 58]
* **Audio Playback:** PAM8403 3W Stereo Amplifier + Miniature Speaker via 3.5mm TRRS jack[cite: 55, 59]
* **Chassis:** Custom 3D-printed enclosure with dedicated mounting and ventilation slots[cite: 51, 55, 59]

### Raspberry Pi 4 Hardware Pinout

| Peripheral | Signal | BCM / GPIO | Physical Pin | Notes / Workarounds |
| :--- | :--- | :--- | :--- | :--- |
| **LCD 1 (Left Eye)** | MOSI / SCLK | GPIO 10 / 11 | Pins 19 / 23 | Shared SPI data & clock bus[cite: 94] |
| | CS / DC / RST | GPIO 8 / 24 / 25 | Pins 24 / 18 / 22 | Dedicated chip select & reset lines[cite: 94] |
| **LCD 2 (Right Eye)** | MOSI / SCLK | GPIO 10 / 11 | Pins 19 / 23 | Shared SPI data & clock bus[cite: 94] |
| | CS / DC / RST | GPIO 7 / 23 / 27 | Pins 26 / 16 / 13 | Dedicated chip select & reset lines[cite: 94] |
| **INMP441 Mic** | BCLK / WS / SD | GPIO 18 / 19 / 20 | Pins 12 / 35 / 38 | I2S mono mode (L/R tied to GND)[cite: 94] |
| **ERM Vibration** | PWM / Digital IN | GPIO 26 | Pin 37 | Driven via daemon thread[cite: 58, 94, 127] |
| **PAM8403 Amp** | Audio Output | Analog Audio | 3.5mm TRRS | Requires 4-pole TRRS adapter[cite: 59, 95] |

> **Critical Hardware Fixes Implemented:**
> * **Audio Output Grounding:** Standard 3-pole TRS audio cables short ground to composite video on the Pi 4[cite: 59, 95]. A 4-pole TRRS-to-TRS adapter resolves ground looping[cite: 59, 95].
> * **I2S Overlay Conflict:** Standard `i2s-mmap` can lead to kernel panic on boot; replaced with `dtoverlay=googlevoicehat-soundcard` in `/boot/firmware/config.txt`[cite: 73].
> * **Display SPI Driver:** Built a custom `spidev` + `RPi.GPIO` frame-streamer to manage independent Chip Select lines without library locking conflicts[cite: 57, 73, 95].
> * **Mic Pre-amplification:** Raw INMP441 I2S samples record at ~4% full scale; handled via software gain staging (`sox gain 20`)[cite: 57, 112].

---

## 🧠 Software Architecture & Workflow

(https://github.com/Malithi022/emotion-aware-companion-robot/blob/main/system_architecture_flow.png)
