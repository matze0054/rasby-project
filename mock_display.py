#!/usr/bin/env python3
"""Render what the e-paper shows to a PNG, without the hardware.

Usage: python mock_display.py [--panel 2in9|7in5] [--page clock|pokemon|holidays|matchday|table|bayern]
       [--live] [-o preview.png] [--scale 3]   (--page applies to the 2.9" panel only)
By default sample data is used; --live fetches real weather/departures.
The pages other than the clock always fetch live data.
"""
import argparse
import sys
import time
import types
from datetime import datetime, timedelta

# Stub the Waveshare driver so epaper_clock can be imported off-device.
_driver = types.ModuleType("waveshare_epd.epd2in9_V2")
_driver.epdconfig = types.SimpleNamespace(module_exit=lambda cleanup=True: None)
_pkg = types.ModuleType("waveshare_epd")
_pkg.epd2in9_V2 = _driver
sys.modules.update({"waveshare_epd": _pkg, "waveshare_epd.epd2in9_V2": _driver})

import epaper_clock as clock  # noqa: E402
from PIL import Image  # noqa: E402

WIDTH, HEIGHT = 128, 296  # native panel size, as passed to render()


def sample_departures():
    now = time.time() * 1000
    rows = [("U6", "Klinikum Großhadern", 3), ("U6", "Garching-Forschungszentrum", 7),
            ("U6", "Klinikum Großhadern", 13), ("U6", "Garching-Forschungszentrum", 17),
            ("U6", "Klinikum Großhadern", 23)]
    return [{"label": l, "destination": d,
             "realtimeDepartureTime": now + m * 60000 + 30000} for l, d, m in rows]


def sample_dashboard():
    now = datetime.now()
    start = now.replace(minute=0, second=0, microsecond=0)
    sample_rain = [0, 5, 20, 45, 70, 90, 100, 60, 30, 10, 0, 0, 15, 25]
    sample_temp = [8.4, 9.1, 10.5, 12.0, 13.4, 14.2, 13.8, 12.6, 11.0, 9.8, 9.0, 8.2, 7.9, 7.5]
    weather = {
        "temp": 12.4, "label": "Partly cloudy",
        "hours": [(start + timedelta(hours=i), r, t)
                  for i, (r, t) in enumerate(zip(sample_rain, sample_temp))],
    }
    departures = [(row["label"], row["destination"], int((row["realtimeDepartureTime"] - time.time() * 1000) // 60000))
                  for row in sample_departures()]
    return weather, departures + [("U6", "Klinikum Großhadern", 33), ("U6", "Garching-Forschungszentrum", 37),
                                  ("U6", "Klinikum Großhadern", 43)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=("2in9", "7in5"), default="2in9",
                    help="7in5 renders the 800x480 dashboard of epaper_clock_7in5.py")
    ap.add_argument("--live", action="store_true", help="use real network data")
    ap.add_argument("--bayern-home", action="store_true", help="7in5: preview the Bayern home-game banner")
    ap.add_argument("--page", choices=clock.PAGE_ORDER, default="clock", help="2in9 only")
    ap.add_argument("-o", "--output", default="preview.png")
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    if args.panel == "7in5":
        import epaper_clock_7in5 as dash

        now = datetime.now()
        if args.bayern_home:
            dash.bayern_home_today = lambda now: (now.replace(hour=18, minute=30), "upcoming", None)
        if args.live:
            weather, departures = dash.fetch_weather(), dash.fetch_departures(now.timestamp())
        else:
            weather, departures = sample_dashboard()
        image = dash.render(now, weather, departures).convert("L")
        if args.scale != 1:
            image = image.resize((image.width * args.scale, image.height * args.scale), Image.NEAREST)
        image.save(args.output)
        print(f"Saved {args.output} ({image.width}x{image.height})")
        return

    if args.live:
        weather = clock.fetch_weather()
    else:
        weather = "12°C  Partly cloudy"
        clock._station_id = "sample"
        clock.mvg_get = lambda path, params: sample_departures()

    image = clock.render_page(args.page, WIDTH, HEIGHT, weather, datetime.now())
    image = image.resize((image.width * args.scale, image.height * args.scale), Image.NEAREST)
    image.save(args.output)
    print(f"Saved {args.output} ({image.width}x{image.height})")

if __name__ == "__main__":
    main()
