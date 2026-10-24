# rasby-project

E-paper clock, date and weather display on a Raspberry Pi Zero 2 W with a Waveshare 2.9" e-paper module (V2, 296x128).

- Script: [epaper_clock.py](epaper_clock.py)
- Wiring diagram: [wiring.svg](wiring.svg)
- Repo: https://github.com/matze0054/rasby-project (private)

## Hardware

- Raspberry Pi Zero 2 W, 64 GB microSD, header pins fitted
- Waveshare 2.9" e-paper module, V2 (label: Rev2.1, FPC-7519 rev.b), supplied 8-wire cable
- Display BS pad is set to "0" (4-line SPI)

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

## Later

- Run the clock at boot with a systemd service.
