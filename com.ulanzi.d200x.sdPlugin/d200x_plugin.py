#!/usr/bin/env python3
"""OpenDeck device plugin for the Ulanzi D200X.

Exposes the D200X to OpenDeck as a device with:

    * 14 LCD keys  -- a 5x3 grid where the last two cells of the bottom row are
      a single, double-width screen (device index 13).
    * 2 side buttons (device indices 15/16), reported to OpenDeck as touchpoints.
    * 3 rotary encoders (device indices 17/18/19), reported as encoders.

OpenDeck grid position -> D200X hardware index is the identity mapping:

    Keypad  0..12  -> screens 0..12          (rows 1 and 2, plus 10/11/12)
    Keypad  13     -> the double-width screen
    Keypad  14     -> unused (right half of the double-width screen)
    Keypad  15/16  -> the two small side buttons  (touchpoints 1 and 2)
    Encoder 0/1/2  -> dials 17/18/19

OpenDeck renders every key to a 144x144 JPEG data URL and pushes it with
`setImage`; the plugin batches those into a single ZIP bundle (the only way the
D200X accepts icons) and writes it over raw HID.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import hashlib
import io
import json
import logging
import os
import queue
import random
import shutil
import struct
import subprocess
import sys
import threading
import time
import zipfile
from base64 import b64decode
from typing import Dict, List, Optional, Tuple

try:
    import hid
except ImportError:  # pragma: no cover - reported at runtime
    hid = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover - reported at runtime
    Image = None

try:
    import websockets
except ImportError:  # pragma: no cover - reported at runtime
    websockets = None


# --------------------------------------------------------------------------- #
# Device constants
# --------------------------------------------------------------------------- #

VENDOR_ID = 0x2207
PRODUCT_ID = 0x0019

PACKET_SIZE = 1024
CHUNK_DATA = 1016  # payload bytes carried by the first packet
HEADER = b"\x7c\x7c"

CMD_SET_BUTTONS = 0x0001
CMD_SET_SMALL_WINDOW = 0x0006
CMD_SET_BRIGHTNESS = 0x000A
CMD_SET_LABEL_STYLE = 0x000B
CMD_IN_BUTTON = 0x0101
CMD_IN_BUTTON_ALT = 0x0102

ICON_SIZE = 196          # native icon resolution of a single screen
WIDE_ICON_WIDTH = 392    # the double-width screen is squeezed from 392 -> 196

# Small-window (double-width screen) modes understood by the firmware.
WINDOW_MODE_STATS = 0
WINDOW_MODE_CLOCK = 1
WINDOW_MODE_IMAGE = 2

# What the wide screen shows when no other action occupies it. Stored in the
# plugin's global settings and edited from the "Wide screen" property inspector.
ACTION_WIDE_SCREEN = "com.ulanzi.d200x.widescreen"
WIDE_SETTING = "wideMode"
WIDE_MODES = {
    "clock": WINDOW_MODE_CLOCK,   # the firmware's own clock
    "stats": WINDOW_MODE_STATS,   # the firmware's CPU/RAM/GPU gauges
    "off": WINDOW_MODE_IMAGE,     # image mode fed a black icon
}
WIDE_DEFAULT = "clock"

# --------------------------------------------------------------------------- #
# OpenDeck device description
# --------------------------------------------------------------------------- #

DEVICE_ID = "ulanzi-d200x"  # first two chars must match DeviceNamespace ("ul")
DEVICE_NAME = "Ulanzi D200X"
DEVICE_TYPE = 0  # plain key grid (type 7 would enable Stream Deck+ LCD strips)

ROWS = 3
COLUMNS = 5
ENCODERS = 3
TOUCHPOINTS = 2

KEY_COUNT = ROWS * COLUMNS          # 15 grid slots
WIDE_KEY = 13                       # the double-width screen
PHANTOM_KEY = 14                    # right half of WIDE_KEY, not addressable
SCREEN_KEYS = [i for i in range(KEY_COUNT) if i != PHANTOM_KEY]  # 0..13
TOUCHPOINT_KEYS = [KEY_COUNT + i for i in range(TOUCHPOINTS)]    # 15, 16
DIAL_BASE = 17                      # hardware index of encoder 0

# --------------------------------------------------------------------------- #
# Timing
# --------------------------------------------------------------------------- #

FLUSH_DEBOUNCE = 0.35    # coalesce a burst of setImage events into one bundle
MIN_BUNDLE_INTERVAL = 1.5  # never push ZIP bundles faster than this
CLOCK_INTERVAL = 2.0     # how often the CPU/RAM/GPU gauges are refreshed
GPU_INTERVAL = 5.0       # GPU utilisation is the expensive one to sample
RECONNECT_GRACE = 30.0   # tolerate this long of HID absence before deregistering
HID_POLL = 0.005

logger = logging.getLogger("d200x")


# --------------------------------------------------------------------------- #
# Raw HID protocol
# --------------------------------------------------------------------------- #

def build_packet(command: int, data: bytes, length: int) -> bytes:
    """Build a 1024-byte control packet."""
    packet = bytearray(PACKET_SIZE)
    packet[0:2] = HEADER
    packet[2:4] = struct.pack(">H", command)
    packet[4:8] = struct.pack("<I", length)
    packet[8:8 + len(data)] = data
    return bytes(packet)


def send_command(dev, command: int, payload: bytes) -> None:
    dev.write(build_packet(command, payload, len(payload)))


def send_bundle(dev, data: bytes) -> None:
    """Send a ZIP bundle: one header packet followed by raw 1024-byte chunks."""
    first = data[:CHUNK_DATA].ljust(CHUNK_DATA, b"\x00")
    dev.write(build_packet(CMD_SET_BUTTONS, first, len(data)))
    for offset in range(CHUNK_DATA, len(data), PACKET_SIZE):
        dev.write(data[offset:offset + PACKET_SIZE].ljust(PACKET_SIZE, b"\x00"))


def parse_input(data: bytes) -> Optional[Tuple[int, bool, Optional[int]]]:
    """Decode an input report.

    Returns ``(index, pressed, dial_event)`` where ``dial_event`` is None for
    normal keys and 0=release, 1=press, 2=turn left, 3=turn right for dials.
    """
    if len(data) < 12 or data[0:2] != HEADER:
        return None
    command = struct.unpack(">H", data[2:4])[0]
    if command not in (CMD_IN_BUTTON, CMD_IN_BUTTON_ALT):
        return None

    body = data[8:12]
    index = body[1]
    if index in (17, 18, 19) or body[2] == 2:
        return index, body[3] == 1, body[3]
    return index, body[3] == 0x01, None


# --------------------------------------------------------------------------- #
# Image handling
# --------------------------------------------------------------------------- #

def _decode_data_url(image: str) -> Optional[bytes]:
    if not image:
        return None
    if "," in image and image.startswith("data:"):
        image = image.split(",", 1)[1]
    try:
        return b64decode(image)
    except Exception:
        return None


def render_icon(raw: bytes, wide: bool) -> bytes:
    """Convert an OpenDeck-rendered image into a D200X icon PNG.

    The double-width screen is driven by a 196x196 icon that the firmware
    stretches to 2:1, so a wide icon is composed on a 392x196 canvas (square
    artwork centred, black bars either side) and then squeezed back down.
    """
    with Image.open(io.BytesIO(raw)) as src:
        img = src.convert("RGB").resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
        if wide:
            canvas = Image.new("RGB", (WIDE_ICON_WIDTH, ICON_SIZE), (0, 0, 0))
            canvas.paste(img, ((WIDE_ICON_WIDTH - ICON_SIZE) // 2, 0))
            img = canvas.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
        return out.getvalue()


def blank_icon() -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (ICON_SIZE, ICON_SIZE), (0, 0, 0)).save(out, format="PNG", optimize=True)
    return out.getvalue()


def build_bundle(icons: Dict[int, bytes], omit: Optional[frozenset] = None) -> bytes:
    """Pack icons + manifest into the ZIP bundle the firmware expects.

    Cells listed in ``omit`` get no manifest entry at all. A cell that is named
    in the manifest is repainted when the bundle lands, so the wide screen is
    left out whenever the firmware is the one drawing it -- otherwise every
    push flashes the icon underneath for as long as the repaint takes.

    The firmware chokes on 0x00/0x7c bytes landing on a 1024-byte packet
    boundary, so the bundle is rebuilt with differently sized padding until the
    layout is clean.
    """
    omit = omit or frozenset()
    data = b""
    for attempt in range(31):
        padding = "init" if attempt == 0 else "".join(
            random.choices("abcdefghijklmnopqrstuvwxyz", k=8 + attempt * 8)
        )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Written first so that retries shift every subsequent file offset.
            zf.writestr("dummy.txt", padding)

            manifest: Dict[str, dict] = {}
            written: Dict[str, bool] = {}
            for index in SCREEN_KEYS:
                if index in omit:
                    continue
                entry = {"State": 0, "ViewParam": [{"Text": ""}]}
                png = icons.get(index)
                if png:
                    # Content-addressed so identical icons are stored once and a
                    # changed icon always gets a name the firmware hasn't cached.
                    name = f"icons/{hashlib.sha1(png).hexdigest()[:12]}.png"
                    if name not in written:
                        zf.writestr(name, png)
                        written[name] = True
                    entry["ViewParam"][0]["Icon"] = name
                manifest[f"{index % COLUMNS}_{index // COLUMNS}"] = entry

            zf.writestr("manifest.json", json.dumps(manifest, sort_keys=True,
                                                   separators=(",", ":"), indent=2))

        data = buffer.getvalue()
        if not any(data[i:i + 1] in (b"\x00", b"\x7c") for i in range(CHUNK_DATA, len(data), PACKET_SIZE)):
            return data

    logger.warning("No clean bundle layout after 30 attempts; sending anyway")
    return data


# --------------------------------------------------------------------------- #
# System statistics
# --------------------------------------------------------------------------- #

class SystemStats:
    """CPU / RAM / GPU utilisation, read straight from /proc and /sys.

    The firmware has no way of measuring the host, so the three percentages it
    draws on the status screen are whatever the last SET_SMALL_WINDOW command
    carried -- send zeroes and the gauges sit at zero.
    """

    def __init__(self) -> None:
        self._cpu_prev: Optional[Tuple[int, int]] = None
        self._gpu_nodes = sorted(glob.glob("/sys/class/drm/card*/device/gpu_busy_percent"))
        self._nvidia = None if self._gpu_nodes else shutil.which("nvidia-smi")
        self._gpu_value = 0
        self._gpu_read = 0.0

    def read(self) -> Tuple[int, int, int]:
        return self._cpu(), self._memory(), self._gpu()

    def _cpu(self) -> int:
        try:
            with open("/proc/stat") as handle:
                fields = [int(value) for value in handle.readline().split()[1:]]
        except (OSError, ValueError):
            return 0
        if len(fields) < 5:
            return 0

        idle = fields[3] + fields[4]  # idle + iowait
        total = sum(fields)
        previous, self._cpu_prev = self._cpu_prev, (idle, total)
        if previous is None:
            return 0

        total_delta = total - previous[1]
        if total_delta <= 0:
            return 0
        busy = total_delta - (idle - previous[0])
        return max(0, min(100, round(100 * busy / total_delta)))

    def _memory(self) -> int:
        values: Dict[str, int] = {}
        try:
            with open("/proc/meminfo") as handle:
                for line in handle:
                    key, _, rest = line.partition(":")
                    if key in ("MemTotal", "MemAvailable"):
                        values[key] = int(rest.split()[0])
                        if len(values) == 2:
                            break
        except (OSError, ValueError):
            return 0

        total = values.get("MemTotal", 0)
        if total <= 0:
            return 0
        return max(0, min(100, round(100 * (total - values.get("MemAvailable", 0)) / total)))

    def _gpu(self) -> int:
        now = time.monotonic()
        if now - self._gpu_read < GPU_INTERVAL:
            return self._gpu_value
        self._gpu_read = now

        for node in self._gpu_nodes:  # amdgpu exposes this directly
            try:
                with open(node) as handle:
                    self._gpu_value = max(0, min(100, int(handle.read().strip())))
                return self._gpu_value
            except (OSError, ValueError):
                continue

        if self._nvidia:
            try:
                result = subprocess.run(
                    [self._nvidia, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2, check=True)
                self._gpu_value = max(0, min(100, int(result.stdout.split()[0])))
            except Exception:
                # Don't keep paying for a query that does not work.
                self._nvidia = None
                self._gpu_value = 0
        return self._gpu_value


# --------------------------------------------------------------------------- #
# HID worker
# --------------------------------------------------------------------------- #

class HidWorker(threading.Thread):
    """Owns the HID handle: all reads and writes happen on this thread.

    The D200X briefly resets its USB interface while it decodes a large icon
    bundle. That looks exactly like an unplug, so the worker silently reopens
    the handle and only reports a disconnect once the device has been missing
    for ``RECONNECT_GRACE`` seconds.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, on_connect, on_disconnect, on_input):
        super().__init__(name="d200x-hid", daemon=True)
        self._loop = loop
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect
        self._on_input = on_input
        self._commands: "queue.Queue[Tuple[str, tuple]]" = queue.Queue()
        self._stop = threading.Event()
        self._dev = None
        self._announced = False
        self._missing_since: Optional[float] = None

    # -- public API (thread safe) ------------------------------------------- #

    def submit(self, kind: str, *args) -> None:
        self._commands.put((kind, args))

    def stop(self) -> None:
        self._stop.set()

    # -- internals ---------------------------------------------------------- #

    def _dispatch(self, callback, *args) -> None:
        self._loop.call_soon_threadsafe(callback, *args)

    def _open(self) -> bool:
        try:
            devices = hid.enumerate(VENDOR_ID, PRODUCT_ID)
            if not devices:
                return False
            dev = hid.device()
            dev.open_path(devices[0]["path"])
            dev.set_nonblocking(True)
        except Exception as exc:
            logger.debug("Open failed: %s", exc)
            return False

        self._dev = dev
        self._missing_since = None
        if not self._announced:
            self._announced = True
            logger.info("D200X connected")
            self._dispatch(self._on_connect)
        else:
            logger.info("D200X HID handle reacquired")
        return True

    def _drop(self, reason: str) -> None:
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:
                pass
            self._dev = None
        if self._missing_since is None:
            self._missing_since = time.monotonic()
            logger.debug("HID handle lost (%s)", reason)

    def _check_gone(self) -> None:
        if (self._announced and self._missing_since is not None
                and time.monotonic() - self._missing_since > RECONNECT_GRACE):
            self._announced = False
            self._missing_since = None
            logger.warning("D200X gone for %.0fs — reporting disconnect", RECONNECT_GRACE)
            self._dispatch(self._on_disconnect)

    def _run_commands(self) -> None:
        while True:
            try:
                kind, args = self._commands.get_nowait()
            except queue.Empty:
                return
            try:
                if kind == "bundle":
                    send_bundle(self._dev, args[0])
                elif kind == "command":
                    send_command(self._dev, args[0], args[1])
            except Exception as exc:
                # Re-queue so the write survives the reconnect.
                self._commands.put((kind, args))
                self._drop(f"write: {exc}")
                return

    def run(self) -> None:
        while not self._stop.is_set():
            if self._dev is None:
                if not self._open():
                    self._check_gone()
                    time.sleep(1.0)
                continue

            self._run_commands()
            if self._dev is None:
                continue

            try:
                report = self._dev.read(PACKET_SIZE)
            except Exception as exc:
                self._drop(f"read: {exc}")
                continue

            if report:
                event = parse_input(bytes(report))
                if event:
                    self._dispatch(self._on_input, event)
            else:
                time.sleep(HID_POLL)

        self._drop("shutdown")


