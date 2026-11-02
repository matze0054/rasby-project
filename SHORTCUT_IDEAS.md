# iPhone Shortcuts: ideas for the e-paper dashboard

Status quo: one Shortcut ("Pi off") runs `Run Script Over SSH` against a key restricted to `shutdown`/`cancel` (see [IPHONE_SHUTDOWN.md](IPHONE_SHUTDOWN.md)). The same mechanism (SSH with a forced command, or HTTP to a tiny service on the Pi) can do much more. Ideas only, nothing implemented.

## 1. Control the display
- **Page picker**: a menu (Pokemon, Holidays, Matchday, Table, Bayern, Clock) that jumps straight to that page of `fun_screen.py`.
- **Next / previous page** buttons, or "pause rotation" while you show someone a page.
- **Force refresh now** (e.g. after a goal) and **full-refresh/de-ghost** to clear e-paper ghosting.
- **Night mode**: stop refreshing 23:00-06:00, via Shortcuts Automation (time of day) or Focus mode "Sleep" on/off.
- **Orientation / theme toggle** (inverted, big-clock only, minimal).

## 2. Push content from the phone
- **Quick note / message**: "Share Sheet -> Pi" shows a text (shopping item, "Call mum", door code) on the screen for N minutes.
- **Share a URL or photo**: dither the image to 1-bit and show it (family photo of the day, a QR code for Wi-Fi guests, a boarding pass QR).
- **Dictate a reminder** with Siri ("Hey Siri, put on the display: buy milk").
- **Countdown timer** (cooking, parking) with a big number on the display.
- **Clipboard to display**: show whatever is on the iPhone clipboard.

## 3. Phone data to the display
- Calendar: next event / today's agenda from the iPhone Calendar (no Google API needed).
- Reminders list (today's open tasks), Health data (steps, sleep), battery level of iPhone/AirPods.
- Current location / commute time to work from Maps, "leave now" hint.
- Now Playing track, or the weather from the Weather app instead of an API key.
- Package-tracking or flight status via Shortcuts' web actions.

## 4. Football extras (Bayern / table / matchday pages)
- Notification when a match starts or a goal is scored -> display flips to the match page (iOS push through ntfy/Pushover plus a Shortcut automation, or the Pi polls openLigaDB and pings the phone).
- "Who plays today?" Siri query reading the data back.
- Pick the favourite team via a list so the Bayern page becomes configurable.

## 5. Operate the Pi itself
- **Reboot**, **restart the dashboard service**, **update (git pull) and restart** with one tap.
- **Status card**: IP, Wi-Fi signal, CPU temperature, uptime, last successful refresh, disk space, shown as an iOS notification.
- **Wake/power plan**: scheduled "Pi off" at night and a smart plug (HomeKit/Shelly) as the "on" switch, so the whole off/on cycle is hands-free.
- **Fetch logs** (last 20 lines) when something looks wrong, and a "display self-test" pattern.
- **Backup** the SD card config to iCloud/NAS.

## 6. Automations (no tapping)
- Arrive home / leave home (location trigger): wake the screen / show "away" page and save refreshes.
- Wi-Fi connect trigger: when the iPhone joins home Wi-Fi, sync calendar and reminders to the Pi.
- Alarm dismissed in the morning: switch to the "morning" page (weather, calendar, public transport).
- Charger plugged in at night: switch to a calm clock.
- NFC tags: stick a tag on the desk, tap -> "focus timer" page; tag at door -> "leaving" checklist.

## 7. Smart-home bridge
- The Pi as a status board for HomeKit: window open, washing machine done, front door locked.
- Buttons for scenes (living room lights) next to the "Pi off" shortcut, in one Shortcuts folder / home-screen widget.

## 8. Fun
- "Pokemon of the day" reroll, random fact, joke or quote on shake.
- Shared whiteboard: family members send a message to the display from their own shortcut.
- Game-like pages: score counter for board games, dice roll, coin flip.

## Technical building blocks (for later)
- **Keep SSH forced-command pattern** for simple actions; extend `pi_power.sh` into a dispatcher with a whitelist (`page <name>`, `refresh`, `status`, `note <text>`), never arbitrary shell.
- **Or add a tiny local HTTP endpoint** (Flask, LAN-only, token header) so Shortcuts uses `Get Contents of URL` (JSON in/out, easier than SSH, supports images and large text).
- Shortcuts features that help: Share Sheet input, Siri phrases, Automations (time, location, Wi-Fi, Focus, charger, NFC), widgets, Action Button on newer iPhones, Apple Watch.
- Security: LAN only, restrictive key or token, validate and length-limit text, rate-limit refreshes (e-paper wears out with too frequent full refreshes).
- Constraint: works only on the home network unless a VPN (Tailscale) or Raspberry Pi Connect is used.

## Suggested first picks
1. Page picker + refresh now (small, daily useful).
2. "Send a note to the display" via the Share Sheet.
3. Calendar agenda page fed from the phone.
4. Pi status notification and night-mode automation.
