import os
import shutil
import signal
import threading
import time
from gpiozero import MotionSensor
from subprocess import run, Popen, DEVNULL, TimeoutExpired

from config import get_env_int, get_env_str, load_env, get_now

load_env()

# Configuration
PIR_PIN = get_env_int("PIR_PIN", 17)
OFF_DELAY = get_env_int("OFF_DELAY", 60)  # Time in seconds (300 = 5 minutes)
DISPLAY_NAME = get_env_str("DISPLAY_NAME", "HDMI-A-1")  # Run 'wlr-randr' to verify this name
HA_URL = get_env_str("HA_URL", "http://homeassistant:8123/dashboard-nebula/0?kiosk")
WATCHDOG_INTERVAL = get_env_int("WATCHDOG_INTERVAL", 300)  # Health check every 5 minutes

# Tell python which display to control (Standard for PI Kiosks)
os.environ.setdefault('WAYLAND_DISPLAY', "wayland-0")
os.environ.setdefault('XDG_RUNTIME_DIR', f"/run/user/{os.getuid()}")

# State variables protected by lock for thread safety
state_lock = threading.Lock()
last_motion_time = time.time()
screen_on = True
browser_proc = None
running = True

def launch_browser():
    global browser_proc
    # Start chromium in kiosk mode if it is not already running
    print(f"[{get_now()}] Launching Chromium...", flush=True)
    cmd = [
        "chromium",
        "--kiosk",
        "--noerrdialogs",
        "--disable-infobars",
        "--disable-restore-session-state",
        HA_URL
    ]
    # Redirect stdout/stderr to DEVNULL to prevent buffer filling
    browser_proc = Popen(cmd, stdout=DEVNULL, stderr=DEVNULL)


def close_browser():
    global browser_proc
    try:
        if browser_proc is not None and browser_proc.poll() is None:
            print(f"[{get_now()}] Closing Chromium...", flush=True)
            browser_proc.terminate()
            try:
                browser_proc.wait(timeout=5)
            except TimeoutExpired:
                print(f"[{get_now()}] Chromium did not terminate, killing...", flush=True)
                browser_proc.kill()
                browser_proc.wait(timeout=5)  # Reap the process
        browser_proc = None
    except Exception as e:
        print(f"[{get_now()}] Failed to close Chromium: {e}", flush=True)

    # Cleanup any orphaned chromium processes
    try:
        if shutil.which('pkill') is not None:
            run(['pkill', '-f', 'chromium.*--kiosk'], check=False, timeout=10)
    except Exception:
        pass

def turn_on():
    global screen_on
    with state_lock:
        if not screen_on:
            print(f"[{get_now()}] Waking up screen...", flush=True)
            try:
                # 'wlr-randr --output HDMI-A-1 --on' powers on the HDMI output
                run(['wlr-randr', '--output', DISPLAY_NAME, '--on'], timeout=30)
                screen_on = True
                time.sleep(1)  # Give the screen a second to handshake
                launch_browser()
            except TimeoutExpired:
                print(f"[{get_now()}] WARNING: wlr-randr timed out during turn_on", flush=True)
            except Exception as e:
                print(f"[{get_now()}] ERROR during turn_on: {e}", flush=True)


def turn_off():
    global screen_on
    with state_lock:
        if screen_on:
            print(f"[{get_now()}] Putting screen to sleep...\n", flush=True)
            close_browser()
            try:
                # 'wlr-randr --output HDMI-A-1 --off' puts the monitor in to power-save mode
                run(['wlr-randr', '--output', DISPLAY_NAME, '--off'], timeout=30)
                screen_on = False
            except TimeoutExpired:
                print(f"[{get_now()}] WARNING: wlr-randr timed out during turn_off", flush=True)
            except Exception as e:
                print(f"[{get_now()}] ERROR during turn_off: {e}", flush=True)

def on_motion():
    """Callback triggered when motion is detected."""
    global last_motion_time
    with state_lock:
        last_motion_time = time.time()
    turn_on()


def check_idle():
    """Check if screen should be turned off due to inactivity."""
    global last_motion_time
    with state_lock:
        idle_time = time.time() - last_motion_time
        is_on = screen_on

    if is_on and idle_time > OFF_DELAY:
        turn_off()


def watchdog():
    """Periodic health check and cleanup."""
    global browser_proc, running
    while running:
        time.sleep(WATCHDOG_INTERVAL)
        if not running:
            break

        print(f"[{get_now()}] Watchdog: health check", flush=True)

        # Check if browser should be running but crashed
        with state_lock:
            is_on = screen_on

        if is_on and browser_proc is not None:
            if browser_proc.poll() is not None:
                print(f"[{get_now()}] Watchdog: Browser crashed, restarting...", flush=True)
                launch_browser()


def idle_checker():
    """Thread that periodically checks for idle timeout."""
    global running
    while running:
        time.sleep(1)
        if not running:
            break
        check_idle()


def shutdown(signum, frame):
    """Handle shutdown signals gracefully."""
    global running
    print(f"[{get_now()}] Received shutdown signal, cleaning up...", flush=True)
    running = False


# Set up signal handlers for graceful shutdown
signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

# Initialize the motion sensor with event-driven callback
pir = MotionSensor(PIR_PIN, queue_len=1)
pir.when_motion = on_motion

print(f"[{get_now()}] Jezior HomeAssistant Kiosk Power Manager Active. Press CTRL+C to exit.\n", flush=True)

# Start chromium on script launch
launch_browser()

# Start background threads
watchdog_thread = threading.Thread(target=watchdog, daemon=True, name="watchdog")
watchdog_thread.start()

idle_thread = threading.Thread(target=idle_checker, daemon=True, name="idle_checker")
idle_thread.start()

try:
    # Main thread just waits - all work is event-driven
    while running:
        time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    running = False
    print(f"[{get_now()}] Shutting down, leaving screen on...", flush=True)
    # Force screen on state to ensure turn_on() runs
    with state_lock:
        screen_on = False
    turn_on()  # Leave screen on if we quit the script
