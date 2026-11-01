# One-tap shutdown from the iPhone (home Wi-Fi) with a switched power strip

Goal: tap a shortcut on the iPhone, the Pi shuts down cleanly one minute later, then you flip the switch on the power strip. No internet service is involved: the iPhone logs in to the Pi over your home Wi-Fi with SSH (built into the Shortcuts app) using a key that is only allowed to run two things: `shutdown` and `cancel`.

Works only while the iPhone and the Pi are on the same Wi-Fi. Away from home, use https://connect.raspberrypi.com in Safari and run `sudo shutdown -h now`.

Overview of what you do:

- Part A, on the Pi: check that SSH works and update the repo (5 minutes).
- Part B, on the iPhone: create the shortcut and its SSH key (5 minutes).
- Part C, on the Pi: allow only that key to shut down (5 minutes).
- Part D: test and daily use.

You need the Mac (or any computer) with the Raspberry Pi Connect terminal open on the Pi, and your iPhone on the home Wi-Fi.

---

## Part A: prepare the Pi

Open the remote shell: https://connect.raspberrypi.com, your device `rasbyprojectmk`, **Connect**, **Remote shell**. Then run:

```bash
cd ~/rasby-project && git pull
chmod +x pi_power.sh
systemctl is-active ssh          # expect: active
sudo -n /sbin/shutdown -c; echo "exit=$?"   # must NOT say "a password is required" (see below)
hostname -I                      # note the IP address, e.g. 192.168.1.42
```

- If `ssh` is not `active`: `sudo systemctl enable --now ssh`. (SSH was enabled in your setup, so this is normally fine.)
- If the `sudo -n` line says `sudo: a password is required`, the shutdown cannot run from the phone. Allow only the two shutdown commands without a password (asks for your password once):

  ```bash
  echo 'mkern ALL=(root) NOPASSWD: /sbin/shutdown -h +1, /sbin/shutdown -c' | sudo tee /etc/sudoers.d/pi-shutdown
  sudo chmod 440 /etc/sudoers.d/pi-shutdown
  sudo visudo -cf /etc/sudoers.d/pi-shutdown     # expect: parsed OK
  sudo -n /sbin/shutdown -c; echo "exit=$?"      # must not say "a password is required"
  ```

  This does not make `sudo` passwordless in general, only these two exact commands. The test command only cancels a pending shutdown and is harmless.
- Write down the IP address from `hostname -I`. It is the fallback if the name `rasbyprojectmk.local` does not work on the iPhone. In your router, give the Pi a fixed IP address ("DHCP reservation") so the address never changes.

---

## Part B: create the shortcut and the key on the iPhone

### B1. Allow Shortcuts to use the local network

On the iPhone: **Settings, Privacy & Security, Local Network**, switch **Shortcuts** on. (If the entry does not appear yet, it shows up after the first run of the shortcut and the prompt "Shortcuts would like to find and connect to devices on your local network", tap **Allow**.)

### B2. Create the shortcut "Pi off"

1. Open the **Shortcuts** app, tap **+** (top right) to create a new shortcut.
2. Tap the name at the top, **Rename**, enter `Pi off`.
3. Tap **Add Action**, search for `Run Script Over SSH` and tap it.
4. Tap the small arrow or **Show More** on the action so all fields are visible and fill in:

   | Field | Value |
   |---|---|
   | Script | `shutdown` |
   | Host | `rasbyprojectmk.local` (or the IP address from Part A) |
   | Port | `22` |
   | User | `mkern` |
   | Authentication | **SSH Key** |

   The Script must be exactly the single word `shutdown`, nothing else (the Pi only accepts `shutdown` and `cancel`).
5. Leave **Input** empty.

### B3. Create the SSH key and copy its public key

1. Still in the action, tap the **SSH Key** field (the key selector).
2. Choose **New SSH Key**, type **ed25519** (or RSA if ed25519 is not offered), and confirm.
3. Tap **Share Public Key** (also called "Copy Public Key", it may be in the same menu, or reached by tapping the key). The iOS share sheet opens.
4. Send the key to the computer you use for the Pi shell: **AirDrop** to your Mac, or **Messages/Mail to yourself**, or **Notes** if you use iCloud.
5. On the computer, open the text and **copy the whole line**. It looks like this (one single line, no line breaks):

   ```
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... some-comment
   ```

   Do not mix it up with the private key; Shortcuts never shows the private key.

### B4. Add a confirmation (recommended)

To avoid accidental shutdowns, put a confirmation in front of the SSH action:

