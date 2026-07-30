***English** · [Español](CHANGELOG.es.md)*

# Changelog

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
