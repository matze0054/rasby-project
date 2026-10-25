#!/usr/bin/env python3
"""Extra e-paper pages: Wikipedia 'On this day', Pokémon of the day, next public holidays."""
import io
import json
import random
import urllib.request
from datetime import date

from PIL import Image, ImageDraw, ImageFont, ImageOps

REGION = "DE-BY"  # Nager.Date region code used to filter public holidays
REGION_NAME = "Bavaria"
HOLIDAY_ROWS = 5
POKEMON_COUNT = 1025  # size of the National Pokédex at the time of writing
SPRITE_SIZE = 116
USER_AGENT = "epaper-clock/1.0 (personal e-paper project)"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

_cache = {}
_event_visits = 0


def font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


def _fetch_json(url):
    return json.loads(_fetch(url))


def _daily(key, today, load):
    """Cache load() per day; if a reload fails, keep serving the previous value."""
    entry = _cache.get(key)
    if entry and entry[0] == today:
        return entry[1]
    try:
        value = load()
    except Exception:
        return entry[1] if entry else None
    _cache[key] = (today, value)
    return value


def _ellipsize(text, fnt, max_width):
    if fnt.getlength(text) <= max_width:
        return text
    while text and fnt.getlength(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


def _wrap(text, fnt, max_width, max_lines):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and fnt.getlength(trial) > max_width:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _ellipsize(lines[-1] + "…", fnt, max_width)
    return lines


def _canvas(width, height):
    # Draw in landscape: the panel is 128x296 natively.
    image = Image.new("1", (height, width), 255)
    return image, ImageDraw.Draw(image)


def _message(width, height, title, text):
    image, draw = _canvas(width, height)
    draw.text((10, 3), title, font=font(FONT_BOLD, 14), fill=0)
    draw.line((10, 26, height - 10, 26), fill=0)
    draw.text((height // 2, width // 2 + 12), text, font=font(FONT_REG, 14), fill=0, anchor="mm")
    return image


def _load_events(today):
    data = _fetch_json(
        "https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/"
        f"{today.month:02d}/{today.day:02d}"
    )
    events = [(e["year"], e["text"]) for e in data["events"] if len(e["text"]) <= 220]
    random.shuffle(events)
    return events


def render_on_this_day(width, height, now):
    global _event_visits
    today = now.date()
    events = _daily("events", today, lambda: _load_events(today))
    if not events:
        return _message(width, height, "On this day", "Wikipedia unavailable")
    year, text = events[_event_visits % len(events)]
    _event_visits += 1

    image, draw = _canvas(width, height)
    draw.text((10, 3), f"On this day · {today.day} {today:%b}", font=font(FONT_BOLD, 14), fill=0)
    draw.text((height - 10, 0), str(year), font=font(FONT_BOLD, 20), fill=0, anchor="ra")
    draw.line((10, 26, height - 10, 26), fill=0)
    body_size, line_height, max_lines = (17, 22, 4) if len(text) <= 90 else (13, 16, 6)
    body = font(FONT_REG, body_size)
    for i, line in enumerate(_wrap(text, body, height - 20, max_lines)):
        draw.text((10, 32 + i * line_height), line, font=body, fill=0)
    return image


def _load_pokemon(today):
    pid = random.Random(today.toordinal()).randint(1, POKEMON_COUNT)
    data = _fetch_json(f"https://pokeapi.co/api/v2/pokemon/{pid}")
    sprites = data["sprites"]
    art_url = sprites["other"]["official-artwork"]["front_default"] or sprites["front_default"]
    art = Image.open(io.BytesIO(_fetch(art_url))).convert("RGBA")
    flat = Image.new("RGBA", art.size, "white")
    flat.alpha_composite(art)
    gray = ImageOps.autocontrast(flat.convert("L"), cutoff=2)
    gray = gray.point(lambda v: round(255 * (v / 255) ** 0.6))  # lift midtones, dithering darkens them
    gray.thumbnail((SPRITE_SIZE, SPRITE_SIZE), Image.Resampling.LANCZOS)
    return {
        "id": data["id"],
        "name": data["name"].replace("-", " ").title(),
        "types": [t["type"]["name"].title() for t in data["types"]],
        "height": data["height"] / 10,  # decimetres to metres
        "weight": data["weight"] / 10,  # hectograms to kilograms
        "sprite": gray.convert("1"),  # Floyd-Steinberg dithering
    }


def render_pokemon(width, height, now):
    today = now.date()
    mon = _daily("pokemon", today, lambda: _load_pokemon(today))
    if not mon:
        return _message(width, height, "Pokémon of the day", "PokéAPI unavailable")

    image, draw = _canvas(width, height)
    sprite = mon["sprite"]
    image.paste(
        sprite,
        (6 + (SPRITE_SIZE - sprite.width) // 2, 6 + (SPRITE_SIZE - sprite.height) // 2),
    )
    x = SPRITE_SIZE + 16
    room = height - x - 8
    for size in (22, 19, 16, 13):
        name_font = font(FONT_BOLD, size)
        if name_font.getlength(mon["name"]) <= room:
            break
    small = font(FONT_REG, 12)
    draw.text((x, 3), "Pokémon of the day", font=font(FONT_REG, 11), fill=0)
    draw.text((x, 20), mon["name"], font=name_font, fill=0)
    draw.text((x, 52), f"No. {mon['id']}", font=small, fill=0)
    draw.text((x, 70), " / ".join(mon["types"]), font=font(FONT_BOLD, 14), fill=0)
    draw.text((x, 94), f"Height  {mon['height']:.1f} m", font=small, fill=0)
    draw.text((x, 110), f"Weight  {mon['weight']:.1f} kg", font=small, fill=0)
    return image


def _load_holidays(today):
    data = _fetch_json("https://date.nager.at/api/v3/NextPublicHolidays/DE")
    return [
        (date.fromisoformat(h["date"]), h["localName"])
        for h in data
        if h["global"] or REGION in (h["counties"] or [])
    ]


def render_holidays(width, height, now):
    today = now.date()
    loaded = _daily("holidays", today, lambda: _load_holidays(today))
    holidays = [h for h in loaded or [] if h[0] >= today][:HOLIDAY_ROWS]
    if not holidays:
        return _message(width, height, "Public holidays", "Nager.Date unavailable")

    image, draw = _canvas(width, height)
    draw.text((10, 3), f"Public holidays · {REGION_NAME}", font=font(FONT_BOLD, 14), fill=0)
    draw.line((10, 26, height - 10, 26), fill=0)
    reg, bold = font(FONT_REG, 12), font(FONT_BOLD, 12)
    for i, (day, name) in enumerate(holidays):
        y = 33 + i * 19
        days = (day - today).days
        when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} d"
        row_font = bold if i == 0 else reg
        right_width = row_font.getlength(when)
        name_room = height - 10 - right_width - 4 - 90
        draw.text((10, y), f"{day:%a %d %b}", font=reg, fill=0)
        draw.text((90, y), _ellipsize(name, row_font, name_room), font=row_font, fill=0)
        draw.text((height - 10, y), when, font=row_font, fill=0, anchor="ra")
    return image


PAGES = {
    "wiki": render_on_this_day,
    "pokemon": render_pokemon,
    "holidays": render_holidays,
}
