import os
import shlex
import time
from gpiozero import MotionSensor
from subprocess import run, Popen

from config import get_env_int, get_env_str, load_env, get_now

load_env()

# Configuration
PIR_PIN = get_env_int("PIR_PIN", 17)
OFF_DELAY = get_env_int("OFF_DELAY", 60)  # Time in seconds (300 = 5 minutes)
DISPLAY_NAME = get_env_str("DISPLAY_NAME", "HDMI-A-1")  # Run 'wlr-randr' to verify this name
HA_URL = get_env_str("HA_URL", "http://homeassistant:8123/dashboard-nebula/0?kiosk")
FOCUS_CMD = get_env_str("FOCUS_CMD", "")

# Tell python which display to control (Standard for PI Kiosks)
os.environ.setdefault('WAYLAND_DISPLAY', "wayland-0")
os.environ.setdefault('XDG_RUNTIME_DIR', f"/run/user/{os.getuid()}")

pir = MotionSensor(PIR_PIN, queue_len=1)
last_motion_time = time.time()
screen_on = True

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


def focus_browser():
    if FOCUS_CMD:
        try:
            run(shlex.split(FOCUS_CMD), check=False)
            return
        except Exception:
            return

    try:
        run(['swaymsg', '[app_id="chromium"]', 'focus'], check=False)
        run(['swaymsg', '[app_id="chromium-browser"]', 'focus'], check=False)
    except Exception:
        pass

    try:
        run(['hyprctl', 'dispatch', 'focuswindow', 'class:^(chromium|Chromium)$'], check=False)
    except Exception:
        pass

    try:
        run(['xdotool', 'search', '--onlyvisible', '--class', 'chromium', 'windowactivate'], check=False)
    except Exception:
        pass

def refresh_browser():
    # Simulate F5 to refresh the page
    print(f"[{get_now()}] Refreshing browser...")
    try:
        focus_browser()
        time.sleep(0.2)
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
