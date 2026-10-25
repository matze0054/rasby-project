#!/usr/bin/env python3
"""Extra e-paper pages: Pokémon of the day, next public holidays, Bundesliga (OpenLigaDB)."""
import io
import json
import random
import time
import urllib.request
from datetime import date, datetime, timedelta

from PIL import Image, ImageDraw, ImageFont, ImageOps

REGION = "DE-BY"  # Nager.Date region code used to filter public holidays
REGION_NAME = "Bavaria"
HOLIDAY_ROWS = 5
POKEMON_COUNT = 1025  # size of the National Pokédex at the time of writing
SPRITE_SIZE = 116
OPENLIGA = "https://api.openligadb.de"
LEAGUE = "bl1"  # 1. Bundesliga
TEAM_ID = 40  # FC Bayern München
LEAGUE_LABELS = {"bl1": "Bundesliga", "ucl": "Champions League", "dfb": "DFB-Pokal"}
USER_AGENT = "epaper-clock/1.0 (personal e-paper project)"

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

_cache = {}


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


def _cached(key, stamp, load):
    """Cache load() per stamp (a date or a time bucket); if a reload fails, keep the previous value."""
    entry = _cache.get(key)
    if entry and entry[0] == stamp:
        return entry[1]
    try:
        value = load()
    except Exception:
        return entry[1] if entry else None
    _cache[key] = (stamp, value)
    return value


def _ellipsize(text, fnt, max_width):
    if fnt.getlength(text) <= max_width:
        return text
    while text and fnt.getlength(text + "…") > max_width:
        text = text[:-1]
    return text.rstrip() + "…"


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
    mon = _cached("pokemon", today, lambda: _load_pokemon(today))
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
    loaded = _cached("holidays", today, lambda: _load_holidays(today))
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


def _openliga(path):
    return _fetch_json(f"{OPENLIGA}{path}")


