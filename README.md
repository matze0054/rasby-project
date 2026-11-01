# rasby-project

E-paper clock, date and weather display on a Raspberry Pi Zero 2 W. Two display setups, **one at a time** (both use the same Pi pins):

- Waveshare 2.9" e-paper module (V2, 296x128) on jumper wires: [epaper_clock.py](epaper_clock.py), wiring diagram: [wiring.svg](wiring.svg)
- Waveshare 7.5" e-paper driver HAT (Rev2.3, V2, 800x480) stacked on the Pi: [epaper_clock_7in5.py](epaper_clock_7in5.py) with its own driver [epd7in5_v2.py](epd7in5_v2.py), see [7.5" display](#75-display)
- Repo: https://github.com/matze0054/rasby-project (private)
- Turning the Pi and the dashboard on and off: [OPERATING.md](OPERATING.md)

## Hardware

- Raspberry Pi Zero 2 W, 64 GB microSD, header pins fitted
- Waveshare 2.9" e-paper module, V2 (label: Rev2.1, FPC-7519 rev.b), supplied 8-wire cable
- Display BS pad is set to "0" (4-line SPI)
- Waveshare 7.5" e-paper HAT (800x480, V2) with e-Paper Driver HAT Rev2.3, stacked on the header

## Current status (where I stopped)

- Pi boots, is online in Raspberry Pi Connect as `rasbyprojectmk` (user `mkern`), SSH and Connect are enabled.
- SPI is enabled, `waveshare_epd` is copied into `~/rasby-project/` on the Pi, and the repo is cloned there via a read-only deploy key.
- The display does not react yet: the Waveshare demo and `epaper_clock.py` run without errors, but the screen never changes.
- Diagnosis: GPIO24 (BUSY) floats and a clear call returns in 0.02 s (a real refresh takes 2 s or more), so the display is not answering. The photos showed several wires on the wrong Pi header pins (GND possibly on pin 4 = 5V).

## Next steps

1. Shut down and unplug the Pi: `sudo shutdown -h now`.
2. Rewire exactly as below, then power on.
3. Test BUSY:

   ```bash
   pinctrl set 24 ip pu; pinctrl get 24   # expect lo
   pinctrl set 24 ip pn
   ```

4. Run the script:

   ```bash
   cd ~/rasby-project && python3 epaper_clock.py
   ```

   The screen should flash and show the time, date and weather.
5. If BUSY still reads `hi`: reseat every wire, try another jumper for BUSY and VCC, move VCC to pin 17 and GND to pin 9 or 14, and send a top-down photo of the header.
6. If BUSY reads `lo` but the clear is still fast (< 0.5 s): recheck DC, CS, RST and DIN.
7. If the controller works (clear takes 2 s or more) but the screen stays blank: suspect the panel or its flat cable, and contact Waveshare or the seller.

## Wiring

Count header columns from the SD-card end (column 1 = pins 1 and 2). Odd pins are the inner row (nearer the board centre), even pins the outer (edge) row. Wire with the Pi powered off. See [wiring.svg](wiring.svg).

| Wire | Display pin | Pi pin | GPIO | Row, column |
|---|---|---|---|---|
| grey | VCC | 1 | 3V3 | inner, 1 |
| brown | GND | 6 | GND | outer, 3 |
| white | RST | 11 | GPIO17 | inner, 6 |
| purple | BUSY | 18 | GPIO24 | outer, 9 |
| blue | DIN | 19 | GPIO10 | inner, 10 |
| green | DC | 22 | GPIO25 | outer, 11 |
| yellow | CLK | 23 | GPIO11 | inner, 12 |
| orange | CS | 24 | GPIO8 | outer, 12 |

## 7.5" display

Waveshare 7.5inch e-Paper HAT, **V2** (800x480, black/white, SPI, 3.3 V/5 V tolerant), driver HAT Rev2.3. Layout: large clock and date, current temperature and conditions with a bar chart of the rain probability for the next 12 hours (`RAIN_HOURS`), and the Pokémon of the day (left); the next 8 U-Bahn departures (right), with a banner above them when FC Bayern plays at home that day (kick-off time, or LIVE and the score during the match), and the next public holiday at the bottom right. Preview without hardware: `python mock_display.py --panel 7in5` (add `--live` for real data, `--bayern-home` to see the banner).

### Hardware setup

The HAT plugs straight onto the Pi's 40-pin header and uses the standard Waveshare pins: SPI0.0 (MOSI GPIO10, SCLK GPIO11, CS GPIO8), RST GPIO17, DC GPIO25, BUSY GPIO24 and PWR GPIO18. These are the same pins the 2.9" module uses, so only one of the two can be connected and running at a time:

1. Shut the Pi down and unplug it (`sudo shutdown -h now`).
2. Remove the 2.9" wires from the header (the HAT covers the header anyway).
3. Check the HAT's switches: interface config on **4-line SPI (0)** (the default). Leave the display config switch as delivered unless Waveshare's wiki for the 7.5" V2 says otherwise.
4. Plug the HAT onto the header, aligned so that pin 1 matches, and connect the flat cable of the 7.5" panel to the HAT's FPC connector (flip the latch, insert the cable with the contacts facing the board, close the latch).
5. Power the Pi on.

Switching back to the 2.9" later means removing the HAT and re-wiring as in [Wiring](#wiring) (and the 2.9" script runs only while the HAT is not connected).

