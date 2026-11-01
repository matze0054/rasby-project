#!/usr/bin/env python3
"""Dashboard (clock, weather forecast, U-Bahn departures, next holiday and Bayern match)
for a Waveshare 7.5" e-paper driver HAT (V2, 800x480) stacked on a Raspberry Pi.

The HAT uses the standard Waveshare pins (SPI0.0, GPIO17/25/24/18), the same pins as the 2.9"
display, so epaper_clock.py and this script cannot run on the same Pi at the same time.
The panel is cleared to white on exit; `--clear` does only that.
"""
import argparse
import json
import signal
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

import fun_screen

LATITUDE = 48.22  # 80939 Munich
LONGITUDE = 11.62
STATION = "Kieferngarten"
MVG_API = "https://www.mvg.de/api/bgw-pt/v3"
MAX_DEPARTURES = 8
WEATHER_EVERY = 10  # minutes between weather fetches
RAIN_HOURS = 12  # hours shown in the rain-probability bar chart

# HAT pins (BCM numbers) when stacked on the 40-pin header; PIN_PWR = None if the HAT has no PWR pin.
PIN_RST, PIN_DC, PIN_BUSY, PIN_PWR = 17, 25, 24, 18
SPI_BUS, SPI_DEVICE = 0, 0

PARTIAL_REFRESH = True  # False: flash-free partial updates are replaced by fast full-frame refreshes
FULL_REFRESH_EVERY = 15  # refreshes (minutes) between full, flashing refreshes that clear ghosting
LEAD_SECONDS = {"partial": 1.0, "fast": 2.0, "full": 5.0}  # initial guesses of the refresh durations
ROTATE = 0  # 180 if the display is mounted upside down
CLEAR_ON_EXIT = True

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

WIDTH, HEIGHT = 800, 480
MARGIN = 24
SPLIT = 440  # x of the vertical divider between the two columns

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


def fit_font(path, text, max_size, max_width):
    for size in range(max_size, 9, -1):
        f = font(path, size)
        if f.getlength(text) <= max_width:
            return f
    return font(path, 10)


