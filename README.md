# HomeAssistant Kiosk Power Management

Motion-activated kiosk “power manager” for a HomeAssistant dashboard. I have HomeAssistant running on a local server, and wanted to have a kiosk near the entry of my home that would power on when motion was detected, and power off after a period of inactivity.

Using a Raspberry Pi 5 with a PIR motion sensor, and an old monitor I had lying around, I was able to achieve what I was looking for... Here's how it works:

- Launches `chromium` in kiosk mode pointed at your Home Assistant dashboard URL
- Uses a PIR motion sensor on a Raspberry Pi GPIO pin to detect motion
- Turns the HDMI output on/off using `wlr-randr` (Wayland / wlroots)
- Refreshes the dashboard after wake (sends `F5`)

## Hardware

### PIR sensor wiring (typical)

Most PIR modules have `VCC`, `GND`, `OUT`.

- **VCC**: 5V or 3.3V depending on your module (check your PIR module’s specs)
- **GND**: Pi GND
- **OUT**: Pi GPIO **17** (physical pin **11**) by default

If your PIR outputs 5V logic, use a level shifter or a PIR module with 3.3V output to avoid damaging the Pi.

## Requirements

- Python 3 + `gpiozero`
- `chromium`
- `wlr-randr`
- `wtype`
- `xdotool`

## Configuration

Edit these constants at the top of `ha-kiosk.py`:

- `PIR_PIN = 17`
  - GPIO pin used for PIR `OUT`.
- `OFF_DELAY = 60`
  - Seconds of inactivity before turning the display off.
- `DISPLAY_NAME = 'HDMI-A-1'`
  - Output name as reported by `wlr-randr`.
- `HA_URL = "http://homeassistant:8123/dashboard-nebula/0?kiosk"`
  - URL opened by Chromium.

To verify your display output name, run `wlr-randr` and update `DISPLAY_NAME` accordingly.

## Running manually

```bash
python3 ha-kiosk.py >> kiosk.log
```

Stop with `CTRL+C`. On exit, the script calls `turn_on()` so the screen is left on.

## Run on boot with systemd (recommended)

This should run as the same user that owns the Wayland session/compositor.

Copy `ha-kiosk.service` to `/etc/systemd/system/ha-kiosk.service` (adjust `User` and paths):

Enable/start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ha-kiosk.service
```
