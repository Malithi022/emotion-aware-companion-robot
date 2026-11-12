import RPi.GPIO as GPIO
import spidev
import time
from PIL import Image, ImageDraw

# ── DISPLAY DRIVER ────────────────────────────────────────────────────────────

class ST7735:
    SWRESET = 0x01
    SLPOUT  = 0x11
    COLMOD  = 0x3A
    MADCTL  = 0x36
    CASET   = 0x2A
    RASET   = 0x2B
    RAMWR   = 0x2C
    DISPON  = 0x29
    NORON   = 0x13

    def __init__(self, cs, dc, rst, width=128, height=128):
        self.cs  = cs
        self.dc  = dc
        self.rst = rst
        self.w   = width
        self.h   = height

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.dc,  GPIO.OUT)
        GPIO.setup(self.rst, GPIO.OUT)

        self.spi = spidev.SpiDev()
        self.spi.open(0, 0 if cs == 8 else 1)
        self.spi.max_speed_hz = 16000000
        self.spi.mode = 0

        self._reset()
        self._init()

    def _reset(self):
        GPIO.output(self.rst, GPIO.HIGH); time.sleep(0.05)
        GPIO.output(self.rst, GPIO.LOW);  time.sleep(0.05)
        GPIO.output(self.rst, GPIO.HIGH); time.sleep(0.15)

    def _cmd(self, cmd):
        GPIO.output(self.dc, GPIO.LOW)
        self.spi.writebytes([cmd])

    def _data(self, data):
        GPIO.output(self.dc, GPIO.HIGH)
        if isinstance(data, int):
            self.spi.writebytes([data])
        else:
            for i in range(0, len(data), 4096):
                self.spi.writebytes(data[i:i+4096])

    def _init(self):
        self._cmd(self.SWRESET); time.sleep(0.15)
        self._cmd(self.SLPOUT);  time.sleep(0.5)
        self._cmd(self.COLMOD);  self._data(0x05)
        self._cmd(self.MADCTL);  self._data(0x68)
        self._cmd(self.NORON);   time.sleep(0.1)
        self._cmd(self.DISPON);  time.sleep(0.1)

    def display(self, image):
        image = image.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        img   = image.convert("RGB")
        pixels = list(img.getdata())
        data = []
        for r, g, b in pixels:
            colour = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            data.append((colour >> 8) & 0xFF)
            data.append(colour & 0xFF)
        self._cmd(self.CASET)
        self._data([0x00, 0x02, 0x00, 0x81])
        self._cmd(self.RASET)
        self._data([0x00, 0x01, 0x00, 0x80])
        self._cmd(self.RAMWR)
        self._data(data)

    def cleanup(self):
        self.spi.close()


# ── COLOUR PALETTE ────────────────────────────────────────────────────────────
BLACK      = (0,   0,   0)
WHITE      = (255, 255, 255)
CYAN       = (0,   220, 220)
SOFT_BLUE  = (100, 180, 255)
YELLOW     = (255, 220,  50)
RED        = (220,  50,  50)
PURPLE     = (180,  80, 220)
ORANGE     = (255, 140,   0)
BG_DARK    = (10,  10,  30)
BG_NEUTRAL = (15,  15,  40)

W, H = 128, 128
YOFF = 2


# ── EYE DRAWING ───────────────────────────────────────────────────────────────