# --------------------------------------------------------------------------- #
# Plugin
# --------------------------------------------------------------------------- #

class D200XPlugin:
    def __init__(self, port: int, uuid: str, register_event: str):
        self._port = port
        self._uuid = uuid
        self._register_event = register_event
        self._ws = None
        self._loop: asyncio.AbstractEventLoop
        self._hid: Optional[HidWorker] = None

        self._icons: Dict[int, bytes] = {}
        self._blank = b""
        self._sent_signature: Optional[str] = None
        self._flush_handle: Optional[asyncio.TimerHandle] = None
        self._flush_task: Optional[asyncio.Task] = None
        self._last_bundle = 0.0
        self._registered = False
        self._window_mode = WINDOW_MODE_CLOCK
        self._wide_setting = WIDE_DEFAULT
        self._settings_seen = False
        self._wide_contexts: set = set()   # our own action sitting on the wide key
        self._stats = SystemStats()
        self._stats_cache: Tuple[int, int, int] = (0, 0, 0)

    # -- websocket ---------------------------------------------------------- #

    async def _send(self, payload: dict) -> None:
        if self._ws is None:
            logger.warning("Dropped %s: no websocket", payload.get("event"))
            return
        try:
            await self._ws.send(json.dumps(payload))
        except Exception as exc:
            logger.warning("Failed to send %s: %s", payload.get("event"), exc)

    async def run(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._blank = await asyncio.to_thread(blank_icon)

        self._hid = HidWorker(
            self._loop,
            lambda: self._loop.create_task(self._on_device_connected()),
            lambda: self._loop.create_task(self._on_device_disconnected()),
            self._on_hid_input,
        )

        clock: Optional[asyncio.Task] = None
        try:
            async with websockets.connect(f"ws://127.0.0.1:{self._port}") as ws:
                self._ws = ws
                await self._send({"event": self._register_event, "uuid": self._uuid})
                logger.info("Registered plugin %s on port %d", self._uuid, self._port)
                await self._send({"event": "getGlobalSettings", "context": self._uuid})

                # Only now may the HID worker report a connection: registerDevice
                # has nowhere to go before the socket is up.
                self._hid.start()
                clock = self._loop.create_task(self._clock_loop())

                async for message in ws:
                    try:
                        await self._on_message(json.loads(message))
                    except Exception:
                        logger.exception("Error handling message")
        finally:
            if clock is not None:
                clock.cancel()
            self._hid.stop()
        logger.info("Websocket closed, exiting")

    # -- device lifecycle --------------------------------------------------- #

    async def _on_device_connected(self) -> None:
        await self._send({
            "event": "registerDevice",
            "payload": {
                "id": DEVICE_ID,
                "plugin": self._uuid,
                "name": DEVICE_NAME,
                "rows": ROWS,
                "columns": COLUMNS,
                "encoders": ENCODERS,
                "touchpoints": TOUCHPOINTS,
                "infobars": 0,
                "type": DEVICE_TYPE,
            },
        })
        self._registered = True
        logger.info("Registered device %s with OpenDeck", DEVICE_ID)

        # OpenDeck bakes titles into the images it renders, so the firmware must
        # not draw labels of its own on top.
        self._hid.submit("command", CMD_SET_LABEL_STYLE, json.dumps({
            "Align": "bottom",
            "Color": 0xFFFFFF,
            "FontName": "Roboto",
            "ShowTitle": False,
            "Size": 10,
            "Weight": 80,
        }).encode("utf-8"))
        self._push_window_mode()

        if self._icons:
            # Re-arm the cached bundle rather than asking OpenDeck to re-render:
            # a rerender request on every firmware reset turns into a loop.
            logger.info("Restoring %d cached icons", len(self._icons))
            self._sent_signature = None
            self._schedule_flush()
        else:
            await self._send({"event": "rerenderImages", "payload": DEVICE_ID})

    async def _on_device_disconnected(self) -> None:
        if not self._registered:
            return
        self._registered = False
        await self._send({"event": "deregisterDevice", "payload": DEVICE_ID})
        logger.info("Deregistered device %s", DEVICE_ID)

    # -- inbound events ----------------------------------------------------- #

    async def _on_message(self, message: dict) -> None:
        event = message.get("event")
        if event == "setImage":
            self._on_set_image(message)
        elif event == "setBrightness":
            brightness = max(0, min(100, int(message.get("brightness", 100))))
            self._hid.submit("command", CMD_SET_BRIGHTNESS, str(brightness).encode("ascii"))
            logger.debug("Brightness -> %d", brightness)
        elif event == "didReceiveGlobalSettings":
            self._on_global_settings((message.get("payload") or {}).get("settings") or {})
        elif event in ("willAppear", "willDisappear"):
            self._on_appearance(event, message)
        elif event in ("deviceDidConnect", "deviceDidDisconnect"):
            pass
        else:
            logger.debug("Ignoring event %s", event)

    def _on_global_settings(self, settings: dict) -> None:
        mode = str(settings.get(WIDE_SETTING, WIDE_DEFAULT)).lower()
        if mode not in WIDE_MODES:
            mode = WIDE_DEFAULT
        if mode == self._wide_setting and self._settings_seen:
            return
        self._settings_seen = True
        self._wide_setting = mode
        logger.info("Wide screen: %s", mode)
        self._apply_wide_mode()

    def _on_appearance(self, event: str, message: dict) -> None:
        """Track our own 'Wide screen' action so its icon does not fight the mode."""
        if message.get("action") != ACTION_WIDE_SCREEN or message.get("device") != DEVICE_ID:
            return

        payload = message.get("payload") or {}
        coordinates = payload.get("coordinates") or {}
        if payload.get("controller", "Keypad") != "Keypad":
            return
        if coordinates.get("row", 0) * COLUMNS + coordinates.get("column", 0) != WIDE_KEY:
            return

        context = json.dumps(message.get("context"), sort_keys=True)
        if event == "willAppear":
            self._wide_contexts.add(context)
        else:
            self._wide_contexts.discard(context)
        logger.info("Wide screen action %s (%s)",
                    "placed" if event == "willAppear" else "removed", self._wide_setting)
        self._apply_wide_mode()

    def _on_set_image(self, message: dict) -> None:
        if message.get("device") not in (None, DEVICE_ID):
            return

        controller = message.get("controller")
        position = message.get("position")

        if controller is None and position is None:
            self._icons.clear()
            self._schedule_flush()
            return

        # The dials have no displays of their own.
        if controller != "Keypad" or not isinstance(position, int):
            return
        if position == PHANTOM_KEY or position not in SCREEN_KEYS:
            # 14 is the right half of the wide screen; 15/16 are the side
            # buttons, which have no display.
            return

        raw = _decode_data_url(message.get("image") or "")
        if raw is None:
            self._icons.pop(position, None)
            self._schedule_flush()
            return

        try:
            icon = render_icon(raw, wide=(position == WIDE_KEY))
        except Exception as exc:
            logger.warning("Could not decode image for key %s: %s", position, exc)
            return

        self._icons[position] = icon
        self._schedule_flush()

    # -- outbound HID input ------------------------------------------------- #

    def _on_hid_input(self, event: Tuple[int, bool, Optional[int]]) -> None:
        index, pressed, dial = event

        if dial is not None:
            if not (DIAL_BASE <= index < DIAL_BASE + ENCODERS):
                return
            position = index - DIAL_BASE
            if dial == 1:
                payload = {"event": "encoderDown", "payload": {"device": DEVICE_ID, "position": position}}
            elif dial == 0:
                payload = {"event": "encoderUp", "payload": {"device": DEVICE_ID, "position": position}}
            elif dial in (2, 3):
                payload = {"event": "encoderChange", "payload": {
                    "device": DEVICE_ID, "position": position, "ticks": -1 if dial == 2 else 1}}
            else:
                return
        elif index in SCREEN_KEYS or index in TOUCHPOINT_KEYS:
            payload = {"event": "keyDown" if pressed else "keyUp",
                       "payload": {"device": DEVICE_ID, "position": index}}
        else:
            logger.debug("Unmapped hardware index %d", index)
            return

        self._loop.create_task(self._send(payload))

    # -- icon bundle flushing ----------------------------------------------- #

    def _schedule_flush(self) -> None:
        if self._flush_handle is not None:
            self._flush_handle.cancel()
        self._flush_handle = self._loop.call_later(FLUSH_DEBOUNCE, self._start_flush)

    def _start_flush(self) -> None:
        self._flush_handle = None
        if self._flush_task is None or self._flush_task.done():
            self._flush_task = self._loop.create_task(self._flush())
        else:
            # A bundle is already on its way out; queue another pass after it.
            self._schedule_flush()

    async def _flush(self) -> None:
        wait = MIN_BUNDLE_INTERVAL - (time.monotonic() - self._last_bundle)
        if wait > 0:
            await asyncio.sleep(wait)

        icons = {index: self._icons.get(index, self._blank) for index in SCREEN_KEYS}

        mode = self._wide_mode()
        if mode != self._window_mode:
            self._window_mode = mode
            self._push_window_mode()

        # In clock and stats mode the firmware draws the wide screen itself, so
        # keep that cell out of the bundle entirely: naming it would repaint it
        # on every push, which reads as a flicker. "Off" is image mode fed a
        # black icon, so it stays in.
        omit = frozenset() if mode == WINDOW_MODE_IMAGE else frozenset({WIDE_KEY})

        signature = hashlib.sha1(
            b"".join(hashlib.sha1(icons[i]).digest() for i in SCREEN_KEYS if i not in omit)
            + repr(sorted(omit)).encode()
        ).hexdigest()
        if signature == self._sent_signature:
            return

        bundle = await asyncio.to_thread(build_bundle, icons, omit)
        self._sent_signature = signature
        self._last_bundle = time.monotonic()
        self._hid.submit("bundle", bundle)
        logger.info("Pushed icon bundle (%d icons, %.1f KiB)", len(self._icons), len(bundle) / 1024)

    # -- small window ------------------------------------------------------- #

    def _wide_shows_action(self) -> bool:
        """True when the wide screen is displaying another action's icon."""
        return WIDE_KEY in self._icons and not self._wide_contexts

    def _wide_mode(self) -> int:
        if self._wide_shows_action():
            return WINDOW_MODE_IMAGE
        return WIDE_MODES[self._wide_setting]

    def _apply_wide_mode(self) -> None:
        mode = self._wide_mode()
        if mode != self._window_mode:
            self._window_mode = mode
            self._push_window_mode()
        self._schedule_flush()

    def _push_window_mode(self) -> None:
        cpu, memory, gpu = self._stats_cache
        payload = f"{self._window_mode}|{cpu}|{memory}|{time.strftime('%H:%M:%S')}|{gpu}"
        self._hid.submit("command", CMD_SET_SMALL_WINDOW, payload.encode("utf-8"))

    async def _clock_loop(self) -> None:
        while True:
            await asyncio.sleep(CLOCK_INTERVAL)
            if not self._registered or self._window_mode != WINDOW_MODE_STATS:
                # Only the gauges need feeding. Restating clock or image mode
                # just makes the firmware repaint the screen, which blinks.
                continue
            self._stats_cache = await asyncio.to_thread(self._stats.read)
            self._push_window_mode()


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-port", type=int, required=True)
    parser.add_argument("-pluginUUID", dest="uuid", required=True)
    parser.add_argument("-registerEvent", dest="register_event", default="registerPlugin")
    parser.add_argument("-info", dest="info", default="{}")
    known, _ = parser.parse_known_args(argv)
    return known


def main() -> int:
    logging.basicConfig(
        level=logging.DEBUG if os.environ.get("D200X_DEBUG") else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        stream=sys.stderr,
    )

    missing = [name for name, module in
               (("hidapi", hid), ("Pillow", Image), ("websockets", websockets)) if module is None]
    if missing:
        logger.error("Missing Python packages: %s", ", ".join(missing))
        logger.error("Install them on the host, e.g. "
                     "sudo pacman -S python-hidapi python-pillow python-websockets")
        return 1

    args = parse_args(sys.argv[1:])
    plugin = D200XPlugin(args.port, args.uuid, args.register_event)
    try:
        asyncio.run(plugin.run())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Plugin terminated")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
