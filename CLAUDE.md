# CLAUDE.md

Working notes for this repository. Read this first — it is meant to make walking
the tree unnecessary for routine work.

## What this is

An **OpenDeck device plugin** for the Ulanzi D200X: it registers the hardware
with [OpenDeck](https://github.com/nekename/OpenDeck) so any OpenDeck action can
be dropped on its keys, side buttons and dials. It is not a standalone
controller.

The predecessor project — a standalone daemon plus PyQt GUI for the same device —
lives at `~/Proyectos/Ulanzi-Deck-Linux-edu`. Its `ulanzi_manager/device.py` is
the reference implementation of the wire protocol and is worth reading when a
protocol question comes up. Both drive the same USB device, so **only one may run
at a time**.

Remote: `git@github.com:edubox/opendeck-ulanzi-d200x.git`, branch `main`.

## Layout

```
├── README.md / README.es.md          kept 1:1, English + Spain Spanish
├── CHANGELOG.md / CHANGELOG.es.md    same pairing
├── CLAUDE.md                         project memory; AGENTS.md is a symlink to it so opencode loads the same source
├── install.sh                        copies into the running OpenDeck's plugin dir
├── 60-ulanzi-d200x.rules             single udev rule, uaccess
└── com.ulanzi.d200x.sdPlugin/
    ├── manifest.json                 DeviceNamespace "ul", one action
    ├── launch.sh                     flatpak-spawn --host if present, else python3
    ├── d200x_plugin.py               everything: HID, images, websocket, stats
    ├── propertyInspector/widescreen.html   the only settings UI (bilingual)
    └── assets/{icon,widescreen}.png
```

`d200x_plugin.py` is the whole plugin. Its sections, in order: device/protocol
constants → image helpers (`render_icon`, `build_bundle`) → `SystemStats` →
`HidWorker` (the only thread that touches the handle) → `D200XPlugin` (websocket,
event handling, flushing) → entry point.

## Slot map

OpenDeck can only describe rectangular grids, so the device is declared 5×3 with
one dead cell. The mapping to hardware indices is the identity:

| OpenDeck | Hardware | Notes |
|---|---|---|
| Keypad 0–12 | screens 0–12 | 196×196 icons |
| Keypad 13 | the double-width screen | see below |
| Keypad 14 | — | phantom: the right half of key 13, never addressed |
| Keypad 15/16 | side buttons | declared as the 2 touchpoints |
| Encoder 0/1/2 | dials 17/18/19 | turn + press |

`DEVICE_ID = "ulanzi-d200x"` and `manifest.json`'s `DeviceNamespace` must stay in
sync: OpenDeck looks the namespace up as `device_id[..2]`, and it must be exactly
two characters (`"ul"`).

## The wide screen (key 13)

One global setting, `{"wideMode": "clock" | "stats" | "off"}`, stored by OpenDeck
in `~/.config/opendeck/settings/com.ulanzi.d200x.sdPlugin.json` and edited from
the **Wide screen** action's property inspector (`com.ulanzi.d200x.widescreen`).
It applies whether or not that action is on key 13, so it also governs the empty
slot. Any *other* action there wins and its icon is rendered instead.

`clock` → firmware mode 1, `stats` → mode 0 fed real percentages, `off` → mode 2
with a black icon. The device measures nothing itself: the CPU/RAM/GPU gauges
draw whatever the last `SET_SMALL_WINDOW` carried, sampled from `/proc/stat`,
`/proc/meminfo` and `gpu_busy_percent`/`nvidia-smi`. It does keep its own time,
so the clock is seeded once and left alone.

## Hardware protocol

VID `0x2207`, PID `0x0019`, raw HID, 1024-byte packets: header `7c 7c`, command
big-endian at 2:4, length little-endian at 4:8, data from 8. The first packet of
a transfer carries 1016 data bytes, the rest are raw 1024-byte chunks.

| Command | Value | Purpose |
|---|---|---|
| `SET_BUTTONS` | `0x0001` | the ZIP bundle: `manifest.json` + icons, keys `"{col}_{row}"` |
| `SET_SMALL_WINDOW` | `0x0006` | `mode\|cpu\|mem\|HH:MM:SS\|gpu` |
| `SET_BRIGHTNESS` | `0x000a` | 0–100 |
| `SET_LABEL_STYLE` | `0x000b` | forced `ShowTitle: false` — OpenDeck bakes titles into the image |
| `IN_BUTTON` | `0x0101`/`0x0102` | input; dial byte: 0 release, 1 press, 2 left, 3 right |

The firmware cannot take per-key images — only the whole ZIP bundle — and it
mis-parses a bundle when a `0x00` or `0x7c` byte lands on a 1024-byte packet
boundary, hence the `dummy.txt` re-padding retry loop in `build_bundle`.

## Install / test loop

OpenDeck on this machine is the **native** package (`opendeck-bin`,
`/usr/bin/opendeck`), not the Flatpak. Do not assume otherwise.

```sh
./install.sh                                  # or --link for development
pkill -f '^/usr/bin/opendeck'; sleep 3
setsid nohup /usr/bin/opendeck --hide >/dev/null 2>&1 </dev/null &
tail -f ~/.local/share/opendeck/logs/plugins/com.ulanzi.d200x.sdPlugin.log
```

A restart of OpenDeck is required for manifest changes *and* for plugin code
changes (OpenDeck does not respawn a killed plugin).

| What | Where |
|---|---|
| plugin directory | `~/.config/opendeck/plugins/` |
| plugin log | `~/.local/share/opendeck/logs/plugins/<uuid>.log` |
| OpenDeck's own log | `~/.local/share/opendeck/logs/opendeck.log` (UTC) |
| global settings | `~/.config/opendeck/settings/<uuid>.json` |
| profile / placed actions | `~/.config/opendeck/profiles/ulanzi-d200x/Default.json` |
| property inspector webserver | `http://localhost:57118/<abs-path>\|opendeck_property_inspector` |

Python dependencies are **system packages**, not a venv:
`python-hidapi python-pillow python-websockets` (Arch names).

Protocol or event questions about OpenDeck are answered from its source, not
from memory:

```sh
curl -sL https://github.com/nekename/OpenDeck/archive/refs/tags/v2.13.1.tar.gz | tar xz
```

Useful entry points there: `src-tauri/src/shared.rs` (`DeviceInfo`, `Action`,
`ActionContext`), `src-tauri/src/events/inbound/` (what a plugin may send),
`src-tauri/src/plugins/manifest.rs` (manifest schema) and
`src/components/DeviceView.svelte` (the fixed layout).

## Device permissions

One udev rule, hidraw only:

```
KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idVendor}=="2207", ATTRS{idProduct}=="0019", MODE="0660", TAG+="uaccess"
```

`python-hidapi` links `libhidapi-hidraw.so`, so no `SUBSYSTEM=="usb"` rule is
needed. Rules apply on a device event: replug after installing. The docs assume a
clean system — no prior D200 tooling installed.

## Conventions

- Code and code comments in English; user-facing docs in both English and Spain
  Spanish, kept structurally identical (`README.md` ↔ `README.es.md`, same for
  the changelogs). Check internal anchors: GitHub turns " — " into `--`.
- Comments explain *why*, not what. Match the density already in the file.
- Verify before claiming: run it, paste the real output.
- Every user-visible change gets a `CHANGELOG.md` + `CHANGELOG.es.md` entry, and
  a `Version` bump in `manifest.json`.
- Do not commit or push unless asked.

## Gotchas already paid for

1. **The install is native, not Flatpak** — an entire session was lost to this.
2. **Only one D200 plugin may be enabled.** `com.glmagalhaes.ulanzi.d200.sdPlugin`
   claims the same hidraw node and re-registers the device as a plain 5×3 with no
   encoders; that is why dials and side buttons once "did not exist".
3. **`registerDevice` before the websocket is open is silently dropped** — start
   the HID worker only after `registerPlugin` has been sent.
4. **Never answer a firmware reset with `rerenderImages`.** The D200X resets its
   USB interface while digesting a bundle; treat it as a reconnect, replay the
   cached bundle, and only report a disconnect after 30 s of absence.
5. **Anything repainted while the firmware owns the wide screen flickers.** With
   live keys a bundle goes out every few seconds, so in clock/stats mode key 13
   gets no manifest entry (`build_bundle(..., omit=)`) and the mode command is
   sent only when the mode changes; the 2 s timer only feeds the gauges in stats
   mode. **But the cell still has to be blanked once** (`_wide_blanked`): the
   firmware draws over that cell without clearing it, so a cell nobody paints
   keeps showing whatever is behind — the boot logo after a power cut, or the
   icon of an action that used to be there. Once at connect, never on a push.
6. **A plugin's only settings UI is an action's property inspector.** OpenDeck
   has no plugin-level settings page; `HasSettingsInterface` merely sends the
   plugin a `showSettingsInterface` event that it must handle by drawing its own
   window. From a property inspector, `set`/`getGlobalSettings` take
   `context: inPropertyInspectorUUID`; from the plugin, the plugin UUID.
7. Two cosmetic requests are impossible from a plugin (half-size side buttons on
   the dial row; key 13 drawn as one wide key): the layout is hardcoded in
   OpenDeck's `DeviceView.svelte`/`Key.svelte`.

## Subagents

Five task-specific subagents, mirrored for both tools so either can drive the
same workflow. Spawn them only when asked to.

- **Claude Code:** `~/.claude/agents/*.md` — tiers map to `haiku` / `sonnet` /
  `opus`. Session default is `opus` with `effortLevel: high`.
- **opencode:** `~/.config/opencode/agents/*.md` — same five agents under the
  GLM family: `glm-5-turbo` / `glm-4.7` / `glm-5.2`.

| Agent | Tier | Use it for |
|---|---|---|
| `scout` | fast | "where does X live", read-only sweeps, path lists |
| `implementer` | mid | a change that is already decided; mechanical refactors; tests |
| `doc-writer` | mid | READMEs and the EN/ES pair |
| `deep-debugger` | strong | unknown causes, timing/USB/protocol weirdness, design trade-offs |
| `reviewer` | strong | reviewing a diff before commit; reports, does not fix |
