***English** · [Español](README.es.md)*

# Ulanzi D200X plugin for OpenDeck

A **device plugin** for [OpenDeck](https://github.com/nekename/OpenDeck): it makes the
Ulanzi D200X show up as a normal deck inside OpenDeck, so any OpenDeck action
(from any plugin) can be dropped onto its keys, side buttons and dials.

This is not a stand-alone controller — it replaces the role of `ulanzi_manager`'s
daemon while OpenDeck is running. Run one or the other, not both.

Runs on **Linux and Windows**. Windows support is a fork of
[edubox/opendeck-ulanzi-d200x](https://github.com/edubox/opendeck-ulanzi-d200x);
it has also been tested with the plain **D200**, which uses the same USB IDs and
protocol (it just has no dials or side buttons, so those slots never fire).

## What it exposes

| Hardware | OpenDeck slot | Notes |
|---|---|---|
| 12 square screens (rows 1–2 and the first three of row 3) | Keypad 0–12 | 196×196 icons |
| the double-width screen (bottom right) | Keypad 13 | see below |
| — | Keypad 14 | unused: it is the right half of key 13 |
| the 2 small side buttons | Touchpoint 1 & 2 (Keypad 15/16) | buttons only, no display |
| the 3 rotary encoders | Encoder 0–2 | turn + press |

That is 14 screens in total, which is why the grid is declared as 5×3 with one
dead cell — OpenDeck can only describe rectangular grids, so the merged screen
occupies slot 13 and slot 14 is left empty on purpose.

### The double-width screen (slot 13)

What this screen shows is configurable. Drop the plugin's own **Wide screen**
action on it and its property inspector offers:

| Mode | What the screen shows |
|---|---|
| **Clock** (default) | the clock built into the device |
| **System monitor** | the firmware's CPU / RAM / GPU gauges |
| **Off** | black |

The setting is global rather than per-key: it applies to the wide screen whether
or not the action is sitting on it, so it also decides what an **empty** slot 13
shows.

Drop any **other** action there instead and the screen switches to image mode
and renders that action's icon, letterboxed so it is not stretched.

Either way the screen stays pressable and fires `Keypad 13`.

The device does not measure the host: the firmware draws whatever percentages
the last status update carried. The plugin samples `/proc/stat` and
`/proc/meminfo` for CPU and RAM, and `gpu_busy_percent` (amdgpu) or `nvidia-smi`
for the GPU — with neither available the GPU gauge stays at zero.

## Cosmetic limitations

Two things about the on-screen layout cannot be fixed from here, because a
device plugin can only declare `rows`, `columns`, `encoders`, `touchpoints`,
`infobars` and `type` — everything else is hardcoded in OpenDeck's frontend
(`src/components/DeviceView.svelte`):

* The two side buttons render full size in a row of their own, rather than at
  half size centred alongside the dials.
* The double-width screen shows as slot 13 plus an empty slot 14, rather than as
  one key spanning both cells and the gap between them.

Both are pure layout. `Key.svelte` already supports rectangular canvases and
scaling (it uses them for the Stream Deck Neo's infobar), so changing this would
mean patching and rebuilding OpenDeck, or an upstream feature request.

## Requirements

Python 3 with three packages:

```sh
# Arch / CachyOS
sudo pacman -S python-hidapi python-pillow python-websockets
# Debian / Ubuntu
sudo apt install python3-hid python3-pil python3-websockets
```

If you run OpenDeck as a Flatpak, install them **on the host**, not inside the
sandbox: the plugin re-launches itself on the host with `flatpak-spawn --host`,
because neither `/dev/hidraw*` nor `hidapi` is reachable from inside the sandbox.

## Device permissions (udev) — required

By default `/dev/hidraw*` is readable only by root, so **the plugin cannot see
the D200X until a udev rule grants access**. This is the single most common
reason for "the device does not show up in OpenDeck".

OpenDeck installs a `40-streamdeck.rules` of its own, but it does *not* help
here: it only covers Elgato's vendor ID (`0fd9`), not Ulanzi's (`2207`).

```sh
sudo cp 60-ulanzi-d200x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

The rule is a single line, matching the form OpenDeck ships for its own devices:

```
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2207", ATTRS{idProduct}=="0019", MODE="0660", TAG+="uaccess"
```

No `SUBSYSTEM=="usb"` rule is needed — `python-hidapi` uses the hidraw backend
(`libhidapi-hidraw.so`), so only the hidraw node is ever opened. Add one only if
you have deliberately built hidapi against libusb.

udev rules are applied when a device event fires, so **if the D200X was already
plugged in, unplug and replug it** (or reboot).

### Verifying

```sh
$ ls -l $(python3 -c "import hid;print(' '.join(d['path'].decode() for d in hid.enumerate(0x2207,0x0019)))")
crw-rw----+ 1 root root 243, 5 ... /dev/hidraw5
crw-rw----+ 1 root root 243, 6 ... /dev/hidraw6
```

The device exposes **two** hidraw interfaces and the rule matches both; the
plugin uses the first one. What matters is the trailing `+`: that is the
`uaccess` ACL giving your session read/write access. Confirm it with
`getfacl /dev/hidraw5` — you should see `user:<you>:rw-`.

`install.sh` performs this check for you and tells you if the node is not
writable.

If your system does not use systemd-logind, `uaccess` does nothing. Add
`GROUP="input"` to the rule and make sure you are in that group.

### Why not `MODE="0666"`

Plenty of guides use `MODE="0666"`, which works but makes the device
world-readable and world-writable — any local process can then read your key
presses and drive the screens. `TAG+="uaccess"` grants access only to the user
logged in at the local seat, which is both safer and the modern convention.

## Install

```sh
sudo cp 60-ulanzi-d200x.rules /etc/udev/rules.d/   # see above; do this first
sudo udevadm control --reload-rules && sudo udevadm trigger

./install.sh          # copy into OpenDeck's plugins directory
./install.sh --link   # symlink instead, for development
./install.sh --uninstall
```

Then restart OpenDeck.

## Windows

No udev rule or driver is needed: Windows lets any user open the deck. The
plugin ships as a self-contained `d200x_plugin.exe`, built with PyInstaller, so
OpenDeck does not depend on a Python install at runtime.

Building needs Python 3.10 or newer (python.org, `winget install Python.Python.3.13`,
or scoop). From the repository:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1             # build into .venv and install
powershell -ExecutionPolicy Bypass -File .\install.ps1 -SkipBuild  # reinstall the last build
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall
```

The plugin goes to `%APPDATA%\opendeck\plugins\com.ulanzi.d200x.sdPlugin`; then
restart OpenDeck. **Quit Ulanzi Studio** (`UlanziDeck.exe`) and stop it from
starting with Windows, since it drives the same device. The installer warns if
it is running.

The plugin log is `%LOCALAPPDATA%\opendeck\logs\plugins\com.ulanzi.d200x.sdPlugin.log`.

Differences from Linux:

* The device has no report IDs, so on Windows every output report is sent with
  a leading `0x00` byte (hidapi would otherwise take the `0x7c` header as the
  ID). Interface 0 is opened explicitly, since interface 1 is a boot keyboard that
  Windows keeps locked.
* CPU and RAM for the stats screen come from `psutil`. GPU load comes only from
  `nvidia-smi`, so on AMD or Intel graphics the GPU gauge stays at 0.

## How it works

OpenDeck renders each key to a JPEG data URL and pushes it with `setImage`. The
D200X does not accept per-key images: the firmware only takes a **ZIP bundle**
containing `manifest.json` plus every icon, written over raw HID in 1024-byte
packets. So the plugin:

1. Decodes each `setImage`, scales it to 196×196 (392×196 squeezed for the wide
   screen) and caches it.
2. Coalesces bursts of updates (`FLUSH_DEBOUNCE`) and rate-limits bundles
   (`MIN_BUNDLE_INTERVAL`) so the firmware is not flooded.
3. Rebuilds the bundle, padding `dummy.txt` until no `0x00`/`0x7c` byte lands on
   a packet boundary — a firmware parsing bug the original daemon hits too.

A page full of live keys (a clock, a system monitor) means a bundle every few
seconds, and anything the firmware repaints in that moment flickers. So when the
firmware is the one drawing the wide screen — clock or system monitor — that
cell gets no manifest entry at all, and the mode is only restated when it
actually changes. Re-sending it on a timer makes the firmware repaint the clock,
which reads as a blink.

The device keeps time by itself, so seeding the clock once when it connects is
enough. Only the system monitor needs feeding, every two seconds.

Input reports are decoded on the same HID thread and forwarded as `keyDown` /
`keyUp` / `encoderChange` / `encoderDown` / `encoderUp`.

### Reconnect handling

While the D200X digests a large bundle it briefly resets its USB interface,
which is indistinguishable from an unplug. The HID worker therefore reopens the
handle silently and only reports a disconnect to OpenDeck after the device has
been missing for 30 seconds. On reacquire it re-sends its cached bundle rather
than asking OpenDeck to re-render — requesting a rerender on every reset is what
turned this into an infinite loop in an earlier attempt.

## Troubleshooting

**The device does not appear in OpenDeck.** In order of likelihood:

1. **Missing udev rule** — see [Device permissions](#device-permissions-udev--required).
   Remember to replug the device afterwards. This is by far the usual cause.
2. **Missing Python packages.** `install.sh` checks for these and names them.
3. **Plugin installed in the wrong directory.** A native OpenDeck reads
   `~/.config/opendeck/plugins/`, the Flatpak reads
   `~/.var/app/me.amankhanna.opendeck/config/opendeck/plugins/`. `install.sh`
   picks the one belonging to the OpenDeck that is running.

**The device appears but the screens stay blank.** Check the log for
`Pushed icon bundle`. If that line never appears, OpenDeck is not sending
images; if it appears but the screens do not change, something else is talking
to the device — make sure `ulanzi_manager`'s daemon is not running.

**Only one process may drive the device.** If you have also installed another
D200-family device plugin (for example `com.glmagalhaes.ulanzi.d200.sdPlugin`),
disable one of them: they open the same hidraw node and overwrite each other's
screens. `install.sh` warns you if it finds one.

## Debugging

The plugin logs to stderr, which OpenDeck captures. The path depends on how
OpenDeck was installed:

```sh
# native package (opendeck-bin and friends)
tail -f ~/.local/share/opendeck/logs/plugins/com.ulanzi.d200x.sdPlugin.log
# Flatpak
tail -f ~/.var/app/me.amankhanna.opendeck/data/opendeck/logs/plugins/com.ulanzi.d200x.sdPlugin.log
```

Set `D200X_DEBUG=1` in the environment for verbose output.

## Protocol notes

| Command | Value | Purpose |
|---|---|---|
| `SET_BUTTONS` | `0x0001` | icon/manifest ZIP bundle |
| `SET_SMALL_WINDOW` | `0x0006` | wide screen mode: `0` stats, `1` clock, `2` image |
| `SET_BRIGHTNESS` | `0x000a` | 0–100 |
| `SET_LABEL_STYLE` | `0x000b` | disabled here — OpenDeck bakes titles into the image |
| `IN_BUTTON` | `0x0101` / `0x0102` | key and dial input |

Hardware indices: screens `0–13`, side buttons `15`/`16`, dials `17`/`18`/`19`
(dial event byte: `0` release, `1` press, `2` turn left, `3` turn right).
