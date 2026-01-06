import os
import time
from datetime import datetime
from gpiozero import MotionSensor
from subprocess import run, Popen

# Configuration
PIR_PIN = 17 # Use GPIO 17 (Pin 11)
OFF_DELAY = 60 # Time in seconds (300 = 5 minutes)
DISPLAY_NAME = 'HDMI-A-1' # Run 'wlr-randr' to verify this name
HA_URL = "http://homeassistant:8123/dashboard-nebula/0?kiosk"

# Tell python which display to control (Standard for PI Kiosks)
os.environ['WAYLAND_DISPLAY'] = "wayland-0"
os.environ['XDG_RUNTIME_DIR'] = f"/run/user/{os.getuid()}"

pir = MotionSensor(PIR_PIN, queue_len=1)
last_motion_time = time.time()
screen_on = True

def get_now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def launch_browser():
    # Start chromium in kiosk mode if it is not already running
    print(f"[{get_now()}] Launching Chromium...")
    cmd = [
        "chromium",
        "--kiosk",
        "--noerrdialogs",
        "--disable-infobars",
        "--disable-restore-session-state",
        HA_URL
    ]
    Popen(cmd)

def refresh_browser():
    # Simulate F5 to refresh the page
    print(f"[{get_now()}] Refreshing browser...")
    try:
        # Try wayland native first
        run(['wtype', '-k', 'F5'], check=False)
        # Fallback to xdotool
        run(['xdotool', 'key', 'F5'], check=False)
    except Exception as e:
        print(f"[{get_now()}] Refresh signal failed: {e}")

def turn_on():
    global screen_on
    if not screen_on:
        # Manual debounce to ensure the motion is real
        time.sleep(2)
        if pir.motion_detected:
            print(f"[{get_now()}] Waking up screen...")
            # 'wlr-randr --output HDMI-A-1 --on' powers on the HDMI output
            run(['wlr-randr', '--output', DISPLAY_NAME, '--on'])
            screen_on = True
            time.sleep(1) # Give the screen a second to handshake
            refresh_browser()

def turn_off():
    global screen_on
    if screen_on:
        print(f"[{get_now()}] Putting screen to sleep...\n\n")
        # 'wlr-randr --output HDMI-A-1 --off' puts the monitor in to power-save mode
        run(['wlr-randr', '--output', DISPLAY_NAME, '--off'])
        screen_on = False

print(f"[{get_now()}] Jezior HomeAssistant Kiosk Power Manager Active. Press CTRL+C to exit.\n")

#Start chromium on script launch
launch_browser()

try:
    # Ensure screen is on at start of application
    turn_on()

    while True:
        if pir.motion_detected:
            last_motion_time = time.time()
            turn_on()

        # Check if "off delay" has passed
        if screen_on and (time.time() - last_motion_time > OFF_DELAY):
            turn_off()

        time.sleep(1) # Check every second

except KeyboardInterrupt:
    turn_on() # Leave screen on if we quit the script
