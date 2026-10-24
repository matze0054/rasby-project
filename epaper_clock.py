#!/usr/bin/env python3
"""Clock + date + weather for a Waveshare 2.9" e-paper on a Raspberry Pi."""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Match the model printed on your module: epd2in9 (V1), epd2in9_V2, epd2in9b, ...
from waveshare_epd import epd2in9_V2 as epd_driver

LATITUDE = 48.22  # 80939 Munich
LONGITUDE = 11.62
REFRESH_SECONDS = 60
WEATHER_EVERY = 5  # refresh weather every N display refreshes
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


def fetch_departures():
    """Return a list of 'U6 Destination  4'' strings for the station."""
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
        now = time.time()
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


def render(width, height, weather):
    # Draw in landscape: the panel is 128x296 natively.
    image = Image.new("1", (height, width), 255)
    draw = ImageDraw.Draw(image)
    now = datetime.now()

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
    for i, (text, mins) in enumerate(fetch_departures()):
        y = 24 + i * 20
        draw.text((split + 8, y), text, font=f_dep, fill=0)
        draw.text((height - 4, y), mins, font=f_dep, fill=0, anchor="ra")
    return image


def main():
    epd = epd_driver.EPD()
    try:
        weather = "Weather unavailable"
        tick = 0
        while True:
            if tick % WEATHER_EVERY == 0:
                weather = fetch_weather()
            tick += 1
            epd.init()
            image = render(epd.width, epd.height, weather)
            epd.display(epd.getbuffer(image))
            epd.sleep()
            time.sleep(REFRESH_SECONDS)
    except KeyboardInterrupt:
        epd_driver.epdconfig.module_exit(cleanup=True)


if __name__ == "__main__":
    main()
