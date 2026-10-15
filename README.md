***English** · [Español](README.es.md)*

# Ulanzi D200X / D200H plugin for OpenDeck

Use a **Ulanzi D200X** or **D200H** stream controller with
[OpenDeck](https://github.com/nekename/OpenDeck), the free, open-source Stream
Deck software, on **Windows** or **Linux**.

This is a *device plugin*: it makes the Ulanzi deck show up in OpenDeck like any
Stream Deck, so you can drop any OpenDeck action, from any plugin, onto its keys,
dials and side buttons. You don't need Ulanzi Studio.

> This is a fork of [edubox/opendeck-ulanzi-d200x](https://github.com/edubox/opendeck-ulanzi-d200x),
> which supports the D200X on Linux. This fork adds **Windows** support and the
> **D200H**. Thanks to the original author for reverse-engineering the protocol.
> Since 1.3.0 it has its own plugin ID, `dev.kastro5.ulanzi-d200`.

## Contents

- [Supported hardware](#supported-hardware)
- [Install on Windows](#install-on-windows)
- [Install on Linux](#install-on-linux)
- [Choosing the model](#choosing-the-model)
- [Using the deck in OpenDeck](#using-the-deck-in-opendeck)
- [Known limitations](#known-limitations)
- [Troubleshooting](#troubleshooting)
- [How it works](#how-it-works)
- [Credits and license](#credits-and-license)

## Supported hardware

| Model | Screens | Dials | Side buttons | Status |
|---|---|---|---|---|
| **D200X** | 13 keys + 1 wide screen | 3 (turn + press) | 2 | supported (upstream, Linux) |
| **D200H** (deck dock) | 13 keys + 1 wide screen | — | — | supported, tested on Windows 11 |

Both models use the same USB ID (`2207:0019`) and the same protocol. They can't
be told apart over USB, so you tell the plugin which one you have (see
[Choosing the model](#choosing-the-model)).

| OS | Status |
|---|---|
| Windows 10 / 11 | supported (this fork) |
| Linux (native or Flatpak OpenDeck) | supported (upstream) |
| macOS | untested |

## Install on Windows

### Quick install (download)

No Python needed.

1. **Quit Ulanzi Studio** (`UlanziDeck.exe`, in the system tray) and turn off its
   autostart. It drives the same device and would fight OpenDeck over it.
2. Install [OpenDeck](https://github.com/nekename/OpenDeck/releases) and start
   it once.
3. From the [latest release](https://github.com/kastro5/opendeck-ulanzi-d200/releases/latest),
   download the zip for your model: `opendeck-ulanzi-d200h-…zip` or
   `opendeck-ulanzi-d200x-…zip`.
4. Extract it into `%APPDATA%\opendeck\plugins\` (paste that path into the
   Explorer address bar). You should end up with
   `%APPDATA%\opendeck\plugins\dev.kastro5.ulanzi-d200.sdPlugin\d200x_plugin.exe`.
5. Quit OpenDeck from the tray and start it again.

**Upgrading from a version before 1.3.0?** The plugin's folder changed from
`com.ulanzi.d200x.sdPlugin` to `dev.kastro5.ulanzi-d200.sdPlugin`. Delete the old
folder (or remove the old plugin in OpenDeck's Plugins tab), because both would
claim the deck. Your model and wide screen settings carry over by themselves, and
your keys stay as they are.

If Windows SmartScreen or your antivirus flags `d200x_plugin.exe`, that's because
it's an unsigned PyInstaller build. If you'd rather not trust a downloaded exe,
build it yourself as described below.

### Build from source

#### 1. Prerequisites

- **OpenDeck** for Windows ([releases](https://github.com/nekename/OpenDeck/releases)).
  Start it once so it creates its config folder.
- **Python 3.10 or newer**, used only to *build* the plugin. Get it from
  [python.org](https://www.python.org/downloads/) or run
  `winget install Python.Python.3.13`. The built plugin is a standalone `.exe`,
  so OpenDeck doesn't need Python at runtime.
- **Quit Ulanzi Studio** (`UlanziDeck.exe`, in the system tray) and turn off its
  autostart. It drives the same device and would fight OpenDeck over it.

No driver is needed. Windows lets any user open the deck.

#### 2. Build and install

Clone or download this repository, open PowerShell in its folder, and run:

```powershell
# D200H owners:
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Model d200h

# D200X owners:
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Model d200x
```

The script:

1. Creates a private Python environment in `.venv` and installs `hidapi`,
   `pillow`, `websockets`, `psutil` and `pyinstaller` into it. Your system Python
   is left alone.
2. Builds `dist\d200x_plugin.exe`.
3. Copies the plugin to `%APPDATA%\opendeck\plugins\dev.kastro5.ulanzi-d200.sdPlugin`.
4. Warns you if Ulanzi Studio or another D200 plugin is running.

#### 3. Restart OpenDeck

Quit OpenDeck from the tray icon and start it again. The deck appears in the
device selector at the top left, as **Ulanzi D200H** or **Ulanzi D200X**.

#### Other installer options

```powershell
.\install.ps1 -SkipBuild    # reinstall the last build without rebuilding
.\install.ps1 -Uninstall    # remove the plugin from OpenDeck
```

`-Model` is remembered, so later reinstalls keep it unless you pass it again.

## Install on Linux

Python 3 with three packages:

```sh
# Arch / CachyOS
sudo pacman -S python-hidapi python-pillow python-websockets
# Debian / Ubuntu
sudo apt install python3-hid python3-pil python3-websockets
```

If OpenDeck runs as a Flatpak, install these **on the host**. The plugin
re-launches itself there with `flatpak-spawn --host`.

**A udev rule is required.** By default `/dev/hidraw*` is root-only, so the
plugin can't see the deck until the rule grants access:

```sh
sudo cp 60-ulanzi-d200x.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
# then unplug and replug the deck

./install.sh             # copy into OpenDeck's plugins directory
./install.sh --link      # symlink instead, for development
./install.sh --uninstall
```

Then restart OpenDeck. Instead of `install.sh` you can also extract the zip for
your model from the [latest release](https://github.com/kastro5/opendeck-ulanzi-d200/releases/latest)
into `~/.config/opendeck/plugins/`; it contains the Linux launcher too.

The rule uses `TAG+="uaccess"`, which gives the logged-in user access, rather
than the world-writable `MODE="0666"` many guides suggest. Without
systemd-logind, add `GROUP="input"` to the rule and join that group.
`install.sh` checks that the device node is writable and tells you if it isn't.

On Linux, choose the model from OpenDeck, as described below.

## Choosing the model

The plugin needs to know whether it's driving a D200X (dials and side buttons)
or a D200H (keys only). There are two ways to set it:

- **At install time (Windows):** `install.ps1 -Model d200h` or `-Model d200x`.
  This writes `defaults.json` next to the plugin. Without it, the plugin
  assumes D200X.
- **From inside OpenDeck:**
  1. Find **Wide screen** under the *Ulanzi D200* category in the action list on
     the right.
  2. **Drag** it onto a key. Clicking it in the list does nothing.
  3. Click that key in the grid. Its settings appear below the grid.
  4. Choose the model under **Model**.
  5. **Restart OpenDeck.** The plugin switches immediately, but OpenDeck's
     editor stays on the old device and shows an empty grid until it restarts.

A model chosen in OpenDeck overrides the installer's. Each model is its own
device in OpenDeck (`ulanzi-d200x` / `ulanzi-d200h`) with its own profiles, so
switching doesn't carry your key setup across.

## Using the deck in OpenDeck

The deck appears as a 5 × 3 grid:

```
┌────┬────┬────┬────┬────┐
│  0 │  1 │  2 │  3 │  4 │
├────┼────┼────┼────┼────┤
│  5 │  6 │  7 │  8 │  9 │
├────┼────┼────┼────┴────┤
│ 10 │ 11 │ 12 │13 (wide)│   ← slot 14 is the right half of 13 and does nothing
└────┴────┴────┴─────────┘
  D200X only:  ◯ dial 1   ◯ dial 2   ◯ dial 3     ▭ side 1   ▭ side 2
```

| On the deck | In OpenDeck | Notes |
|---|---|---|
| 13 square screens | keys 0–12 | icons scaled to the 196×196 screen |
| the wide screen (bottom right) | **key 13** | put its action here, not on 14 |
| — | key 14 | unused, the right half of the wide screen |
| 3 dials (D200X) | encoders 1–3 | turn and press |
| 2 side buttons (D200X) | touchpoints 1–2 | buttons only, no display |

### The wide screen

By default the wide screen shows the deck's own **clock**. To change it, drag the
**Wide screen** action onto it, click it, and pick a mode:

| Mode | What the screen shows |
|---|---|
| **Clock** (default) | the clock built into the device |
| **System monitor** | CPU, RAM and GPU gauges, fed by the plugin every 2 s |
| **Off** | black |

The setting is global: it applies even when the action isn't on the wide screen.
If you put any **other** action on key 13, the wide screen shows that action's
icon instead, letterboxed so it isn't stretched. Either way, pressing the wide
screen fires key 13.

The system monitor gets CPU and RAM from the OS. GPU load comes from
`nvidia-smi` on NVIDIA cards, or from `gpu_busy_percent` on Linux AMD cards. On
other GPUs the gauge reads 0.

### Brightness

OpenDeck's brightness setting and the **Device Brightness** action are passed straight to the deck.

## Known limitations

- **The wide screen can't be one big key in OpenDeck's editor.** OpenDeck draws
  every device as a uniform grid of square keys, and a plugin can't merge cells.
  So the wide screen is key 13, with an empty key 14 beside it. On the deck it's
  one screen. Fixing this needs a change in OpenDeck itself.
  [OpenDeck PR #359](https://github.com/nekename/OpenDeck/pull/359) proposes
  letting plugins describe their exact layout, and this plugin already sends
  one: key 13 as a single double-width key, with the side buttons at half
  height. Stock OpenDeck ignores it. A build with #359 should draw the deck
  correctly with no plugin update.
- **D200X side buttons get their own row** in the editor, at full size, rather
  than sitting beside the dials. This is the same OpenDeck layout limitation.
- **Icons are re-sent as one bundle.** The firmware can't update a single key, so
  every change re-sends all icons (see [How it works](#how-it-works)). A page with
  many fast-changing keys updates at most every 1.5 s.
- **Only one program can drive the deck.** Close Ulanzi Studio, and don't install
  a second D200 plugin such as `com.glmagalhaes.ulanzi.d200.sdPlugin`.

## Troubleshooting

**The deck doesn't appear in OpenDeck**

- *Windows:* make sure Ulanzi Studio is fully closed (check the tray), then
  restart OpenDeck. Check the plugin log (below) for `Deck connected`.
- *Linux:* this is almost always the udev rule. Install it, then unplug and
  replug the deck.
- Make sure the plugin is in OpenDeck's plugins folder (`%APPDATA%\opendeck\plugins`
  on Windows, `~/.config/opendeck/plugins` on Linux) and that OpenDeck was
  restarted after installing.

**The grid is empty after changing the model.** Restart OpenDeck. Its editor
doesn't follow a device that is swapped while it is running.

**Wrong layout (dials shown on a D200H, or none on a D200X).** Set the model:
see [Choosing the model](#choosing-the-model).

**The screens don't change.** Look for `Pushed icon bundle` in the log. If it's
there but the deck doesn't update, another program is talking to the deck.

**The GPU gauge is stuck at 0.** Your GPU isn't NVIDIA (or Linux AMD). See
[The wide screen](#the-wide-screen).

### Logs

| Platform | Plugin log |
|---|---|
| Windows | `%LOCALAPPDATA%\opendeck\logs\plugins\dev.kastro5.ulanzi-d200.sdPlugin.log` |
| Linux (native) | `~/.local/share/opendeck/logs/plugins/dev.kastro5.ulanzi-d200.sdPlugin.log` |
| Linux (Flatpak) | `~/.var/app/me.amankhanna.opendeck/data/opendeck/logs/plugins/dev.kastro5.ulanzi-d200.sdPlugin.log` |

Set the environment variable `D200X_DEBUG=1` before starting OpenDeck for verbose
logs.

## How it works

The whole plugin is one Python file,
[`d200x_plugin.py`](dev.kastro5.ulanzi-d200.sdPlugin/d200x_plugin.py). OpenDeck starts
it and talks to it over a websocket using the Stream Deck plugin protocol. The
plugin talks to the deck over raw USB HID.

**Images.** OpenDeck renders each key as a JPEG and sends it with `setImage`.
The deck's firmware doesn't accept per-key images. It only takes a **ZIP
bundle** containing a `manifest.json` and every icon, sent in 1024-byte packets.
So the plugin:

1. scales each image to 196×196 and caches it;
2. waits for bursts of updates to settle (0.35 s) and sends at most one bundle
   every 1.5 s;
3. pads the ZIP until no `0x00` or `0x7c` byte lands on a packet boundary, which
   works around a firmware parsing bug.

While the firmware draws the wide screen itself (clock or system monitor), that
cell is left out of the bundle, so it doesn't flicker on every update.

**Input.** Key presses, dial turns and dial presses arrive as HID input reports.
The HID thread waits for them with a blocking read that times out every 100 ms,
so an idle deck uses next to no CPU. They're forwarded to OpenDeck as `keyDown`/`keyUp` and
`encoderChange`/`encoderDown`/`encoderUp`.

**Keep-alive.** The firmware falls back to its boot logo if the host is silent
for less than a minute. Whenever nothing has been written for 5 s, the plugin
re-sends the current brightness, which keeps the deck awake without redrawing
anything.

**Reconnects.** The deck briefly resets its USB connection while it unpacks a
large bundle. The plugin reopens the device quietly and only tells OpenDeck the
deck is gone after 30 s of absence. On reconnect it re-sends its cached icons.

### What the Windows port changed

- **Report ID byte.** The deck's HID descriptor has no report IDs and 1024-byte
  reports. Linux (hidraw) writes the 1024 bytes as-is. Windows requires a leading
  report-ID byte, so every write is sent as `0x00` + 1024 bytes. Without it,
  hidapi takes the `0x7c` header as the ID and the payload shifts by one byte.
  Reads need no change, because Windows strips the ID.
- **Interface choice.** The deck has two HID interfaces: interface 0 is the
  vendor channel, and interface 1 is a boot keyboard that Windows locks. The
  plugin opens interface 0 explicitly.
- **System stats.** `/proc` doesn't exist on Windows, so CPU and RAM come from
  `psutil`.
- **Packaging.** OpenDeck on Windows launches a plugin's `CodePathWin` directly,
  so the plugin is shipped as a console `.exe` built with PyInstaller. Its stderr
  goes to OpenDeck's plugin log.

### Protocol reference

Every packet is 1024 bytes: header `7c 7c`, a 2-byte big-endian command, a
4-byte little-endian payload length, then the payload.

| Command | Value | Purpose |
|---|---|---|
| `SET_BUTTONS` | `0x0001` | icon + manifest ZIP bundle |
| `SET_SMALL_WINDOW` | `0x0006` | wide screen: `mode\|cpu\|ram\|HH:MM:SS\|gpu`; mode `0` stats, `1` clock, `2` image |
| `SET_BRIGHTNESS` | `0x000a` | `0`–`100`, as ASCII |
| `SET_LABEL_STYLE` | `0x000b` | label font and colour (titles are hidden; OpenDeck draws them into the image) |
| `IN_BUTTON` | `0x0101` / `0x0102` | input from the deck |

Input hardware indices: screens `0`–`13`, side buttons `15`/`16`, dials
`17`/`18`/`19`. Dial event byte: `0` release, `1` press, `2` turn left,
`3` turn right.

## Repository layout

| Path | What it is |
|---|---|
| `dev.kastro5.ulanzi-d200.sdPlugin/` | the plugin: `d200x_plugin.py`, `manifest.json`, icons, settings panel |
| `install.ps1` | Windows build + install script |
| `requirements-build.txt` | pinned build dependencies, shared by `install.ps1` and CI |
| `scripts/package_release.py` | packages the exe into the per-model release zips |
| `.github/workflows/release.yml` | builds and publishes releases |
| `install.sh` | Linux install script |
| `60-ulanzi-d200x.rules` | Linux udev rule |
| `CHANGELOG.md` | release notes |

## Making a release

Releases are built by GitHub Actions, not on a developer's PC:

1. Bump `Version` in `dev.kastro5.ulanzi-d200.sdPlugin/manifest.json`, and add a
   `## <version>` entry to `CHANGELOG.md` (and `CHANGELOG.es.md`). The English
   entry becomes the release notes.
2. Commit, then tag and push:
   `git tag -a v1.2.3 -m "v1.2.3" && git push origin main v1.2.3`

The [Release workflow](.github/workflows/release.yml) builds the exe on
Windows, checks that it starts, packages both zips, and publishes the release.
It refuses a tag that doesn't match the manifest version. To test a build
without publishing, run the workflow by hand from the Actions tab and download
the zips from its artifacts.

## Credits and license

- Original plugin and protocol work:
  [edubox/opendeck-ulanzi-d200x](https://github.com/edubox/opendeck-ulanzi-d200x).
- Windows port and D200H support: this fork.
- [OpenDeck](https://github.com/nekename/OpenDeck) by nekename.

Licensed under the **GNU GPL v3.0**, the same as the original. See
[LICENSE](LICENSE). Not affiliated with Ulanzi.