def ellipsize(text, fnt, max_width):
    if fnt.getlength(text) <= max_width:
        return text
    while text and fnt.getlength(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


# -- data ------------------------------------------------------------------------------


def fetch_weather():
    """Return the current weather and the hourly rain probability, or None if the request fails."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        "&current=temperature_2m,weather_code"
        "&hourly=precipitation_probability"
        "&timezone=auto&forecast_days=2"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        cur, hourly = data["current"], data["hourly"]
        hours = [
            (datetime.fromisoformat(t), p)
            for t, p in zip(hourly["time"], hourly["precipitation_probability"])
            if p is not None
        ]
        return {
            "temp": cur["temperature_2m"],
            "label": WEATHER_CODES.get(cur["weather_code"], "Unknown"),
            "hours": hours,
        }
    except Exception:
        return None


_station_id = None


def mvg_get(path, params):
    url = f"{MVG_API}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"User-Agent": "epaper-clock"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)


def fetch_departures(at):
    """Return [(line, destination, minutes)] for the station as of `at` (epoch seconds), or None."""
    global _station_id
    try:
        if _station_id is None:
            found = mvg_get("/locations", {"query": STATION})
            station = next(l for l in found if l.get("type") == "STATION" and "globalId" in l)
            _station_id = station["globalId"]
        deps = mvg_get(
            "/departures",
            {"globalId": _station_id, "limit": 20, "transportTypes": "UBAHN"},
        )
        rows = []
        for d in deps:
            if d.get("cancelled"):
                continue
            minutes = max(0, int((d["realtimeDepartureTime"] / 1000 - at) // 60))
            rows.append((d["label"], d["destination"], minutes))
            if len(rows) == MAX_DEPARTURES:
                break
        return rows
    except Exception:
        return None


def next_holiday(today):
    loaded = fun_screen._cached("holidays", today, lambda: fun_screen._load_holidays(today))
    return next(((d, n) for d, n in loaded or [] if d >= today), None)


def bayern_home_today(now):
    """Return (kickoff, state, score) if Bayern still has a home game today, else None."""
    path = f"/getmatchesbyteamid/{fun_screen.TEAM_ID}/1/3"
    matches = fun_screen._cached(
        "bayern7in5", fun_screen._bucket(1800), lambda: fun_screen._openliga(path)
    )
    for m in matches or []:
        kickoff = datetime.fromisoformat(m["matchDateTime"])
        if kickoff.date() != now.date() or m["team1"]["teamId"] != fun_screen.TEAM_ID:
            continue
        state, score = fun_screen._match_info(m, now)
        if state != "final":
            return kickoff, state, score
    return None


# -- drawing ---------------------------------------------------------------------------


def deg(value):
    """Rounded temperature with the degree sign; avoids "-0°"."""
    return f"{round(value) + 0}°"


def day_text(day, today):
    delta = (day - today).days
    return "today" if delta == 0 else "tomorrow" if delta == 1 else f"in {delta} days"


def draw_clock(draw, now):
    clock_font = fit_font(FONT_BOLD, "00:00", 120, SPLIT - MARGIN - 8)
    draw.text((MARGIN - 4, 112), f"{now:%H:%M}", font=clock_font, fill=0, anchor="ls")
    date_font = fit_font(FONT_REG, "Wednesday, 30 September", 30, SPLIT - 2 * MARGIN)
    draw.text((MARGIN, 152), f"{now:%A}, {now.day} {now:%B}", font=date_font, fill=0, anchor="ls")


def draw_rain_chart(draw, hours, now):
    """Bar chart of the rain probability for the next RAIN_HOURS hours."""
    start = now.replace(minute=0, second=0, microsecond=0)
    bars = [(t, p) for t, p in hours if t >= start][:RAIN_HOURS]
    if not bars:
        return
    left, right, top, bottom = MARGIN + 44, SPLIT - 20, 236, 314
    height = bottom - top
    label = font(FONT_REG, 13)
    for pct in (0, 50, 100):
        y = bottom - round(height * pct / 100)
        draw.text((left - 6, y), f"{pct}%", font=label, fill=0, anchor="rm")
        if pct:
            for x in range(left, right, 8):  # dashed guide line
                draw.line((x, y, x + 3, y), fill=0)
    draw.line((left, bottom, right, bottom), fill=0, width=2)
    slot = (right - left) / RAIN_HOURS
    for i, (t, pct) in enumerate(bars):
        x = left + i * slot
        bar_h = round(height * pct / 100)
        if pct and bar_h < 2:
            bar_h = 2
        if bar_h:
            draw.rectangle((x + 4, bottom - bar_h, x + slot - 4, bottom - 1), fill=0)
        if i % 3 == 0:
            draw.text((x + slot / 2, bottom + 18), f"{t:%H}:00", font=label, fill=0, anchor="ms")


def draw_weather(draw, weather, now):
    top = 172
    draw.line((MARGIN, top, SPLIT - 20, top), fill=0, width=2)
    if not weather:
        draw.text((MARGIN, top + 40), "Weather unavailable", font=font(FONT_REG, 26), fill=0)
        return
    big = font(FONT_BOLD, 56)
    base = top + 50
    draw.text((MARGIN, base), f"{deg(weather['temp'])}", font=big, fill=0, anchor="ls")
    x = MARGIN + big.getlength(f"{deg(weather['temp'])}") + 14
    caption = font(FONT_REG, 14)
    cap_w = caption.getlength("Rain chance")
    label = fit_font(FONT_BOLD, weather["label"], 28, SPLIT - 20 - x - cap_w - 10)
    draw.text((x, base), weather["label"], font=label, fill=0, anchor="ls")
    draw.text((SPLIT - 20, base - 18), "Rain chance", font=caption, fill=0, anchor="rs")
    draw.text((SPLIT - 20, base), f"next {RAIN_HOURS} h", font=caption, fill=0, anchor="rs")
    draw_rain_chart(draw, weather["hours"], now)


def draw_pokemon(image, draw, now):
    top = 342
    draw.line((MARGIN, top, SPLIT - 20, top), fill=0, width=2)
    today = now.date()
    mon = fun_screen._cached("pokemon", today, lambda: fun_screen._load_pokemon(today))
    if not mon:
        draw.text((MARGIN, top + 50), "Pokémon unavailable", font=font(FONT_REG, 22), fill=0)
        return
    sprite = mon["sprite"]
    box = fun_screen.SPRITE_SIZE
    image.paste(
        sprite, (MARGIN + (box - sprite.width) // 2, top + 10 + (box - sprite.height) // 2)
    )
    x = MARGIN + box + 18
    room = SPLIT - 20 - x
    draw.text((x, top + 24), "Pokémon of the day", font=font(FONT_REG, 15), fill=0, anchor="ls")
    name_font = fit_font(FONT_BOLD, mon["name"], 30, room)
    draw.text((x, top + 60), mon["name"], font=name_font, fill=0, anchor="ls")
    draw.text((x, top + 84), f"No. {mon['id']}", font=font(FONT_REG, 17), fill=0, anchor="ls")
    types = ellipsize(" / ".join(mon["types"]), font(FONT_BOLD, 19), room)
    draw.text((x, top + 106), types, font=font(FONT_BOLD, 19), fill=0, anchor="ls")
    draw.text(
        (x, top + 126), f"{mon['height']:.1f} m  ·  {mon['weight']:.1f} kg",
        font=font(FONT_REG, 16), fill=0, anchor="ls",
    )


def draw_departures(draw, departures, home_game):
    x0, x1 = SPLIT + 20, WIDTH - MARGIN
    draw.text((x0, 14), STATION, font=fit_font(FONT_BOLD, STATION, 32, x1 - x0), fill=0)
    draw.line((x0, 58, x1, 58), fill=0, width=2)
    y = 70
    if home_game:
        kickoff, state, score = home_game
        text = (
            f"Bayern home · LIVE {score[0]}:{score[1]}" if state == "live"
            else f"Bayern home today · {kickoff:%H:%M}"
        )
        draw.rounded_rectangle((x0, y, x1, y + 34), radius=6, fill=0)
        draw.text(
            ((x0 + x1) // 2, y + 18), text,
            font=fit_font(FONT_BOLD, text, 22, x1 - x0 - 16), fill=255, anchor="mm",
        )
        y += 44
        departures = departures[:MAX_DEPARTURES - 1] if departures else departures
    if not departures:
        text = "No departures" if departures == [] else "Departures n/a"
        draw.text((x0, y + 10), text, font=font(FONT_REG, 22), fill=0)
        return
    row_h = 44
    badge_w = 52
    dest_font, min_font, line_font = font(FONT_REG, 20), font(FONT_BOLD, 26), font(FONT_BOLD, 22)
    for i, (line, dest, minutes) in enumerate(departures):
        row = y + i * row_h
        draw.rounded_rectangle((x0, row, x0 + badge_w, row + 34), radius=6, fill=0)
        draw.text((x0 + badge_w // 2, row + 18), line, font=line_font, fill=255, anchor="mm")
        text = "now" if minutes == 0 else f"{minutes}'"
        draw.text((x1, row + 18), text, font=min_font, fill=0, anchor="rm")
        room = x1 - x0 - badge_w - 12 - min_font.getlength("99'") - 12
        draw.text(
            (x0 + badge_w + 12, row + 18), ellipsize(dest, dest_font, room),
            font=dest_font, fill=0, anchor="lm",
        )


def draw_holiday(draw, now):
    holiday = next_holiday(now.date())
    if not holiday:
        return
    x0, x1 = SPLIT + 20, WIDTH - MARGIN
    y = HEIGHT - 52
    draw.line((x0, y, x1, y), fill=0, width=2)
    f, fb = font(FONT_REG, 19), font(FONT_BOLD, 19)
    day, name = holiday
    when = day_text(day, now.date())
    room = x1 - x0 - fb.getlength(when) - 14
    draw.text((x0, HEIGHT - 18), ellipsize(name, f, room), font=f, fill=0, anchor="ls")
    draw.text((x1, HEIGHT - 18), when, font=fb, fill=0, anchor="rs")


def render(now, weather, departures):
    image = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(image)
    draw_clock(draw, now)
    draw_weather(draw, weather, now)
    draw_pokemon(image, draw, now)
    draw.line((SPLIT, 12, SPLIT, HEIGHT - 12), fill=0, width=2)
    draw_departures(draw, departures, bayern_home_today(now))
    draw_holiday(draw, now)
    image = image.convert("1")
    return image.rotate(ROTATE) if ROTATE else image


# -- hardware loop ---------------------------------------------------------------------


def _terminate(signum, frame):
    raise SystemExit(0)


def new_epd():
    from epd7in5_v2 import EPD

    return EPD(
        rst=PIN_RST, dc=PIN_DC, busy=PIN_BUSY, pwr=PIN_PWR,
        spi_bus=SPI_BUS, spi_device=SPI_DEVICE,
    )


def clear_panel(epd):
    epd.init()
    epd.clear()
    epd.sleep()


def main():
    parser = argparse.ArgumentParser(description="7.5\" e-paper dashboard")
    parser.add_argument("--clear", action="store_true", help="turn the panel white and exit")
    parser.add_argument("--once", action="store_true", help="show one full refresh and exit")
    args = parser.parse_args()

    epd = new_epd()
    if args.clear:
        clear_panel(epd)
        return

    signal.signal(signal.SIGTERM, _terminate)  # so `kill` and systemd stop also clear the panel
    awake = False
    try:
        weather, weather_at = None, None
        lead = dict(LEAD_SECONDS)
        since_full = 0
        in_partial = False
        while True:
            # Prepare the next minute, then push it early so the panel changes right on the boundary.
            now = datetime.now()
            target = now.replace(second=0, microsecond=0)
            if awake and not args.once:
                target += timedelta(minutes=1)  # the very first frame is shown immediately
            if weather_at is None or time.monotonic() - weather_at >= WEATHER_EVERY * 60:
                weather = fetch_weather() or weather
                weather_at = time.monotonic()
            image = render(target, weather, fetch_departures(target.timestamp()))
            buf = epd.getbuffer(image)

            if not awake or since_full >= FULL_REFRESH_EVERY or args.once:
                kind = "full"
            else:
                kind = "partial" if PARTIAL_REFRESH else "fast"
            time.sleep(max(0.0, (target - datetime.now()).total_seconds() - lead[kind]))
            started = time.monotonic()
            if kind == "full":
                epd.init()
                epd.display(buf)
                since_full, in_partial = 0, False
            elif kind == "fast":
                epd.init_fast()
                epd.display(buf)
                since_full += 1
            else:
                epd.display_partial(buf)
                since_full += 1
            awake = True
            lead[kind] = time.monotonic() - started
            if args.once:
                epd.sleep()
                awake = False
                return
            if PARTIAL_REFRESH and not in_partial:
                epd.init_part()  # switch the controller to partial mode for the next minutes
                in_partial = True
            time.sleep(max(0.0, (target - datetime.now()).total_seconds()))
    except KeyboardInterrupt:
        pass
    finally:
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # a second Ctrl+C must not cut the clear short
        if awake and CLEAR_ON_EXIT:
            clear_panel(epd)
        elif awake:
            epd.sleep()


if __name__ == "__main__":
    main()
