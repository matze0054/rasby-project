#!/usr/bin/env python3
"""Clock + date + weather and fun pages for a Waveshare 2.9" e-paper on a Raspberry Pi.

The pages rotate every PAGE_SECONDS. The panel is cleared to white on exit;
`--clear` does only that, e.g. after a power loss.
"""
import argparse
import json
import signal
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

# Match the model printed on your module: epd2in9 (V1), epd2in9_V2, epd2in9b, ...
from waveshare_epd import epd2in9_V2 as epd_driver

import fun_screen

LATITUDE = 48.22  # 80939 Munich
LONGITUDE = 11.62
LEAD_SECONDS = {"partial": 1.0, "full": 5.0}  # initial guesses of how long each refresh takes
FULL_REFRESH_EVERY = 10  # refreshes (5 min at 30 s per page) between full, flashing refreshes
WEATHER_EVERY = 10  # minutes between weather fetches
PAGE_SECONDS = 30  # should divide 60 so pages switch on the clock
PAGE_ORDER = ("clock", "wiki", "pokemon", "holidays")
STATION = "Kieferngarten"
MVG_API = "https://www.mvg.de/api/bgw-pt/v3"
MAX_DEPARTURES = 5

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WEATHER_CODES = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Fog", 51: "Drizzle", 53: "Drizzle", 55: "Drizzle",
    61: "Rain", 63: "Rain", 65: "Heavy rain", 71: "Snow", 73: "Snow",
    75: "Heavy snow", 80: "Showers", 81: "Showers", 82: "Heavy showers",
    95: "Thunderstorm",
}


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def fetch_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&current=temperature_2m,weather_code"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            current = json.load(resp)["current"]
        label = WEATHER_CODES.get(current["weather_code"], "Unknown")
        return f"{current['temperature_2m']:.0f}°C  {label}"
    except Exception:
        return "Weather unavailable"


_station_id = None


def mvg_get(path, params):
    url = f"{MVG_API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "epaper-clock"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def fetch_departures(at=None):
    """Return a list of 'U6 Destination  4'' strings for the station, as of `at` (epoch seconds)."""
    global _station_id
    try:
        if _station_id is None:
            found = mvg_get("/locations", {"query": STATION})
            station = next(
                l for l in found if l.get("type") == "STATION" and "globalId" in l
            )
            _station_id = station["globalId"]
        deps = mvg_get(
            "/departures",
            {"globalId": _station_id, "limit": 20, "transportTypes": "UBAHN"},
        )
        now = at if at is not None else time.time()
        lines = []
        for d in deps:
            if d.get("cancelled"):
                continue
            minutes = max(0, int((d["realtimeDepartureTime"] / 1000 - now) // 60))
            dest = d["destination"]
            if len(dest) > 6:
                dest = dest[:6] + "."
            lines.append((f"{d['label']} {dest}", f"{minutes}'"))
            if len(lines) == MAX_DEPARTURES:
                break
        return lines or [("No departures", "")]
    except Exception:
        return [("Departures n/a", "")]


def render(width, height, weather, now=None, departures=None):
    # Draw in landscape: the panel is 128x296 natively.
    image = Image.new("1", (height, width), 255)
    draw = ImageDraw.Draw(image)
    now = now or datetime.now()

    f_dep = font(FONT_REG, 12)
    split = 140

    draw.text((10, 0), now.strftime("%H:%M"), font=font(FONT_BOLD, 38), fill=0)
    draw.text((10, 52), now.strftime("%a, %d %b"), font=font(FONT_REG, 16), fill=0)
    draw.line((10, 84, split - 10, 84), fill=0)
    temp, _, label = weather.partition("  ")
    draw.text((10, 88), temp, font=font(FONT_BOLD, 14), fill=0)
    draw.text((10, 106), label, font=font(FONT_REG, 12), fill=0)

    draw.line((split, 5, split, width - 5), fill=0)
    draw.text((split + 8, 2), STATION, font=font(FONT_BOLD, 14), fill=0)
    for i, (text, mins) in enumerate(departures if departures is not None else fetch_departures()):
        y = 24 + i * 20
        draw.text((split + 8, y), text, font=f_dep, fill=0)
        draw.text((height - 4, y), mins, font=f_dep, fill=0, anchor="ra")
    return image


def render_page(page, width, height, weather, target):
    if page == "clock":
        return render(width, height, weather, target, fetch_departures(target.timestamp()))
    return fun_screen.PAGES[page](width, height, target)


def clear_panel(epd, awake=False):
    """Turn the panel white and put it to sleep."""
    if awake:
        epd.sleep()  # releases SPI/GPIO so init() can reopen them
    epd.init()
    epd.Clear(0xFF)
    epd.sleep()


def _terminate(signum, frame):
    raise SystemExit(0)


def main():
    parser = argparse.ArgumentParser(description="E-paper clock")
    parser.add_argument("--clear", action="store_true", help="turn the panel white and exit")
    args = parser.parse_args()

    epd = epd_driver.EPD()
    if args.clear:
        clear_panel(epd)
        return

    signal.signal(signal.SIGTERM, _terminate)  # so `kill` and systemd stop also clear the panel
    awake = False
    try:
        weather = "Weather unavailable"
        weather_at = None
        lead = dict(LEAD_SECONDS)
        tick = 0
        since_full = 0
        while True:
            # Prepare the next page, then push it early so the panel changes right on the boundary.
            now = datetime.now()
            seconds_left = PAGE_SECONDS - now.second % PAGE_SECONDS
            target = now.replace(microsecond=0) + timedelta(seconds=seconds_left)
            page = PAGE_ORDER[tick % len(PAGE_ORDER)]
            tick += 1
            if page == "clock" and (
                weather_at is None or time.monotonic() - weather_at >= WEATHER_EVERY * 60
            ):
                weather = fetch_weather()
                weather_at = time.monotonic()
            image = render_page(page, epd.width, epd.height, weather, target)
            buf = epd.getbuffer(image)
            kind = "full" if not awake or since_full >= FULL_REFRESH_EVERY else "partial"
            time.sleep(max(0.0, (target - datetime.now()).total_seconds() - lead[kind]))
            started = time.monotonic()
            if kind == "full":
                if awake:
                    epd.sleep()  # releases SPI/GPIO so init() can reopen them
                epd.init()
                awake = True
                epd.display_Base(buf)
                since_full = 0
            else:
                epd.display_Partial(buf)
                since_full += 1
            lead[kind] = time.monotonic() - started
            time.sleep(max(0.0, (target - datetime.now()).total_seconds()))
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # a second Ctrl+C must not cut the clear short
        if awake:
            clear_panel(epd, awake=True)


if __name__ == "__main__":
    main()
