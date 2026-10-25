#!/usr/bin/env python3
"""Render what the e-paper shows to a PNG, without the hardware.

Usage: python mock_display.py [--page clock|pokemon|holidays|matchday|table|bayern] [--live]
       [-o preview.png] [--scale 3]
By default sample data is used; --live fetches real weather/departures.
The pages other than the clock always fetch live data.
"""
import argparse
import sys
import time
import types
from datetime import datetime

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="use real network data")
    ap.add_argument("--page", choices=clock.PAGE_ORDER, default="clock")
    ap.add_argument("-o", "--output", default="preview.png")
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

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