### Pi setup

SPI0 is already enabled (see below). Nothing else to configure:

```bash
ls /dev/spidev0.*                      # expect /dev/spidev0.0 and /dev/spidev0.1
cd ~/rasby-project && git pull
```

The 7.5" script needs the same packages as the 2.9" one (`python3-pil python3-spidev python3-gpiozero python3-lgpio fonts-dejavu-core`); it does not use the `waveshare_epd` folder. The pins are constants at the top of the script (`PIN_PWR = None` if your HAT has no PWR pin).

### Run

```bash
python3 epaper_clock_7in5.py --once    # one full refresh, then exit (first test, takes about 5 s)
python3 epaper_clock_7in5.py           # runs until Ctrl+C or `kill`, clears the panel on exit
python3 epaper_clock_7in5.py --clear   # only turn the panel white, e.g. after a power loss
```

The panel is refreshed every minute at :00 with a flash-free partial refresh, and every 15 minutes with a full (flashing) refresh to clear ghosting. Settings (location, station, pins, refresh behaviour, `ROTATE`: 180 = upside down, 0 = normal) are constants at the top of the script.

### Troubleshooting

- `FileNotFoundError: /dev/spidev0.0`: SPI is off, run `sudo raspi-config nonint do_spi 0` and reboot.
- `GPIOPinInUse`: another script (for example `epaper_clock.py`) is still running and holds the pins.
- The script hangs at the first refresh: BUSY is not read or the panel is not powered. Reseat the HAT on the header (all 40 pins must make contact) and check the panel's flat cable; `pinctrl get 24` shows the BUSY level.
- Image mirrored or upside down: set `ROTATE = 180` (upside down). Mirrored output is not expected, check you use the V2 driver.
- Grey or washed-out image: Waveshare notes an alternative `0x50` init for this case, see the commented lines in their `epd7in5_V2.py`; adjust `init()` in [epd7in5_v2.py](epd7in5_v2.py).
- Partial refreshes look wrong: set `PARTIAL_REFRESH = False` for fast full-frame refreshes instead.
- Do not leave a Waveshare panel without refreshing for days while powered; the scripts refresh every minute and clear the panel on exit.

### Run at boot (systemd)

Running the script in a terminal ties it to that session: closing the terminal or losing the Raspberry Pi Connect/SSH connection kills it. The systemd service [epaper-7in5.service](epaper-7in5.service) runs it independently of any login, starts it at boot (after the network and the clock sync) and restarts it if it dies.

Install once on the Pi (adjust `User=` and the paths in the file if your user or folder differ):

```bash
cd ~/rasby-project && git pull
sudo cp epaper-7in5.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now epaper-7in5
```

Daily use:

```bash
systemctl status epaper-7in5           # running?
journalctl -u epaper-7in5 -f           # live log (Ctrl+C only stops the log, not the service)
sudo systemctl restart epaper-7in5     # after `git pull` or editing the script
sudo systemctl stop epaper-7in5        # stop it (panel is cleared); needed before running the script by hand
sudo systemctl disable epaper-7in5     # no start at boot
```

When the service stops (stop, restart, shutdown or reboot) the script clears the panel to white. Set `CLEAR_ON_EXIT = False` at the top of the script to keep the last image on the panel instead.

Do not run a second copy by hand or the 2.9" clock while the service runs: they need the same pins (`GPIOPinInUse`).

## Pi setup (already done, for reference)

```bash
sudo raspi-config nonint do_spi 0
sudo apt update
sudo apt install -y python3-pil python3-spidev python3-gpiozero python3-lgpio fonts-dejavu-core git
git clone --depth 1 https://github.com/waveshare/e-Paper.git ~/e-Paper
git clone git@github.com:matze0054/rasby-project.git ~/rasby-project
cp -r ~/e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd ~/rasby-project/
```

## Workflow

- Edit on the Mac, then `git push`.
- On the Pi: `cd ~/rasby-project && git pull`.
- Set `LATITUDE` and `LONGITUDE` in `epaper_clock.py` (currently Berlin).
- Connect to the Pi with a remote shell at https://connect.raspberrypi.com, or `ssh mkern@rasbyprojectmk.local`.

## Useful debug commands

```bash
ls /dev/spidev0.*                      # SPI enabled
pinctrl get 8,10,11,17,24,25           # GPIO10/11 should show a0 (SPI) while the script runs
cd ~/e-Paper/RaspberryPi_JetsonNano/python/examples && python3 epd_2in9_V2_test.py   # Waveshare demo
```
