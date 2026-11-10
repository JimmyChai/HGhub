#!/usr/bin/env python3
"""Apply the upstream iOS workflow's orientation and transport settings."""
import plistlib
from pathlib import Path

paths = sorted(Path("src-tauri/gen/apple").rglob("Info.plist"))
if not paths:
    raise SystemExit("No generated iOS Info.plist found")
orientations = [
    "UIInterfaceOrientationPortrait",
    "UIInterfaceOrientationLandscapeLeft",
    "UIInterfaceOrientationLandscapeRight",
]
for path in paths:
    with path.open("rb") as stream:
        info = plistlib.load(stream)
    for suffix in ("", "~iphone", "~ipad"):
        info[f"UISupportedInterfaceOrientations{suffix}"] = orientations
    info["NSAppTransportSecurity"] = {"NSAllowsArbitraryLoads": True}
    with path.open("wb") as stream:
        plistlib.dump(info, stream, sort_keys=False)
    print(f"Prepared {path}")