def draw_eye(draw, shape, color, bg, mirror=False):
    draw.rectangle([0, 0, W, H], fill=bg)

    if shape == "neutral":
        draw.rounded_rectangle([14, 44+YOFF, 114, 84+YOFF], radius=14, fill=color)

    elif shape == "happy":
        draw.arc([10, 20+YOFF, 118, 118+YOFF], start=200, end=340, fill=color, width=16)

    elif shape == "sad":
        draw.arc([10, 10+YOFF, 118, 108+YOFF], start=20, end=160, fill=color, width=16)

    elif shape == "sad_soft":
        draw.ellipse([24, 40+YOFF, 104, 90+YOFF], fill=color)
        draw.ellipse([34, 24+YOFF, 94,  64+YOFF], fill=bg)

    elif shape == "angry":
        if not mirror:
            pts = [14, 68+YOFF, 114, 44+YOFF, 114, 74+YOFF, 14, 84+YOFF]
        else:
            pts = [14, 44+YOFF, 114, 68+YOFF, 114, 84+YOFF, 14, 74+YOFF]
        draw.polygon(pts, fill=color)

    elif shape == "fear":
        draw.ellipse([18, 14+YOFF, 110, 114+YOFF], fill=color)
        draw.ellipse([32, 28+YOFF,  96, 100+YOFF], fill=bg)
        draw.ellipse([46, 44+YOFF,  82,  80+YOFF], fill=color)
        draw.ellipse([58, 28+YOFF,  74,  44+YOFF], fill=WHITE)

    elif shape == "surprised":
        draw.ellipse([18,  8+YOFF, 110, 120+YOFF], fill=color)
        draw.ellipse([34, 24+YOFF,  94, 104+YOFF], fill=bg)
        draw.ellipse([48, 40+YOFF,  80,  88+YOFF], fill=color)
        draw.ellipse([56, 24+YOFF,  72,  40+YOFF], fill=WHITE)

    elif shape == "disgust":
        if not mirror:
            pts = [14, 54+YOFF, 114, 74+YOFF, 114, 88+YOFF, 14, 78+YOFF]
        else:
            pts = [14, 74+YOFF, 114, 54+YOFF, 114, 78+YOFF, 14, 88+YOFF]
        draw.polygon(pts, fill=color)

    elif shape == "calm":
        draw.ellipse([24, 40+YOFF, 104, 110+YOFF], fill=color)
        draw.rectangle([0, 0, W, 64+YOFF], fill=bg)

    elif shape == "focused":
        draw.rounded_rectangle([10, 52+YOFF, 118, 76+YOFF], radius=10, fill=color)

    elif shape == "blink":
        draw.rounded_rectangle([14, 60+YOFF, 114, 70+YOFF], radius=5, fill=color)


# ── EMOTION MAP ───────────────────────────────────────────────────────────────

EMOTION_MAP = {
    "neutral":    {"shape": "neutral",   "color": CYAN,      "bg": BG_NEUTRAL},
    "happy":      {"shape": "happy",     "color": CYAN,      "bg": BG_DARK},
    "happy_wide": {"shape": "surprised", "color": YELLOW,    "bg": BG_DARK},
    "sad":        {"shape": "sad",       "color": SOFT_BLUE, "bg": BG_DARK},
    "sad_soft":   {"shape": "sad_soft",  "color": SOFT_BLUE, "bg": BG_DARK},
    "angry":      {"shape": "angry",     "color": RED,       "bg": BG_DARK},
    "fear":       {"shape": "fear",      "color": PURPLE,    "bg": BG_DARK},
    "surprised":  {"shape": "surprised", "color": YELLOW,    "bg": BG_DARK},
    "disgust":    {"shape": "disgust",   "color": ORANGE,    "bg": BG_DARK},
    "calm":       {"shape": "calm",      "color": CYAN,      "bg": BG_NEUTRAL},
    "focused":    {"shape": "focused",   "color": CYAN,      "bg": BG_DARK},
}


# ── PUBLIC FUNCTIONS ──────────────────────────────────────────────────────────

def init_displays():
    disp1 = ST7735(cs=8, dc=24, rst=25)
    disp2 = ST7735(cs=7, dc=23, rst=27)
    return disp1, disp2


def show_emotion(disp1, disp2, emotion):
    config = EMOTION_MAP.get(emotion, EMOTION_MAP["neutral"])
    shape  = config["shape"]
    color  = config["color"]
    bg     = config["bg"]

    img_left = Image.new("RGB", (W, H), bg)
    draw_eye(ImageDraw.Draw(img_left), shape, color, bg, mirror=False)
    disp1.display(img_left)

    img_right = Image.new("RGB", (W, H), bg)
    draw_eye(ImageDraw.Draw(img_right), shape, color, bg, mirror=True)
    disp2.display(img_right)


def blink(disp1, disp2, emotion="neutral"):
    config = EMOTION_MAP.get(emotion, EMOTION_MAP["neutral"])
    bg     = config["bg"]
    color  = config["color"]

    for d in [disp1, disp2]:
        img = Image.new("RGB", (W, H), bg)
        draw_eye(ImageDraw.Draw(img), "blink", color, bg)
        d.display(img)

    time.sleep(0.12)
    show_emotion(disp1, disp2, emotion)


def clear_screens(disp1, disp2):
    for d in [disp1, disp2]:
        img = Image.new("RGB", (W, H), BLACK)
        d.display(img)


def cleanup(disp1, disp2):
    disp1.cleanup()
    disp2.cleanup()
    GPIO.cleanup()


# ── DEMO ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Initialising displays...")
    disp1, disp2 = init_displays()
    emotions = list(EMOTION_MAP.keys())
    try:
        for emotion in emotions:
            print(f"  Showing: {emotion}")
            show_emotion(disp1, disp2, emotion)
            time.sleep(0.3)
            blink(disp1, disp2, emotion)
            time.sleep(1.5)
        show_emotion(disp1, disp2, "neutral")
    finally:
        cleanup(disp1, disp2)
        print("Done.")
