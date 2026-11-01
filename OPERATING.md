# Operating guide: turning the Pi and the 7.5" dashboard on and off

The dashboard runs as a systemd service called `epaper-7in5`. It starts by itself at boot, keeps running without any terminal or Raspberry Pi Connect session, and restarts if it crashes. Setup is described in [README.md](README.md#run-at-boot-systemd).

Commands below are typed in a shell on the Pi (Raspberry Pi Connect remote shell, or `ssh mkern@rasbyprojectmk.local`). Closing the shell or losing the connection does **not** affect the dashboard.

## Quick reference

| I want to | Do this |
|---|---|
| Switch everything on | Plug in the power supply |
| Switch everything off | `sudo shutdown -h now`, wait until the green LED stops blinking, then unplug |
| Switch off with the iPhone | Tap the "Pi off" shortcut, wait for the white screen plus 30 s, flip the strip ([setup](#switching-off-with-the-iphone-and-a-switched-power-strip)) |
| Restart the Pi | `sudo reboot` |
| Stop only the dashboard | `sudo systemctl stop epaper-7in5` |
| Start the dashboard again | `sudo systemctl start epaper-7in5` |
| Apply an update | `cd ~/rasby-project && git pull && sudo systemctl restart epaper-7in5` |
| Check if it runs | `systemctl status epaper-7in5` |
| Watch the log | `journalctl -u epaper-7in5 -f` (Ctrl+C stops the log only) |

## Turning everything on

1. Plug in the power supply of the Pi (the HAT with the display is already stacked on it).
2. Wait. The Pi boots, waits for Wi-Fi and the clock sync (the Pi has no battery-backed clock), then starts the dashboard. The first picture appears after about one to two minutes. The panel flashes a few times during the first refresh; that is normal.
3. From then on the display updates every minute (partial refresh), and every 15 minutes with a full, flashing refresh that removes ghosting.

Nothing has to be typed. If nothing appears after five minutes, see [Troubleshooting](#troubleshooting).

## Turning everything off (Pi and display)

Always shut the Pi down properly. Pulling the plug while it runs can corrupt the SD card, and the panel would keep showing the last picture.

1. Open a shell on the Pi and run:

   ```bash
   sudo shutdown -h now
   ```

2. The service stops, the panel is cleared to white (takes a few seconds), and the Pi halts. Raspberry Pi Connect / SSH disconnects, which is expected.
3. Wait until the green activity LED stops blinking (about 10 to 20 seconds), then unplug the power supply.

If you cannot open a shell (no Wi-Fi, no Connect), a hard power cut is the last resort. It risks SD-card corruption, so avoid it when you can.

### Restart

```bash
sudo reboot
```

The dashboard comes back by itself.

## Switching off with the iPhone and a switched power strip

For a one-tap shutdown the iPhone logs in to the Pi over your home Wi-Fi (SSH, built into the Shortcuts app) and runs `shutdown`. It needs no internet service and no extra software on the Pi. It works only while the phone is on the same Wi-Fi as the Pi. Away from home, use Raspberry Pi Connect in Safari (https://connect.raspberrypi.com) and run `sudo shutdown -h now`.

A manual power strip cannot be switched by the phone. So the routine is:

1. Tap the **Pi off** shortcut.
2. The Pi shuts down after one minute and clears the display. When the screen is white, wait **about 30 more seconds** until the green LED has stopped.
3. Flip the strip off.

Switching the strip on again boots the Pi and the dashboard comes back by itself.

If you want the power cut without you being there, only a smart plug can do that (see [Smart plug instead of the strip](#smart-plug-instead-of-the-strip)).

The step-by-step setup (Pi, iPhone, SSH key, test and troubleshooting) is in [IPHONE_SHUTDOWN.md](IPHONE_SHUTDOWN.md). Do it once; afterwards it is one tap.

### Smart plug instead of the strip

A Wi-Fi smart plug (Shelly, Tasmota, Tapo/Kasa, FRITZ!DECT, Zigbee) can cut the power by itself. Use the same shortcut, and let the plug's own schedule or app switch off a few minutes after the shutdown. Never cut the power while the Pi is still running.

## Controlling only the dashboard (the Pi keeps running)

```bash
sudo systemctl stop epaper-7in5       # stop; the panel is cleared to white
sudo systemctl start epaper-7in5      # start again
sudo systemctl restart epaper-7in5    # stop and start, e.g. after changing the script
systemctl status epaper-7in5          # shows "active (running)" when it works
journalctl -u epaper-7in5 -n 50       # last 50 log lines
journalctl -u epaper-7in5 -f          # follow the log live
```

### Do not start at boot / start at boot again

```bash
sudo systemctl disable --now epaper-7in5   # stop now and no longer start at boot
sudo systemctl enable --now epaper-7in5    # start now and at every boot
```

### Updating the script

```bash
cd ~/rasby-project
git pull
sudo systemctl restart epaper-7in5
```

If you changed `epaper-7in5.service` itself, also run:

```bash
sudo cp epaper-7in5.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart epaper-7in5
```

## Running the script by hand (testing)

The service and a manually started script need the same GPIO pins, so only one can run. Stop the service first:

```bash
sudo systemctl stop epaper-7in5
cd ~/rasby-project
python3 epaper_clock_7in5.py --once    # one full refresh, then exit
python3 epaper_clock_7in5.py           # runs until Ctrl+C; stops when the terminal closes
python3 epaper_clock_7in5.py --clear   # only turn the panel white
sudo systemctl start epaper-7in5       # hand control back to the service
```

A manually started script dies when the terminal or connection closes. That is why the service is the normal way to run it.

The 2.9" clock (`epaper_clock.py`) uses the same pins as the HAT and cannot run while the HAT is connected.

## What the display does when stopped

- On stop, restart, shutdown and reboot the script clears the panel to white.
- To keep the last picture visible instead, set `CLEAR_ON_EXIT = False` near the top of `epaper_clock_7in5.py`, `git pull` on the Pi and restart the service. A static picture is held without power, but it then shows an old time until the next start.
- A Waveshare panel should not stay powered and unrefreshed for days. If you do not want the display during the night or while away, shut the Pi down or stop the service.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Nothing on the display after 5 minutes | `systemctl status epaper-7in5` and `journalctl -u epaper-7in5 -n 50`. Is the HAT seated on all 40 pins and the panel's flat cable inserted? |
| `GPIOPinInUse` in the log | Another copy of the script (or `epaper_clock.py`) is running. `sudo systemctl stop epaper-7in5`, close the other one, start the service again. |
| `FileNotFoundError: /dev/spidev0.0` | SPI is off: `sudo raspi-config nonint do_spi 0`, then `sudo reboot`. |
| Wrong time shown | The Pi has no battery-backed clock and needs Wi-Fi to sync. Check `timedatectl` (expect `System clock synchronized: yes`). |
| Weather, departures or Pokémon missing | No internet or the web service is down. The display retries every minute; check `ping -c 3 1.1.1.1`. |
| Ghost images, grey streaks | Wait for the next full refresh (at most 15 minutes) or `sudo systemctl restart epaper-7in5`. |
| Display stuck after a power loss | `sudo systemctl stop epaper-7in5`, run `python3 epaper_clock_7in5.py --clear`, then `sudo systemctl start epaper-7in5`. |
| Service keeps restarting | `journalctl -u epaper-7in5 -n 100` shows the error; it retries every 30 seconds. |
| Lost access to the Pi | Check that it is powered and on Wi-Fi, then try https://connect.raspberrypi.com or `ssh mkern@rasbyprojectmk.local`. |

## Good habits

- Always `sudo shutdown -h now` before unplugging.
- Wire or stack the HAT only with the Pi powered off and unplugged.
- Use a stable 5 V power supply (2.5 A or more) to avoid random reboots and SD-card corruption.
