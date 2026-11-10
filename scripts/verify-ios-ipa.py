#!/usr/bin/env python3
"""Verify the real IPA container and arm64 iPhoneOS executable, then hash it.

This is build-artifact validation, NOT an iPhone runtime or playback test.
"""
import hashlib
import json
import os
import plistlib
import struct
import subprocess
import sys
import zipfile
from pathlib import Path


def verify(path):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("Corrupt IPA ZIP member")
        candidates = [n for n in archive.namelist()
                      if n.startswith("Payload/") and n.endswith(".app/Info.plist")
                      and len(Path(n).parts) == 3]
        if len(candidates) != 1:
            raise ValueError(f"Expected one app, found {candidates}")
        plist_path = candidates[0]
        info = plistlib.loads(archive.read(plist_path))
        if info.get("CFBundleIdentifier") != "com.hghub.huangguo":
            raise ValueError("Unexpected bundle identifier")
        if info.get("CFBundleSupportedPlatforms") != ["iPhoneOS"]:
            raise ValueError("Not an iPhoneOS device app")
        executable = info["CFBundleExecutable"]
        if Path(executable).name != executable:
            raise ValueError("Invalid executable name")
        binary_path = str(Path(plist_path).parent / executable)
        binary = archive.read(binary_path)
        if len(binary) < 32:
            raise ValueError("Truncated Mach-O header")
        magic, cpu, subtype, filetype, ncmds, sizeofcmds, flags, reserved = struct.unpack_from("<8I", binary)
        if (magic, cpu, filetype) != (0xFEEDFACF, 0x100000C, 2):
            raise ValueError("Expected thin arm64 Mach-O executable")
        if sizeofcmds > len(binary) - 32 or ncmds > sizeofcmds // 8:
            raise ValueError("Invalid load command table")
        offset, platforms = 32, []
        for _ in range(ncmds):
            if offset + 8 > 32 + sizeofcmds:
                raise ValueError("Truncated load command")
            command, size = struct.unpack_from("<II", binary, offset)
            if size < 8 or offset + size > 32 + sizeofcmds:
                raise ValueError("Invalid load command size")
            if command == 0x32:
                if size < 24:
                    raise ValueError("Truncated LC_BUILD_VERSION")
                platforms.append(struct.unpack_from("<I", binary, offset + 8)[0])
            offset += size
        if platforms != [2]:
            raise ValueError(f"Expected LC_BUILD_VERSION platform iOS=2, got {platforms}")
        if b"localhost:1420" in binary:
            raise ValueError("Development server URL found in binary")
        minimum = info.get("MinimumOSVersion")
        if not minimum:
            raise ValueError("MinimumOSVersion is absent")
        result = {
            "file": path.name,
            "sha256": hashlib.file_digest(path.open("rb"), "sha256").hexdigest(),
            "bytes": path.stat().st_size,
            "bundle_identifier": info["CFBundleIdentifier"],
            "version": info["CFBundleShortVersionString"],
            "build": info["CFBundleVersion"],
            "minimum_ios": minimum,
            "supported_platforms": info["CFBundleSupportedPlatforms"],
            "architecture": "arm64",
            "macho_platform": "iOS device (2), not simulator",
            "requires_user_signing": True,
            "device_runtime_tested": False,
            "upstream_playback_tested": False,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            "ci_run": os.environ.get("GITHUB_RUN_ID"),
        }
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: verify-ios-ipa.py FILE.ipa")
    path = Path(sys.argv[1])
    result = verify(path)
    path.with_suffix(".verification.json").write_text(json.dumps(result, indent=2) + "\n")
    path.with_suffix(".sha256").write_text(f"{result['sha256']}  {path.name}\n")
    print(json.dumps(result, indent=2))