def _bucket(seconds):
    return int(time.time() // seconds)


def _table(now):
    season = now.year if now.month >= 7 else now.year - 1
    return _cached("table", _bucket(300), lambda: _openliga(f"/getbltable/{LEAGUE}/{season}"))


def _short(team):
    return team["shortName"] or team["teamName"]


def _match_info(match, now):
    """Return (state, score): state is 'upcoming', 'live' or 'final'; score is (home, away) or None."""
    kickoff = datetime.fromisoformat(match["matchDateTime"])
    results = {r["resultTypeID"]: r for r in match["matchResults"]}
    if 2 in results:
        score = (results[2]["pointsTeam1"], results[2]["pointsTeam2"])
    elif match["goals"]:
        last = max(match["goals"], key=lambda g: g["scoreTeam1"] + g["scoreTeam2"])
        score = (last["scoreTeam1"], last["scoreTeam2"])
    elif 1 in results:
        score = (results[1]["pointsTeam1"], results[1]["pointsTeam2"])
    else:
        score = None
    if match["matchIsFinished"]:
        state = "final"
    elif kickoff > now:
        state = "upcoming"
    elif now - kickoff <= timedelta(hours=3):
        state, score = "live", score or (0, 0)
    else:
        state = "final"  # kicked off long ago but never marked finished
    return state, score


def render_matchday(width, height, now):
    matches = _cached("matchday", _bucket(60), lambda: _openliga(f"/getmatchdata/{LEAGUE}"))
    if not matches:
        return _message(width, height, "Bundesliga", "OpenLigaDB unavailable")

    image, draw = _canvas(width, height)
    small, bold = font(FONT_REG, 11), font(FONT_BOLD, 11)
    matchday = matches[0]["group"]["groupOrderID"]
    draw.text((6, 1), f"Bundesliga · Matchday {matchday}", font=font(FONT_BOLD, 12), fill=0)
    draw.line((6, 17, height - 6, 17), fill=0)
    for i, m in enumerate(matches[:9]):
        y = 19 + i * 12
        state, score = _match_info(m, now)
        ink = 0
        if TEAM_ID in (m["team1"]["teamId"], m["team2"]["teamId"]):
            draw.rectangle((2, y, height - 3, y + 11), fill=0)
            ink = 255
        kickoff = datetime.fromisoformat(m["matchDateTime"])
        left = {"final": "FT", "live": "LIVE", "upcoming": _kickoff_text(kickoff, now)}[state]
        middle = f"{score[0]}:{score[1]}" if score else "-:-"
        draw.text((6, y), left, font=bold if state == "live" else small, fill=ink)
        home = _ellipsize(_short(m["team1"]), small, 98)
        draw.text((160, y), home, font=small, fill=ink, anchor="ra")
        draw.text((178, y), middle, font=bold, fill=ink, anchor="ma")
        draw.text((196, y), _ellipsize(_short(m["team2"]), small, 94), font=small, fill=ink)
    return image


def _kickoff_text(kickoff, now):
    return kickoff.strftime("%H:%M" if kickoff.date() == now.date() else "%a %H:%M")


def render_table(width, height, now):
    table = _table(now)
    if not table:
        return _message(width, height, "Bundesliga", "OpenLigaDB unavailable")

    ranked = list(enumerate(table, 1))
    bayern = next((row for row in ranked if row[1]["teamInfoId"] == TEAM_ID), None)
    shown = ranked[:6] + [bayern] if bayern and bayern[0] > 7 else ranked[:7]

    image, draw = _canvas(width, height)
    small, bold = font(FONT_REG, 12), font(FONT_BOLD, 12)
    draw.text((6, 1), "Bundesliga table", font=bold, fill=0)
    for label, x in (("P", 168), ("W-D-L", 218), ("GD", 256), ("Pts", 290)):
        draw.text((x, 4), label, font=font(FONT_REG, 10), fill=0, anchor="ra")
    draw.line((6, 19, height - 6, 19), fill=0)
    for i, (rank, t) in enumerate(shown):
        y = 22 + i * 15
        ink, row_font = 0, small
        if t["teamInfoId"] == TEAM_ID:
            draw.rectangle((2, y - 1, height - 3, y + 13), fill=0)
            ink, row_font = 255, bold
        draw.text((22, y), str(rank), font=row_font, fill=ink, anchor="ra")
        draw.text((30, y), _ellipsize(_short(t), row_font, 115), font=row_font, fill=ink)
        draw.text((168, y), str(t["matches"]), font=row_font, fill=ink, anchor="ra")
        record = f"{t['won']}-{t['draw']}-{t['lost']}"
        draw.text((218, y), record, font=row_font, fill=ink, anchor="ra")
        draw.text((256, y), f"{t['goalDiff']:+d}", font=row_font, fill=ink, anchor="ra")
        draw.text((290, y), str(t["points"]), font=bold, fill=ink, anchor="ra")
    return image


def _scorers(match, team):
    by_player = {}
    for g in sorted(match["goals"], key=lambda g: g["matchMinute"] or 0):
        if g["scoringTeamId"] != team["teamId"]:
            continue
        tag = "(P)" if g["isPenalty"] else "(OG)" if g["isOwnGoal"] else ""
        minute = f"{g['matchMinute']}'" if g["matchMinute"] else ""
        by_player.setdefault(g["goalGetterName"], []).append(minute + tag)
    return ", ".join(f"{name} {' '.join(minutes)}".strip() for name, minutes in by_player.items())


def _countdown(delta):
    minutes = int(delta.total_seconds() // 60)
    if minutes < 60:
        return f"in {max(minutes, 0)} min"
    if minutes < 24 * 60:
        return f"in {minutes // 60} h {minutes % 60:02d} min"
    return f"in {delta.days} days"


def _form_letter(match, score):
    bayern_home = match["team1"]["teamId"] == TEAM_ID
    mine, theirs = score if bayern_home else score[::-1]
    return "W" if mine > theirs else "L" if mine < theirs else "D"


def render_bayern(width, height, now):
    path = f"/getmatchesbyteamid/{TEAM_ID}/6/6"
    matches = _cached("bayern", _bucket(60), lambda: _openliga(path))
    if not matches:
        return _message(width, height, "FC Bayern", "OpenLigaDB unavailable")

    matches = sorted(matches, key=lambda m: m["matchDateTime"])
    info = [(m, *_match_info(m, now)) for m in matches]
    finished = [(m, score) for m, state, score in info if state == "final" and score]
    current = next(((m, state, score) for m, state, score in info if state != "final"), None)

    image, draw = _canvas(width, height)
    bold14, bold15, small, tiny = (
        font(FONT_BOLD, 14), font(FONT_BOLD, 15), font(FONT_REG, 11), font(FONT_REG, 10)
    )
    title = "FC Bayern"
    table = _table(now) or []
    place = next(((i, t) for i, t in enumerate(table, 1) if t["teamInfoId"] == TEAM_ID), None)
    if place:
        title += f" · #{place[0]} · {place[1]['points']} pts"
    draw.text((6, 2), title, font=bold14, fill=0)
    form = " ".join(_form_letter(m, score) for m, score in finished[-5:])
    draw.text((height - 6, 4), form, font=font(FONT_BOLD, 12), fill=0, anchor="ra")
    draw.line((6, 22, height - 6, 22), fill=0)

    if finished:
        m, (home, away) = finished[-1]
        kickoff = datetime.fromisoformat(m["matchDateTime"])
        label = LEAGUE_LABELS.get(m["leagueShortcut"], m["leagueName"])
        draw.text((6, 26), f"Last · {label} · {kickoff:%a %d %b}", font=tiny, fill=0)
        headline = f"{_short(m['team1'])} {home}:{away} {_short(m['team2'])}"
        draw.text((6, 38), _ellipsize(headline, bold15, height - 12), font=bold15, fill=0)
        teams = sorted((m["team1"], m["team2"]), key=lambda t: t["teamId"] != TEAM_ID)
        for i, team in enumerate(teams):
            text = _scorers(m, team)
            if text:
                line = f"{_short(team)}: {text}"
                draw.text((6, 58 + i * 13), _ellipsize(line, small, height - 12), font=small, fill=0)

    draw.line((6, 88, height - 6, 88), fill=0)
    if current:
        m, state, score = current
        kickoff = datetime.fromisoformat(m["matchDateTime"])
        label = LEAGUE_LABELS.get(m["leagueShortcut"], m["leagueName"])
        kind = "Live" if state == "live" else "Next"
        draw.text((6, 92), f"{kind} · {label} · {kickoff:%a %d %b %H:%M}", font=tiny, fill=0)
        if state == "live":
            headline = f"{_short(m['team1'])} {score[0]}:{score[1]} {_short(m['team2'])}"
            side = "LIVE"
        else:
            headline = f"{_short(m['team1'])} – {_short(m['team2'])}"
            side = _countdown(kickoff - now)
        draw.text((height - 6, 106), side, font=font(FONT_REG, 12), fill=0, anchor="ra")
        room = height - 12 - font(FONT_REG, 12).getlength(side) - 8
        draw.text((6, 104), _ellipsize(headline, bold15, room), font=bold15, fill=0)
    return image


PAGES = {
    "pokemon": render_pokemon,
    "holidays": render_holidays,
    #"matchday": render_matchday,
    #"table": render_table,
    #"bayern": render_bayern,
}


def render(page, width, height, now):
    renderer = PAGES[page]
    try:
        return renderer(width, height, now)
    except Exception:
        return _message(width, height, page.title(), "Data unavailable")
