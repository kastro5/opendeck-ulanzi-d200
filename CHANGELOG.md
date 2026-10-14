***English** · [Español](CHANGELOG.es.md)*

# Changelog

## 1.2.1 — 2026-10-14

### Fixed

- **The deck fell back to the Ulanzi boot logo after less than a minute idle.**
  The firmware treats a silent host as gone, and in clock mode the plugin sent
  nothing once the icons were pushed. The plugin now re-sends the current
  brightness whenever nothing has been written for 5 seconds. This keep-alive
  redraws nothing, unlike restating the clock mode, which blinks.

## 1.2.0 — 2026-10-14

### Added

- **Windows support.** `install.ps1` builds a self-contained
  `d200x_plugin.exe` and installs it into OpenDeck. On Windows, output reports
  get the leading report ID byte the HID stack requires, interface 0 is opened
  explicitly, and the stats screen reads CPU and RAM through `psutil`.
- **D200H support.** It shares the D200X's USB ID and protocol but has no dials
  or side buttons. Pick the model with `install.ps1 -Model d200h` or from the
  Wide screen action's settings. Each model registers as its own OpenDeck
  device, with its own profiles.

## 1.1.3 — 2026-08-05

### Fixed

- **The wide screen came up as a frozen system monitor.** With the clock
  selected, the device started on its own default screen — the gauges, stuck at
  zero — until the setting was changed and changed back. The black background
  1.1.2 lays down at connect is a bundle that names the wide cell, and painting
  that cell drops the firmware out of clock and stats mode; the mode was only
  ever sent when it *changed*, so nothing put it back, and the zeros were
  whatever that one command had carried. The mode is now restated behind any
  bundle that paints the cell.
- The wide screen mode now appears in the plugin log, which said nothing about
  it before.

## 1.1.2 — 2026-08-01

### Fixed

- **Occasional flicker of the whole device.** The firmware mis-parses a bundle
  when a `0x00` or `0x7c` byte lands on a 1024-byte packet boundary, so the
  bundle is rebuilt with different padding until the layout is clean — but it
  gave up after 31 tries and sent the malformed bundle anyway. A page with live
  keys bundles ~217 KiB, which puts ~216 bytes on a boundary and leaves barely
  8% of layouts clean, so roughly one push in thirteen went out malformed: with
  a bundle every three seconds, a visible glitch about once a minute. The
  search now runs up to 200 tries, which costs nothing in the common case
  (about twelve tries are needed) and makes giving up vanishingly unlikely.

## 1.1.1 — 2026-08-01

### Fixed

- **The wide screen kept whatever was behind the clock.** The firmware draws the
  clock and the gauges over that cell instead of clearing it first, and 1.1.0
  stopped naming the cell in the bundle in order to kill the flicker — so
  nothing was clearing it either. After the device had been unplugged from the
  mains its boot logo stayed visible behind the time; the icon of an action that
  used to sit on the key did the same. The plugin now lays down a black
  background the first time it takes the cell over, and goes back to leaving it
  alone afterwards, so the flicker does not come back.

## 1.1.0 — 2026-07-31

### Added

- **Configurable wide screen.** A new **Wide screen** action
  (`com.ulanzi.d200x.widescreen`) with a property inspector that chooses what the
  bottom-right double key shows: the device's built-in **clock** (default), a
  **system monitor**, or **off** (black). The choice is a plugin-wide setting, so
  it also governs the key while it is empty; dropping any other action there
  still shows that action's icon. The inspector is in English or Spanish
  depending on OpenDeck's language.
- **Real CPU / RAM / GPU figures** behind the system monitor, sampled from
  `/proc/stat`, `/proc/meminfo` and `gpu_busy_percent` (amdgpu) or `nvidia-smi`.
  The gauges previously received hardcoded zeroes, because the device measures
  nothing itself and only draws what it is sent.

### Fixed

- **Wide screen flicker.** Every cell named in a bundle's `manifest.json` is
  repainted when that bundle lands, so the clock was being overdrawn — and
  briefly showing what was underneath — on every push, which with live keys on
  the page meant every few seconds. The cell is now left out of the bundle
  entirely whenever the firmware is the one drawing it.
- **Clock blink.** The wide-screen mode was restated every two seconds, and each
  command made the firmware repaint. It is now sent only when the mode actually
  changes; the device keeps time on its own.

### Changed

- `install.sh` no longer copies `__pycache__` into the plugin directory.

## 1.0.0

Initial release: the D200X registers with OpenDeck as a 5×3 device — 14 screens
(the bottom-right pair is a single double-width screen), the two side buttons as
touchpoints and the three dials as encoders — with icons packed into the ZIP
bundle the firmware expects, USB reconnects absorbed silently, and a single udev
rule for hidraw access.
