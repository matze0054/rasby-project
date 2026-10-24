#!/usr/bin/env python3
"""Clock + date + weather for a Waveshare 2.9" e-paper on a Raspberry Pi."""
import json
import time
import urllib.request
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Match the model printed on your module: epd2in9 (V1), epd2in9_V2, epd2in9b, ...
from waveshare_epd import epd2in9_V2 as epd_driver

LATITUDE = 48.22  # 80939 Munich
LONGITUDE = 11.62
REFRESH_SECONDS = 300

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


def render(width, height):
    # Draw in landscape: the panel is 128x296 natively.
    image = Image.new("1", (height, width), 255)
    draw = ImageDraw.Draw(image)
    now = datetime.now()

    draw.text((10, 5), now.strftime("%H:%M"), font=font(FONT_BOLD, 64), fill=0)
    draw.text((10, 78), now.strftime("%A, %d %B"), font=font(FONT_REG, 18), fill=0)
    draw.line((10, 105, height - 10, 105), fill=0)
    draw.text((10, 108), fetch_weather(), font=font(FONT_REG, 16), fill=0)
    return image


def main():
    epd = epd_driver.EPD()
    try:
        while True:
            epd.init()
            image = render(epd.width, epd.height)
            epd.display(epd.getbuffer(image))
            epd.sleep()
            time.sleep(REFRESH_SECONDS)
    except KeyboardInterrupt:
        epd_driver.epdconfig.module_exit(cleanup=True)


if __name__ == "__main__":
    main()