1. Tap **+** below the action list, search for `Show Alert` and add it. Place it **above** the SSH action (drag the handle to reorder).
2. Title: `Shut down Pi?`, message: `The Pi shuts down in 1 minute.` If you cancel in the alert, the shortcut stops.
3. Optional: add `Show Notification` below the SSH action with the text `Pi shuts down in 1 minute. Flip the strip when the screen is white and the LED stopped.`

Tap **Done**.

### B5. Create the shortcut "Pi cancel"

Long-press the shortcut "Pi off" in the Shortcuts app, **Duplicate**, rename to `Pi cancel`, open it and change only the **Script** to `cancel`. (You can delete the Show Alert action here.) Tap **Done**.

### B6. Home Screen button (recommended)

Open "Pi off", tap the share/settings icon (**ⓘ** or the **Details** button), **Add to Home Screen**, choose a name and icon, **Add**. Now one tap on the home screen starts it.

---

## Part C: allow only that key on the Pi

Back in the Pi remote shell. You need the public key line from B3 (step 5).

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
```

In the editor, go to the end of the file (if the file already has lines, they are other keys, leave them alone), start a **new line** and paste:

```
restrict,command="/home/mkern/rasby-project/pi_power.sh" ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI... some-comment
```

That is: the text `restrict,command="/home/mkern/rasby-project/pi_power.sh"`, **one space**, then the public key line from the iPhone, all on one line. Save with `Ctrl+O`, `Enter`, exit with `Ctrl+X`. Then:

```bash
chmod 600 ~/.ssh/authorized_keys
cat ~/.ssh/authorized_keys     # check: one line per key, the iPhone key starts with restrict,command=...
```

What this does: whoever logs in with this key can only run `pi_power.sh`, which accepts `shutdown` (halt in 1 minute) and `cancel`, nothing else. It gives no shell, no file access and no port forwarding. If the repo is in a different folder than `/home/mkern/rasby-project`, adjust the path.

---

## Part D: test and use

### D1. Test (nothing shuts down)

1. On the Pi: `sudo shutdown -h +10` (schedules a shutdown in 10 minutes).
2. On the iPhone: run **Pi cancel**. On the first run allow the local-network prompt and, if asked, trust the host key of the Pi.
3. On the Pi: `shutdown --show` should print `No scheduled shutdown.`

If that works, **Pi off** works the same way.

### D2. Daily use: switching off

1. Tap **Pi off** and confirm. The Pi announces the shutdown for one minute later (changed your mind? run **Pi cancel** within that minute).
2. After about a minute the dashboard stops and the **display turns white**.
3. Wait **about 30 more seconds** until the green LED on the Pi stops blinking.
4. Flip the **switch on the power strip** off. Now the Pi has no power.

### D3. Daily use: switching on

Flip the strip on. The Pi boots and the dashboard shows up after one to two minutes, nothing else to do (see [OPERATING.md](OPERATING.md)).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shortcut says "could not resolve host" / times out | iPhone not on the home Wi-Fi (not mobile data, not a guest network), Pi powered off, or `rasbyprojectmk.local` not resolved: use the IP address from `hostname -I` as Host. |
| "Permission denied (publickey)" | The key line in `~/.ssh/authorized_keys` is wrong. It must be one line, with exactly one space between `command="..."` and `ssh-ed25519`, and no line break inside the key. Check `chmod 600 ~/.ssh/authorized_keys`, `chmod 700 ~/.ssh`. Log: `sudo journalctl -u ssh -n 20`. |
| The shortcut ran, but nothing happens on the Pi | Check the Script field: exactly `shutdown` or `cancel`. See the Pi log: `sudo journalctl -u ssh -n 20`. Test the script on the Pi: `SSH_ORIGINAL_COMMAND=cancel ~/rasby-project/pi_power.sh`. |
| "usage: shutdown \| cancel" shown | The Script field contains something else. Set it to exactly `shutdown` or `cancel`. |
| No Local Network entry for Shortcuts in Settings | Run the shortcut once and tap **Allow** in the prompt; it then appears. |
| Pi has a new IP address | Set a DHCP reservation in the router, then update Host in both shortcuts. |
| Host key warning | The Pi was re-installed or got a new SSH identity. Accept the new key in Shortcuts if you are sure it is your Pi. |
| No SSH key option in the action | Update iOS. As a fallback choose **Password** with your Pi password; then the restriction does not apply, so use the key whenever possible. |
| Pi does not shut down but the key works | `sudo -n /sbin/shutdown -c` must work without a password (Part A, sudoers rule). |

## Removing or replacing the phone's access

Delete the iPhone's line from `~/.ssh/authorized_keys` on the Pi (`nano ~/.ssh/authorized_keys`). The shortcut then no longer works. To replace the key, create a new one in Shortcuts (B3) and repeat Part C.
