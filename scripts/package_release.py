#!/usr/bin/env python3
"""Package the built plugin into per-model release zips (Windows and Linux in one).

    python scripts/package_release.py --exe dist/d200x_plugin.exe [--linux-bin dist/d200x_plugin]
                                      [--version 1.2.3]

Writes to release/:
    opendeck-ulanzi-<model>-v<version>.zip   one per model, with the model preset in
                                             defaults.json; OpenDeck's plugin catalogue
                                             asks which one to install
    notes.md                                         release notes, taken from
                                                     this version's CHANGELOG.md entry

The version defaults to the one in manifest.json; when given (CI passes the
tag), it must match the manifest, so a tag can't ship a mislabelled build.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = "dev.kastro5.ulanzi-d200.sdPlugin"
MODELS = ("d200h", "d200x")
REPO = "https://github.com/kastro5/opendeck-ulanzi-d200"
# The self-contained Linux build, which launch.sh runs when it's there.
LINUX_BIN = "d200x_plugin-linux"
UDEV_RULE = "60-ulanzi-d200x.rules"
# Build leftovers, and files written per zip below.
SKIP = {"__pycache__", "defaults.json", "d200x_plugin.exe", LINUX_BIN}


def manifest_version() -> str:
    with open(ROOT / PLUGIN / "manifest.json", encoding="utf-8") as handle:
        return json.load(handle)["Version"]


def changelog_entry(version: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(version)}\b.*?$\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        sys.exit(f"CHANGELOG.md has no '## {version}' entry")
    return match.group(1).strip()


def build_zip(model: str, version: str, exe: Path, linux_bin: Path | None, out: Path) -> Path:
    staging = out / model / PLUGIN
    shutil.copytree(ROOT / PLUGIN, staging, ignore=lambda _dir, names: [n for n in names if n in SKIP])
    shutil.copy2(exe, staging / exe.name)
    if linux_bin:
        shutil.copy2(linux_bin, staging / LINUX_BIN)
    # Linux users need the udev rule before anything works; ship it with the zip.
    shutil.copy2(ROOT / UDEV_RULE, staging / UDEV_RULE)
    (staging / "defaults.json").write_text(json.dumps({"model": model}), encoding="utf-8")

    archive = out / f"opendeck-ulanzi-{model}-v{version}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if not path.is_file():
                continue
            # Forward slashes: some extractors mangle backslashed entries.
            name = path.relative_to(out / model).as_posix()
            if path.suffix in (".sh", ".py") or path.name == LINUX_BIN:
                # Linux runs these: the executable bit, and LF line endings for the
                # scripts, whatever the checkout this was built from did to them.
                info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                info.external_attr = 0o100755 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                data = path.read_bytes()
                zf.writestr(info, data if path.name == LINUX_BIN else data.replace(b"\r\n", b"\n"))
            else:
                zf.write(path, name)
    shutil.rmtree(out / model)
    return archive


def notes(version: str) -> str:
    rows = "\n".join(
        f"| **{model.upper()}** | `opendeck-ulanzi-{model}-v{version}.zip` |" for model in MODELS)
    return f"""{changelog_entry(version)}

## Download

| Your deck | Download |
|---|---|
{rows}

Same zip for Windows and Linux, self-contained on both (no Python needed). Install it from OpenDeck's plugin catalogue (pick your model when asked), or extract it into OpenDeck's `plugins` folder and restart OpenDeck. Upgrading from before 1.3.0: the plugin's folder is now `dev.kastro5.ulanzi-d200.sdPlugin`; remove the old `com.ulanzi.d200x.sdPlugin` (OpenDeck's Plugins tab), and your settings carry over. Full instructions are in the [README]({REPO}#install).

Built by GitHub Actions from the tagged commit.
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--linux-bin", type=Path, help="the PyInstaller build for Linux")
    parser.add_argument("--version", help="defaults to manifest.json; must match it")
    parser.add_argument("--out", type=Path, default=ROOT / "release")
    args = parser.parse_args()

    version = manifest_version()
    if args.version and args.version.lstrip("v") != version:
        sys.exit(f"version {args.version} does not match manifest.json ({version})")
    if not args.exe.is_file():
        sys.exit(f"no exe at {args.exe}")
    if args.linux_bin and not args.linux_bin.is_file():
        sys.exit(f"no Linux build at {args.linux_bin}")

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    for model in MODELS:
        print(build_zip(model, version, args.exe, args.linux_bin, args.out))
    (args.out / "notes.md").write_text(notes(version), encoding="utf-8")
    print(args.out / "notes.md")


if __name__ == "__main__":
    main()
